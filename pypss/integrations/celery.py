import time

from celery.signals import task_postrun, task_prerun

import pypss

from ..utils.config import GLOBAL_CONFIG
from ..utils.trace_utils import get_memory_usage

_task_metrics = {}


def enable_celery_integration():
    """
    Connects pypss to Celery signals to automatically trace all tasks.
    """
    task_prerun.connect(_on_task_prerun)
    task_postrun.connect(_on_task_postrun)


def _on_task_prerun(sender=None, task_id=None, task=None, args=None, kwargs=None, **opts):
    _task_metrics[task_id] = {
        "start_wall": time.time(),
        "start_cpu": time.process_time(),
        "start_mem": get_memory_usage(),
    }


def _on_task_postrun(
    sender=None,
    task_id=None,
    task=None,
    args=None,
    kwargs=None,
    retval=None,
    state=None,
    **opts,
):
    metrics = _task_metrics.pop(task_id, None)
    if not metrics:
        return

    end_wall = time.time()
    end_cpu = time.process_time()
    end_mem = get_memory_usage()

    duration_wall = end_wall - metrics["start_wall"]
    duration_cpu = end_cpu - metrics["start_cpu"]
    wait_time = max(0.0, duration_wall - duration_cpu)

    error = state == "FAILURE"

    trace = {
        "name": f"{GLOBAL_CONFIG.integration_celery_trace_prefix}{task.name}",
        "duration": duration_wall,
        "cpu_time": duration_cpu,
        "wait_time": wait_time,
        "memory": end_mem,
        "memory_diff": end_mem - metrics["start_mem"],
        "error": error,
        "branch_tag": state,
        "timestamp": metrics["start_wall"],
    }

    collector = pypss.get_global_collector()
    if collector:
        collector.add_trace(trace)
