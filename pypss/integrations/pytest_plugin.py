import time
import pytest
from ..instrumentation import get_memory_usage, global_collector
from ..core import compute_pss_from_traces
from ..utils.config import GLOBAL_CONFIG


def pytest_addoption(parser):
    group = parser.getgroup("pypss")
    group.addoption(
        "--pss",
        action="store_true",
        help="Enable PyPSS stability monitoring for tests.",
    )
    group.addoption(
        "--pss-fail-below",
        action="store",
        type=int,
        default=0,
        help="Fail tests if their PSS score is below this threshold.",
    )


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_call(item):
    if not item.config.getoption("--pss"):
        yield
        return

    start_wall = time.time()
    start_cpu = time.process_time()
    start_mem = get_memory_usage()

    outcome = yield

    end_wall = time.time()
    end_cpu = time.process_time()
    end_mem = get_memory_usage()

    duration_wall = end_wall - start_wall
    duration_cpu = end_cpu - start_cpu
    wait_time = max(0.0, duration_wall - duration_cpu)

    # Determine error status from pytest outcome
    error = False
    try:
        outcome.get_result()
    except Exception:
        error = True

    trace = {
        "name": f"{GLOBAL_CONFIG.integration_pytest_trace_prefix}{item.nodeid}",
        "duration": duration_wall,
        "cpu_time": duration_cpu,
        "wait_time": wait_time,
        "memory": end_mem,
        "memory_diff": end_mem - start_mem,
        "error": error,
        "timestamp": start_wall,
    }

    # We can't easily compute PSS for a *single* run of a test (no variance),
    # but we can track it.
    # If the user runs `pytest --count=10`, we could aggregate.
    # For now, we just collect.
    global_collector.add_trace(trace)


def pytest_sessionfinish(session, exitstatus):
    if not session.config.getoption("--pss"):
        return

    traces = global_collector.get_traces()
    if not traces:
        return

    report = compute_pss_from_traces(traces)
    print("\n" + "=" * 20 + " PyPSS Stability Report " + "=" * 20)
    print(f"Overall Stability Score: {report['pss']}/100")

    threshold = session.config.getoption("--pss-fail-below")
    if threshold > 0 and report["pss"] < threshold:
        print(f"❌ FAILURE: PSS {report['pss']} is below threshold {threshold}")
        session.exitstatus = 1
