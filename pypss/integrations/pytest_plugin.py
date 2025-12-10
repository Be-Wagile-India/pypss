import glob
import json
import os
import shutil
import time

import pytest

import pypss

from ..core import compute_pss_from_traces
from ..utils.config import GLOBAL_CONFIG
from ..utils.trace_utils import get_memory_usage

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

    pypss.init()
    collector = pypss.get_global_collector()
    if collector:
        collector.clear()

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

    collector = pypss.get_global_collector()
    if collector:
        collector.add_trace(trace)


def pytest_sessionfinish(session, exitstatus):
    if not session.config.getoption("--pss"):
        return

    collector = pypss.get_global_collector()
    if collector:
        traces = collector.get_traces()
        if traces:
            pid = os.getpid()
            dump_file = os.path.join(TEMP_TRACE_DIR, f"traces_{pid}.json")
            try:
                with open(dump_file, "w") as f:
                    json.dump(traces, f)
            except Exception:
                pass

    if is_worker(session):
        return

    all_traces = []
    trace_files = glob.glob(os.path.join(TEMP_TRACE_DIR, "*.json"))

    for tf in trace_files:
        try:
            with open(tf, "r") as f:
                worker_traces = json.load(f)
                all_traces.extend(worker_traces)
        except Exception:
            pass

    if not all_traces:
        if os.path.exists(TEMP_TRACE_DIR):
            shutil.rmtree(TEMP_TRACE_DIR, ignore_errors=True)
        return

    from collections import defaultdict

    grouped_traces = defaultdict(list)
    for trace in all_traces:
        grouped_traces[trace["name"]].append(trace)

    threshold = session.config.getoption("--pss-fail-below")
    failed_tests = []

    print("\n" + "=" * 30 + " PyPSS Stability Report " + "=" * 30)

    header = f"{'Test Node ID':<50} | {'Runs':<4} | {'PSS':<5} | {'Status'}"
    print(header)
    print("-" * len(header))

    for nodeid, test_traces in grouped_traces.items():
        num_runs = len(test_traces)

        display_name = nodeid.replace(GLOBAL_CONFIG.integration_pytest_trace_prefix, "")
        display_name_truncated = display_name
        if len(display_name_truncated) > 47:
            display_name_truncated = "..." + display_name_truncated[-44:]

        if num_runs < 2:
            print(f"{display_name_truncated:<50} | {num_runs:<4} | {'N/A':<5} | ⚠️  Need >1 run for PSS")
            continue

        try:
            report = compute_pss_from_traces(test_traces)
            pss_score = report["pss"]
            display_score = int(pss_score)
        except Exception as e:
            print(f"{display_name_truncated:<50} | {num_runs:<4} | {'ERR':<5} | ❌ Calc Error: {e}")
            continue

        status = "✅ Stable"
        if threshold > 0 and pss_score < threshold:
            status = "❌ Unstable"
            failed_tests.append(f"{display_name} (PSS: {display_score})")

        print(f"{display_name_truncated:<50} | {num_runs:<4} | {display_score:<5} | {status}")

    print("=" * len(header))

    if os.path.exists(TEMP_TRACE_DIR):
        shutil.rmtree(TEMP_TRACE_DIR, ignore_errors=True)

    if failed_tests:
        print(f"\n❌ FAILURE: The following tests fell below the PSS threshold of {threshold}:")
        for ft in failed_tests:
            print(f"  - {ft}")
        session.exitstatus = 1
    elif threshold > 0:
        print(f"\n✅ SUCCESS: All calculable tests passed PSS threshold {threshold}.")
