import time
import pytest
import os
import json
import shutil
import glob
from ..instrumentation import get_memory_usage, global_collector
from ..core import compute_pss_from_traces
from ..utils.config import GLOBAL_CONFIG

TEMP_TRACE_DIR = ".pypss_traces"


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


def is_worker(session):
    return hasattr(session.config, "workerinput")


@pytest.hookimpl(tryfirst=True)
def pytest_sessionstart(session):
    """Ensure we start with a clean slate."""
    if not session.config.getoption("--pss"):
        return

    global_collector.clear()

    # If Master (or single process), clean the temp dir
    if not is_worker(session):
        if os.path.exists(TEMP_TRACE_DIR):
            shutil.rmtree(TEMP_TRACE_DIR, ignore_errors=True)
        os.makedirs(TEMP_TRACE_DIR, exist_ok=True)


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

    # 1. Dump local traces to file (Worker OR Master)
    traces = global_collector.get_traces()
    if traces:
        # Use PID to avoid collision
        pid = os.getpid()
        dump_file = os.path.join(TEMP_TRACE_DIR, f"traces_{pid}.json")
        try:
            with open(dump_file, "w") as f:
                json.dump(traces, f)
        except Exception:
            # In rare race conditions or permission issues, just ignore
            pass

    # 2. If Worker, stop here.
    if is_worker(session):
        return

    # 3. If Master, aggregate and report
    all_traces = []
    # Wait briefly for file system sync if needed (usually not on local FS)
    trace_files = glob.glob(os.path.join(TEMP_TRACE_DIR, "*.json"))

    for tf in trace_files:
        try:
            with open(tf, "r") as f:
                worker_traces = json.load(f)
                all_traces.extend(worker_traces)
        except Exception:
            pass

    if not all_traces:
        # Clean up even if empty
        if os.path.exists(TEMP_TRACE_DIR):
            shutil.rmtree(TEMP_TRACE_DIR, ignore_errors=True)
        return

    # Group traces by test nodeid
    from collections import defaultdict

    grouped_traces = defaultdict(list)
    for trace in all_traces:
        grouped_traces[trace["name"]].append(trace)

    threshold = session.config.getoption("--pss-fail-below")
    failed_tests = []

    print("\n" + "=" * 30 + " PyPSS Stability Report " + "=" * 30)

    # Header for the manual table
    # ID | Runs | TS | MS | EV | PSS | Status
    header = f"{'Test Node ID':<50} | {'Runs':<4} | {'PSS':<5} | {'Status'}"
    print(header)
    print("-" * len(header))

    for nodeid, test_traces in grouped_traces.items():
        num_runs = len(test_traces)

        # Clean up the nodeid for display (remove prefix if present)
        display_name = nodeid.replace(GLOBAL_CONFIG.integration_pytest_trace_prefix, "")
        # Truncate if too long
        display_name_truncated = display_name
        if len(display_name_truncated) > 47:
            display_name_truncated = "..." + display_name_truncated[-44:]

        if num_runs < 2:
            print(
                f"{display_name_truncated:<50} | {num_runs:<4} | {'N/A':<5} | ⚠️  Need >1 run for PSS"
            )
            continue

        try:
            report = compute_pss_from_traces(test_traces)
            pss_score = report["pss"]
            # Ensure pss_score is treated as int for clean display if possible
            display_score = int(pss_score)
        except Exception as e:
            # Fallback if calculation fails (e.g. rare math errors)
            print(
                f"{display_name_truncated:<50} | {num_runs:<4} | {'ERR':<5} | ❌ Calc Error: {e}"
            )
            continue

        status = "✅ Stable"
        if threshold > 0 and pss_score < threshold:
            status = "❌ Unstable"
            failed_tests.append(f"{display_name} (PSS: {display_score})")

        print(
            f"{display_name_truncated:<50} | {num_runs:<4} | {display_score:<5} | {status}"
        )

    print("=" * len(header))

    # Cleanup at the very end
    if os.path.exists(TEMP_TRACE_DIR):
        shutil.rmtree(TEMP_TRACE_DIR, ignore_errors=True)

    if failed_tests:
        print(
            f"\n❌ FAILURE: The following tests fell below the PSS threshold of {threshold}:"
        )
        for ft in failed_tests:
            print(f"  - {ft}")
        session.exitstatus = 1
    elif threshold > 0:
        print(f"\n✅ SUCCESS: All calculable tests passed PSS threshold {threshold}.")
