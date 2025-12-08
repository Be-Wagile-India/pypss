import time
import asyncio
import sys
import logging
from dataclasses import dataclass
from contextvars import ContextVar
from typing import Optional

from pypss.instrumentation.collectors import global_collector
from pypss.utils.config import GLOBAL_CONFIG

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

        TOOL_ID = monitoring.PROFILER_ID

        try:
            monitoring.use_tool_id(TOOL_ID, "pypss_monitor")
        except ValueError:
            logger.warning(
                "PyPSS: PROFILER_ID in use. Trying DEBUGGER_ID for async monitoring."
            )
            TOOL_ID = monitoring.DEBUGGER_ID
            monitoring.use_tool_id(TOOL_ID, "pypss_monitor")

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

        monitoring.register_callback(
            TOOL_ID, monitoring.events.PY_YIELD, yield_callback
        )
        monitoring.register_callback(
            TOOL_ID, monitoring.events.PY_START, start_callback
        )

        monitoring.set_events(
            TOOL_ID, monitoring.events.PY_YIELD | monitoring.events.PY_START
        )

        _MONITORING_ACTIVE = True
        print(
            "DEBUG: _MONITORING_ACTIVE set to True in _setup_sys_monitoring.",
            file=sys.stderr,
        )
        logger.info(
            "PyPSS: sys.monitoring enabled for yield tracking and task churn analysis."
        )

    except Exception as e:
        logger.warning(f"PyPSS: Failed to initialize sys.monitoring: {e}")
        _MONITORING_ACTIVE = False


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
        self._token = None

    async def __aenter__(self):
        if (
            GLOBAL_CONFIG.sample_rate < 1.0
            and time.time() % 1.0 > GLOBAL_CONFIG.sample_rate
        ):
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

            self.start_mem = psutil.Process().memory_info().rss

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if not self._token:
            return

        ctx = _current_trace_context.get()
        _current_trace_context.reset(self._token)

        end_wall = time.time()
        duration = end_wall - ctx.start_wall

        end_mem = 0
        mem_diff = 0
        if self.start_mem > 0:
            import psutil

            end_mem = psutil.Process().memory_info().rss
            mem_diff = end_mem - self.start_mem

        error_occurred = exc_type is not None
        exception_type = exc_type.__name__ if exc_type else None
        exception_message = str(exc_val) if exc_val else None

        trace = {
            "name": ctx.name,
            "module": ctx.module,
            "branch_tag": ctx.branch_tag,
            "duration": duration,
            "cpu_time": 0.0,
            "wait_time": duration,
            "memory": end_mem,
            "memory_diff": mem_diff,
            "error": error_occurred,
            "exception_type": exception_type,
            "exception_message": exception_message,
            "timestamp": ctx.start_wall,
            "async_op": True,
            "yield_count": ctx.yield_count,
        }

        global_collector.add_trace(trace)


class EventLoopHealthMonitor:
    def __init__(self, interval: float = 0.5, threshold: float = 0.001):
        self.interval = interval
        self.threshold = threshold
        self._task = None
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

                trace = {
                    "name": "__event_loop_health__",
                    "module": "pypss.system",
                    "duration": self.interval,
                    "wait_time": lag,
                    "cpu_time": 0.0,
                    "timestamp": time.time(),
                    "async_op": True,
                    "system_metric": True,
                    "metadata": {
                        "lag": lag,
                        "active_tasks": active_tasks,
                        "churn_rate": churn_rate,
                    },
                }

                if (lag > self.threshold) or (churn_rate > 10.0) or (active_tasks > 10):
                    global_collector.add_trace(trace)

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
    except RuntimeError:
        logger.warning("PyPSS: start_async_monitoring called outside of event loop.")


def stop_async_monitoring():
    global _health_monitor_instance
    if _health_monitor_instance:
        _health_monitor_instance.stop()
