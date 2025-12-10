import functools
import inspect
import random
import time

from ..core.context import get_tags
from ..utils import GLOBAL_CONFIG
from ..utils.config import _get_effective_sample_rate
from ..utils.trace_utils import finalize_trace, get_memory_usage

# Import async context for integration
try:
    from .async_ops import AsyncTraceContext, _current_trace_context
except ImportError:
    _current_trace_context = None  # type: ignore
    AsyncTraceContext = None  # type: ignore


def monitor_function(name=None, branch_tag=None, module_name=None, profile_threshold_ms=0):
    def decorator(func):
        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def wrapper(*args, **kwargs):
                _trace_name = name or func.__name__
                _module_name = module_name or getattr(func, "__module__", "unknown")

                current_sample_rate = _get_effective_sample_rate(False, _trace_name, _module_name)

                if current_sample_rate < 1.0 and random.random() > current_sample_rate:
                    return await func(*args, **kwargs)

                start_wall = time.time()
                start_cpu = time.process_time()
                start_mem = get_memory_usage()
                error_occurred = False
                exception_type = None
                exception_message = None
                yield_count = 0

                profiler = None
                if profile_threshold_ms > 0:
                    import cProfile

                    profiler = cProfile.Profile()
                    profiler.enable()

                token = None
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
                    if profiler:
                        profiler.disable()

                    if token is not None:
                        try:
                            final_ctx = _current_trace_context.get()
                            if final_ctx:
                                yield_count = final_ctx.yield_count
                        finally:
                            _current_trace_context.reset(token)

                    should_record = True
                    if error_occurred:
                        current_sample_rate = GLOBAL_CONFIG.error_sample_rate
                        # Check if still sampled out after adjustment
                        if random.random() > current_sample_rate:
                            should_record = False

                    current_metadata = get_tags()

                    if should_record and profiler:
                        duration_ms = (time.time() - start_wall) * 1000
                        if duration_ms > profile_threshold_ms:
                            import io
                            import pstats

                            s = io.StringIO()
                            # Sort by cumulative time to see bottlenecks
                            ps = pstats.Stats(profiler, stream=s).sort_stats("cumulative")
                            ps.print_stats(20)
                            current_metadata = current_metadata.copy()
                            current_metadata["profile_stats"] = s.getvalue()

                    if should_record:
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
                            metadata=current_metadata,
                        )

            return wrapper

        else:

            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                _trace_name = name or func.__name__
                _module_name = module_name or getattr(func, "__module__", "unknown")

                current_sample_rate = _get_effective_sample_rate(False, _trace_name, _module_name)

                if current_sample_rate < 1.0 and random.random() > current_sample_rate:
                    return func(*args, **kwargs)

                start_wall = time.time()
                start_cpu = time.process_time()
                start_mem = get_memory_usage()
                error_occurred = False
                exception_type = None
                exception_message = None

                profiler = None
                if profile_threshold_ms > 0:
                    import cProfile

                    profiler = cProfile.Profile()
                    profiler.enable()

                try:
                    result = func(*args, **kwargs)
                    return result
                except Exception as e:
                    error_occurred = True
                    exception_type = type(e).__name__
                    exception_message = str(e)
                    raise e
                finally:
                    if profiler:
                        profiler.disable()

                    should_record = True
                    if error_occurred:
                        current_sample_rate = GLOBAL_CONFIG.error_sample_rate
                        # Check if still sampled out after adjustment
                        if random.random() > current_sample_rate:
                            should_record = False

                    current_metadata = get_tags()

                    if should_record and profiler:
                        duration_ms = (time.time() - start_wall) * 1000
                        if duration_ms > profile_threshold_ms:
                            import io
                            import pstats

                            s = io.StringIO()
                            ps = pstats.Stats(profiler, stream=s).sort_stats("cumulative")
                            ps.print_stats(20)
                            current_metadata = current_metadata.copy()
                            current_metadata["profile_stats"] = s.getvalue()

                    if should_record:
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
                            metadata=current_metadata,
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
        self._should_sample = True

    def __enter__(self):
        _trace_name = self.name
        _module_name = self.module_name

        current_sample_rate = _get_effective_sample_rate(False, _trace_name, _module_name)

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

        if error_occurred:
            current_sample_rate = GLOBAL_CONFIG.error_sample_rate
            if random.random() > current_sample_rate:
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
            metadata=get_tags(),
        )
