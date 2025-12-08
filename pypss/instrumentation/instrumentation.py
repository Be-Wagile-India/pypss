import functools
import time
import random
import inspect
# Removed Optional, Any as they are unused

from ..utils import GLOBAL_CONFIG
from ..utils.config import (
    _get_effective_sample_rate,
)  # Import _get_effective_sample_rate from config
from ..utils.trace_utils import finalize_trace, get_memory_usage

# Import async context for integration
try:
    from .async_ops import _current_trace_context, AsyncTraceContext
except ImportError:  # Removed debug print
    _current_trace_context = None  # type: ignore
    AsyncTraceContext = None  # type: ignore


def monitor_function(name=None, branch_tag=None, module_name=None):
    def decorator(func):
        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def wrapper(*args, **kwargs):
                _trace_name = name or func.__name__
                _module_name = module_name or getattr(func, "__module__", "unknown")

                # Pre-calculate effective sample rate (assuming no error yet)
                current_sample_rate = _get_effective_sample_rate(
                    False, _trace_name, _module_name
                )

                # Sampling Check
                if current_sample_rate < 1.0 and random.random() > current_sample_rate:
                    return await func(*args, **kwargs)

                # Capture Start Metrics
                start_wall = time.time()
                start_cpu = time.process_time()
                start_mem = get_memory_usage()
                error_occurred = False
                exception_type = None
                exception_message = None
                yield_count = 0

                # Setup Async Context for Yield Counting (if available)
                token = None
                # print(f"DEBUG: _current_trace_context in async wrapper: {_current_trace_context}", file=sys.stderr)
                ctx = AsyncTraceContext(
                    name=name or func.__name__,
                    module=module_name or getattr(func, "__module__", "unknown"),
                    branch_tag=branch_tag,
                    start_wall=start_wall,
                )
                token = _current_trace_context.set(ctx)

                try:
                    result = await func(*args, **kwargs)
                    return result
                except Exception as e:
                    error_occurred = True
                    exception_type = type(e).__name__
                    exception_message = str(e)
                    raise e
                finally:
                    # Retrieve yield count and reset context
                    if token is not None:
                        try:
                            final_ctx = _current_trace_context.get()
                            if final_ctx:
                                yield_count = final_ctx.yield_count
                        finally:
                            _current_trace_context.reset(token)

                    # If an error occurred, ensure it's sampled (overriding previous sampling decision)
                    if error_occurred:
                        current_sample_rate = GLOBAL_CONFIG.error_sample_rate
                        if (
                            random.random() > current_sample_rate
                        ):  # Check if still sampled out after adjustment
                            return

                    finalize_trace(
                        func,
                        name,
                        branch_tag,
                        module_name,
                        start_wall,
                        start_cpu,
                        start_mem,
                        error_occurred,
                        exception_type,
                        exception_message,
                        is_async=True,
                        yield_count=yield_count,
                    )

            return wrapper

        else:

            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                _trace_name = name or func.__name__
                _module_name = module_name or getattr(func, "__module__", "unknown")

                # Pre-calculate effective sample rate (assuming no error yet)
                current_sample_rate = _get_effective_sample_rate(
                    False, _trace_name, _module_name
                )

                # Sampling Check
                if current_sample_rate < 1.0 and random.random() > current_sample_rate:
                    return func(*args, **kwargs)

                # Capture Start Metrics
                start_wall = time.time()
                start_cpu = time.process_time()
                start_mem = get_memory_usage()
                error_occurred = False
                exception_type = None
                exception_message = None

                try:
                    result = func(*args, **kwargs)
                    return result
                except Exception as e:
                    error_occurred = True
                    exception_type = type(e).__name__
                    exception_message = str(e)
                    raise e
                finally:
                    # If an error occurred, ensure it's sampled (overriding previous sampling decision)
                    if error_occurred:
                        current_sample_rate = GLOBAL_CONFIG.error_sample_rate
                        if (
                            random.random() > current_sample_rate
                        ):  # Check if still sampled out after adjustment
                            return

                    finalize_trace(
                        func,
                        name,
                        branch_tag,
                        module_name,
                        start_wall,
                        start_cpu,
                        start_mem,
                        error_occurred,
                        exception_type,
                        exception_message,
                        is_async=False,
                    )

            return wrapper

    return decorator


class monitor_block:
    def __init__(self, name, branch_tag=None, module_name=None):
        self.name = name
        self.branch_tag = branch_tag
        if module_name:
            self.module_name = module_name
        else:
            try:
                # Portable way to get caller's module name.
                # inspect.stack() can be slow, but it's only called on __init__.
                frm = inspect.stack()[1]
                mod = inspect.getmodule(frm[0])
                self.module_name = mod.__name__ if mod else "unknown"
            except (IndexError, AttributeError):
                self.module_name = "unknown"
        self._should_sample = True  # Initialize flag

    def __enter__(self):
        _trace_name = self.name
        _module_name = self.module_name

        # Determine effective sample rate (assuming no error yet)
        current_sample_rate = _get_effective_sample_rate(
            False, _trace_name, _module_name
        )

        # Sampling Check
        if current_sample_rate < 1.0 and random.random() > current_sample_rate:
            self._should_sample = False
            return self

        self.start_wall = time.time()
        self.start_cpu = time.process_time()
        self.start_mem = get_memory_usage()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if not self._should_sample:
            return

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
            None,  # func is not available for block monitoring
            self.name,
            self.branch_tag,
            self.module_name,
            self.start_wall,
            self.start_cpu,
            self.start_mem,
            error_occurred,
            exception_type,
            exception_message,
            is_async=False,
        )
