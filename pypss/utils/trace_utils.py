import time
import psutil
import os
import random
from typing import Dict, Any, Optional

from pypss.instrumentation.collectors import global_collector

# Memoize the process handle
_process = psutil.Process(os.getpid())


def get_memory_usage():
    """Returns RSS memory usage in bytes."""
    return _process.memory_info().rss


def finalize_trace(
    func: Optional[Any],  # func can be None for block monitoring
    name: str,
    branch_tag: Optional[str],
    module_name: str,
    start_wall: float,
    start_cpu: float,
    start_mem: int,
    error_occurred: bool,
    exception_type: Optional[str],
    exception_message: Optional[str],
    is_async: bool = False,
    yield_count: int = 0,
    metadata: Optional[Dict[str, Any]] = None,  # NEW PARAMETER
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
    filename = getattr(func.__code__, "co_filename", "unknown") if func else "unknown"
    lineno = getattr(func.__code__, "co_firstlineno", 0) if func else 0

    trace = {
        "trace_id": f"{start_wall}-{random.randint(0, 1_000_000)}",
        "name": name,
        "filename": filename,
        "lineno": lineno,
        "module": module_name,
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

    if metadata:  # NEW: Merge metadata into trace
        trace.update(metadata)

    global_collector.add_trace(trace)
