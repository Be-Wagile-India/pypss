import time
import asyncio
import sys
import logging
from dataclasses import dataclass
from contextvars import ContextVar, Token
from typing import Optional
import random

from pypss.utils.config import GLOBAL_CONFIG, _get_effective_sample_rate
from pypss.core.adaptive_sampler import adaptive_sampler
from pypss.core.error_rate_monitor import error_rate_monitor
from pypss.utils.trace_utils import finalize_trace

logger = logging.getLogger(__name__)


@dataclass
class AsyncTraceContext:
    name: str
    module: str
    branch_tag: Optional[str]
    start_wall: float
    yield_count: int = 0


_current_trace_context: ContextVar[Optional[AsyncTraceContext]] = ContextVar(
    "pypss_async_context", default=None
)

_MONITORING_ACTIVE = False
_METRICS_COROUTINE_STARTS = 0
_SYS_MONITORING_TOOL_ID = None
_registered_yield_callback = None
_registered_start_callback = None


def _setup_sys_monitoring():
    global _MONITORING_ACTIVE

    if sys.version_info < (3, 12):
        return

    if _MONITORING_ACTIVE:
        return

    try:
        monitoring = getattr(sys, "monitoring", None)
        if not monitoring:
            logger.warning("PyPSS: sys.monitoring not found despite Python 3.12+")
            return

        global _SYS_MONITORING_TOOL_ID

        _SYS_MONITORING_TOOL_ID = None  # Reset

        # Try PROFILER_ID first
        try:
            monitoring.use_tool_id(monitoring.PROFILER_ID, "pypss_monitor")
            _SYS_MONITORING_TOOL_ID = monitoring.PROFILER_ID
        except ValueError:
            # PROFILER_ID in use, try DEBUGGER_ID
            logger.warning(
                "PyPSS: PROFILER_ID in use. Trying DEBUGGER_ID for async monitoring."
            )
            try:
                monitoring.use_tool_id(monitoring.DEBUGGER_ID, "pypss_monitor")
                _SYS_MONITORING_TOOL_ID = monitoring.DEBUGGER_ID
            except ValueError:
                # Both PROFILER_ID and DEBUGGER_ID in use, try other IDs
                logger.warning(
                    "PyPSS: DEBUGGER_ID also in use. Trying other available tool IDs."
                )
                for tool_id_candidate in range(
                    2, 20
                ):  # Start from 2 to avoid PROFILER_ID and DEBUGGER_ID
                    try:
                        monitoring.use_tool_id(tool_id_candidate, "pypss_monitor")
                        _SYS_MONITORING_TOOL_ID = tool_id_candidate
                        break
                    except ValueError:
                        logger.debug(
                            f"PyPSS: Tool ID {tool_id_candidate} already in use. Trying next."
                        )

        if _SYS_MONITORING_TOOL_ID is None:
            raise RuntimeError("Could not find an available sys.monitoring tool ID.")

        def yield_callback(code, instruction_offset, obj, *args):
            ctx = _current_trace_context.get()
            if ctx:
                ctx.yield_count += 1
            return None

        def start_callback(code, instruction_offset, arg=None):
            # Check for CO_COROUTINE (0x0080) or CO_ITERABLE_COROUTINE (0x0100) or CO_ASYNC_GENERATOR (0x0200)
            if arg and (code.co_flags & (0x0080 | 0x0100 | 0x0200)):
                global _METRICS_COROUTINE_STARTS
                _METRICS_COROUTINE_STARTS += 1
            return None

        _registered_yield_callback = yield_callback
        _registered_start_callback = start_callback

        monitoring.register_callback(
            _SYS_MONITORING_TOOL_ID,
            monitoring.events.PY_YIELD,
            _registered_yield_callback,
        )
        monitoring.register_callback(
            _SYS_MONITORING_TOOL_ID,
            monitoring.events.PY_START,
            _registered_start_callback,
        )

        monitoring.set_events(
            _SYS_MONITORING_TOOL_ID,
            monitoring.events.PY_YIELD | monitoring.events.PY_START,
        )

        _MONITORING_ACTIVE = True
        print(
            "DEBUG: _MONITORING_ACTIVE set to True in _setup_sys_monitoring. TOOL_ID:",
            _SYS_MONITORING_TOOL_ID,
            "Callbacks:",
            _registered_yield_callback,
            _registered_start_callback,
            file=sys.stderr,
        )
        logger.info(
            "PyPSS: sys.monitoring enabled for yield tracking and task churn analysis."
        )

    except Exception as e:
        print(
            "DEBUG: _setup_sys_monitoring failed:",
            e,
            file=sys.stderr,
        )
        logger.warning(f"PyPSS: Failed to initialize sys.monitoring: {e}")
        _MONITORING_ACTIVE = False


def _teardown_sys_monitoring():
    global \
        _MONITORING_ACTIVE, \
        _SYS_MONITORING_TOOL_ID, \
        _registered_yield_callback, \
        _registered_start_callback

    if sys.version_info < (3, 12):
        return

    if not _MONITORING_ACTIVE:
        return

    try:
        monitoring = getattr(sys, "monitoring", None)
        if not monitoring:
            return

        if _SYS_MONITORING_TOOL_ID is not None:
            # Disable events
            monitoring.set_events(_SYS_MONITORING_TOOL_ID, 0)

            # Unregister callbacks
            if _registered_yield_callback:
                monitoring.unregister_callback(
                    _SYS_MONITORING_TOOL_ID,
                    monitoring.events.PY_YIELD,
                    _registered_yield_callback,
                )
            if _registered_start_callback:
                monitoring.unregister_callback(
                    _SYS_MONITORING_TOOL_ID,
                    monitoring.events.PY_START,
                    _registered_start_callback,
                )

            # Release tool ID
            monitoring.use_tool_id(_SYS_MONITORING_TOOL_ID, None)  # Release our tool_id

    except Exception as e:
        logger.warning(f"PyPSS: Failed to tear down sys.monitoring: {e}")
    finally:
        _MONITORING_ACTIVE = False
        _SYS_MONITORING_TOOL_ID = None
        _registered_yield_callback = None
        _registered_start_callback = None
        print(
            "DEBUG: _MONITORING_ACTIVE set to False in _teardown_sys_monitoring. TOOL_ID:",
            _SYS_MONITORING_TOOL_ID,
            file=sys.stderr,
        )
        logger.info("PyPSS: sys.monitoring disabled.")


class AsyncMonitor:
    def __init__(
        self,
        name: str,
        branch_tag: Optional[str] = None,
        module_name: Optional[str] = None,
    ):
        self.name = name
        self.branch_tag = branch_tag
        self.module_name = module_name or "unknown"
        self._token: Optional[Token[Optional[AsyncTraceContext]]] = None

    async def __aenter__(self):
        _trace_name = self.name
        _module_name = self.module_name

        # Pre-calculate effective sample rate (assuming no error yet)
        current_sample_rate = _get_effective_sample_rate(
            False, _trace_name, _module_name
        )

        if current_sample_rate < 1.0 and random.random() > current_sample_rate:
            # Mark that we skipped sampling this instance
            self._token = None
            return self

        start_wall = time.time()

        ctx = AsyncTraceContext(
            name=self.name,
            module=self.module_name,
            branch_tag=self.branch_tag,
            start_wall=start_wall,
            yield_count=0,
        )
        self._token = _current_trace_context.set(ctx)

        self.start_mem = 0
        if GLOBAL_CONFIG.w_ms > 0:
            import psutil

            self.start_mem = (
                psutil.Process().memory_info().rss
            )  # Assign the numeric value

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if not self._token:
            return

        ctx = _current_trace_context.get()
        _current_trace_context.reset(self._token)

        if ctx is None:
            return

        # Removed: duration calculation, now handled within finalize_trace

        # Removed: mem_diff calculation, now handled within finalize_trace

        error_occurred = exc_type is not None
        exception_type = exc_type.__name__ if exc_type else None
        exception_message = str(exc_val) if exc_val else None

        # If an error occurred, ensure it's sampled (overriding previous sampling decision)
        if error_occurred:
            current_sample_rate = GLOBAL_CONFIG.error_sample_rate
            if (
                random.random() > current_sample_rate
            ):  # Check if still sampled out after adjustment
                return

        finalize_trace(
            None,  # func is not directly available for AsyncMonitor
            ctx.name,
            ctx.branch_tag,
            ctx.module,
            ctx.start_wall,
            0.0,  # cpu_time cannot be reliably measured this way for async
            self.start_mem,
            error_occurred,
            exception_type,
            exception_message,
            is_async=True,
            yield_count=ctx.yield_count,
        )


class EventLoopHealthMonitor:
    def __init__(self, interval: float = 0.5, threshold: float = 0.001):
        self.interval = interval
        self.threshold = threshold
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._last_churn_check = time.time()
        self._last_coroutine_count = 0

    def start(self):
        if self._running:
            return
        self._running = True
        try:
            loop = asyncio.get_running_loop()
            self._task = loop.create_task(self._monitor_loop())
            logger.info(
                f"PyPSS: Event Loop Health Monitor started (interval={self.interval}s)"
            )
        except RuntimeError:
            self._running = False
            return

    def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None

    async def _monitor_loop(self):
        global _METRICS_COROUTINE_STARTS

        while self._running:
            try:
                start_time = time.perf_counter()

                await asyncio.sleep(self.interval)

                now = time.perf_counter()
                actual_duration = now - start_time
                lag = max(0.0, actual_duration - self.interval)

                try:
                    active_tasks = len(asyncio.all_tasks())
                except (RuntimeError, Exception) as e:
                    if isinstance(e, RuntimeError):
                        active_tasks = 0
                    else:
                        raise

                current_total_starts = _METRICS_COROUTINE_STARTS
                delta_starts = current_total_starts - self._last_coroutine_count
                self._last_coroutine_count = current_total_starts
                churn_rate = delta_starts / actual_duration

                if (lag > self.threshold) or (churn_rate > 10.0) or (active_tasks > 10):
                    finalize_trace(
                        None,  # func is not available here
                        "__event_loop_health__",
                        None,  # branch_tag
                        "pypss.system",  # module_name
                        time.time(),  # start_wall (using current time as timestamp)
                        0.0,  # start_cpu (no CPU time for system metrics)
                        0,  # start_mem (no start memory for system metrics)
                        False,  # error_occurred
                        None,  # exception_type
                        None,  # exception_message
                        metadata={
                            "system_metric": True,
                            "async_op": True,
                            "duration": self.interval,  # duration from when it wakes up from sleep
                            "wait_time": lag,
                            "cpu_time": 0.0,
                            "metadata": {  # Nested metadata for the original structure
                                "lag": lag,
                                "active_tasks": active_tasks,
                                "churn_rate": churn_rate,
                            },
                        },
                    )

                # Update adaptive sampler with current metrics
                adaptive_sampler.update_metrics(
                    lag=lag,
                    churn_rate=churn_rate,
                )

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"PyPSS: Loop Monitor error: {e}")
                try:
                    await asyncio.sleep(1.0)
                except asyncio.CancelledError:
                    break


_health_monitor_instance = None


def start_async_monitoring(enable_sys_monitoring: bool = True):
    global _health_monitor_instance

    if enable_sys_monitoring:
        _setup_sys_monitoring()

    if _health_monitor_instance is None:
        _health_monitor_instance = EventLoopHealthMonitor()

    try:
        asyncio.get_running_loop()
        _health_monitor_instance.start()
        error_rate_monitor.start()  # NEW
    except RuntimeError:
        logger.warning("PyPSS: start_async_monitoring called outside of event loop.")


def stop_async_monitoring():
    global _health_monitor_instance
    if _health_monitor_instance:
        _health_monitor_instance.stop()
    _teardown_sys_monitoring()  # Call teardown for sys.monitoring
    error_rate_monitor.stop()  # NEW
