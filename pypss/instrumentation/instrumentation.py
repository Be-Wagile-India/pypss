import functools
import time
import psutil
import os
import random
import inspect
from .collectors import global_collector
from ..utils import GLOBAL_CONFIG

# Import async context for integration
try:
    from .async_ops import _current_trace_context, AsyncTraceContext
except ImportError:
    _current_trace_context = None  # type: ignore
    AsyncTraceContext = None  # type: ignore

# Memoize the process handle
_process = psutil.Process(os.getpid())


def get_memory_usage():
    """Returns RSS memory usage in bytes."""
    return _process.memory_info().rss


def _finalize_trace(
    func,
    name,
    branch_tag,
    module_name,
    start_wall,
    start_cpu,
    start_mem,
    error_info,
    is_async=False,
    yield_count=0,
):
    """Helper to calculate metrics and record the trace."""
    end_wall = time.time()
    end_cpu = time.process_time()
    end_mem = get_memory_usage()

    duration_wall = end_wall - start_wall
    duration_cpu = end_cpu - start_cpu

    # Concurrency Wait Time (Approximate)
    if is_async:
        # For async functions, process_time() is unreliable (includes other tasks).
        # We assume async tasks are primarily I/O bound.
        # We treat the entire duration as 'wait_time' (waiting for I/O or Event Loop).
        # This penalizes blocking CPU work in async (which increases duration)
        # and event loop lag, which is appropriate for Concurrency Chaos metric.
        duration_cpu = 0.0  # Cannot reliably attribute CPU to this specific task
        wait_time = duration_wall
    else:
        # If Wall Time > CPU Time, we were waiting (I/O, Locks, Sleep)
        wait_time = max(0.0, duration_wall - duration_cpu)

    # Extract source location and module if available
    filename = getattr(func.__code__, "co_filename", "unknown")
    lineno = getattr(func.__code__, "co_firstlineno", 0)
    # Use provided module_name or fallback to auto-detection
    final_module_name = module_name or getattr(func, "__module__", "unknown")

    error_occurred, exception_type, exception_message = error_info

    trace = {
        "trace_id": f"{start_wall}-{random.randint(0, 1_000_000)}",
        "name": name or func.__name__,
        "filename": filename,
        "lineno": lineno,
        "module": final_module_name,
        "duration": duration_wall,
        "cpu_time": duration_cpu,
        "wait_time": wait_time,
        "memory": end_mem,
        "memory_diff": end_mem - start_mem,
        "error": error_occurred,
        "exception_type": exception_type,
        "exception_message": exception_message,
        "branch_tag": branch_tag,
        "timestamp": start_wall,
    }

    if is_async:
        trace["async_op"] = True
        trace["yield_count"] = yield_count

    global_collector.add_trace(trace)


def monitor_function(name=None, branch_tag=None, module_name=None):
    def decorator(func):
        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def wrapper(*args, **kwargs):
                # Sampling Check
                if (
                    GLOBAL_CONFIG.sample_rate < 1.0
                    and random.random() > GLOBAL_CONFIG.sample_rate
                ):
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
                if _current_trace_context is not None:
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

                    _finalize_trace(
                        func,
                        name,
                        branch_tag,
                        module_name,
                        start_wall,
                        start_cpu,
                        start_mem,
                        (error_occurred, exception_type, exception_message),
                        is_async=True,
                        yield_count=yield_count,
                    )

            return wrapper

        else:

            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                # Sampling Check
                if (
                    GLOBAL_CONFIG.sample_rate < 1.0
                    and random.random() > GLOBAL_CONFIG.sample_rate
                ):
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
                    _finalize_trace(
                        func,
                        name,
                        branch_tag,
                        module_name,
                        start_wall,
                        start_cpu,
                        start_mem,
                        (error_occurred, exception_type, exception_message),
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

    def __enter__(self):
        self.start_wall = time.time()
        self.start_cpu = time.process_time()
        self.start_mem = get_memory_usage()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        end_wall = time.time()
        end_cpu = time.process_time()
        end_mem = get_memory_usage()

        duration_wall = end_wall - self.start_wall
        duration_cpu = end_cpu - self.start_cpu
        wait_time = max(0.0, duration_wall - duration_cpu)

        exception_type = None
        exception_message = None
        if exc_type is not None:
            exception_type = exc_type.__name__
            exception_message = str(exc_val)

        trace = {
            "name": self.name,
            "duration": duration_wall,
            "cpu_time": duration_cpu,
            "wait_time": wait_time,
            "error": exc_type is not None,
            "exception_type": exception_type,
            "exception_message": exception_message,
            "branch_tag": self.branch_tag,
            "memory": end_mem,
            "memory_diff": end_mem - self.start_mem,
            "timestamp": self.start_wall,
            "module": self.module_name,
        }
        global_collector.add_trace(trace)
