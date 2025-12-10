import os
import random
import time
from typing import Any, Dict, Optional

import psutil

import pypss

_process = psutil.Process(os.getpid())


def get_memory_usage():
    """Returns RSS memory usage in bytes."""
    return _process.memory_info().rss


def finalize_trace(
    func: Optional[Any],
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
    metadata: Optional[Dict[str, Any]] = None,
):
    """Helper to calculate metrics and record the trace."""
    try:
        end_wall = time.time()
        end_cpu = time.process_time()
        end_mem = get_memory_usage()

        duration_wall = end_wall - start_wall
        duration_cpu = end_cpu - start_cpu

        if is_async:
            # For async functions, we assume tasks are primarily I/O bound.
            # We treat the entire duration as 'wait_time' (waiting for I/O or Event Loop).
            duration_cpu = 0.0
            wait_time = duration_wall
        else:
            # If Wall Time > CPU Time, we were waiting (I/O, Locks, Sleep)
            wait_time = max(0.0, duration_wall - duration_cpu)

        code = getattr(func, "__code__", None)
        filename = getattr(code, "co_filename", "unknown") if code else "unknown"
        lineno = getattr(code, "co_firstlineno", 0) if code else 0

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

        if metadata:
            trace.update(metadata)

        pypss.get_global_collector().add_trace(trace)
    except Exception:
        pass
