from __future__ import annotations
import time
from rq.job import Job
import pypss
from ..utils.trace_utils import get_memory_usage
from ..utils.config import GLOBAL_CONFIG


class PSSJob(Job):
    """
    RQ Job subclass that traces execution stability.

    Usage::

        from pypss.integrations.rq import PSSJob
        # When enqueueing:
        q.enqueue(func, job_class=PSSJob)
        # Or configure worker to use it by default.
    """

    def perform(self):
        start_wall = time.time()
        start_cpu = time.process_time()
        start_mem = get_memory_usage()

        error = False
        try:
            return super().perform()
        except Exception:
            error = True
            raise
        finally:
            end_wall = time.time()
            end_cpu = time.process_time()
            end_mem = get_memory_usage()

            duration_wall = end_wall - start_wall
            duration_cpu = end_cpu - start_cpu
            wait_time = max(0.0, duration_wall - duration_cpu)

            trace = {
                "name": f"{GLOBAL_CONFIG.integration_rq_trace_prefix}{self.func_name}",
                "duration": duration_wall,
                "cpu_time": duration_cpu,
                "wait_time": wait_time,
                "memory": end_mem,
                "memory_diff": end_mem - start_mem,
                "error": error,
                "timestamp": start_wall,
            }
            collector = pypss.get_global_collector()
            if collector:
                collector.add_trace(trace)
