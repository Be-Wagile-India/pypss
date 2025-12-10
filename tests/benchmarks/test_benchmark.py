import time
import timeit

import pypss
from pypss.instrumentation import monitor_function
from pypss.utils import GLOBAL_CONFIG


def workload_empty():
    """A minimal workload to measure pure overhead."""
    pass


@monitor_function("bench_empty")
def instrumented_workload_empty():
    pass


def workload_io():
    """A realistic workload (1ms IO) to measure relative impact."""
    time.sleep(0.001)


@monitor_function("bench_io")
def instrumented_workload_io():
    time.sleep(0.001)


def run_benchmark():
    print("=" * 60)
    print("🚀 PyPSS Benchmark Suite")
    print("=" * 60)

    pypss.init()  # Initialize pypss
    collector = pypss.get_global_collector()

    # --- PART 1: Micro-Benchmark (Pure Overhead) ---
    iterations_micro = 100_000
    print(f"\n[1] Micro-Benchmark (Empty Function) - {iterations_micro:,} iterations")
    print("-" * 60)

    # 1. Baseline
    t0 = timeit.timeit(workload_empty, number=iterations_micro)
    baseline_ops = iterations_micro / t0
    print(f"Baseline (No Instr):  {t0:.4f}s | {baseline_ops:,.0f} ops/sec")

    # 2. Instrumented (100%)
    collector.clear()
    GLOBAL_CONFIG.sample_rate = 1.0
    t1 = timeit.timeit(instrumented_workload_empty, number=iterations_micro)
    instr_ops = iterations_micro / t1
    overhead_us = ((t1 - t0) / iterations_micro) * 1e6

    print(f"Instrumented (100%):  {t1:.4f}s | {instr_ops:,.0f} ops/sec | +{overhead_us:.2f} µs overhead")

    # 3. Instrumented (1%)
    collector.clear()
    GLOBAL_CONFIG.sample_rate = 0.01
    t2 = timeit.timeit(instrumented_workload_empty, number=iterations_micro)
    sampled_ops = iterations_micro / t2
    overhead_sampled_us = ((t2 - t0) / iterations_micro) * 1e6

    print(f"Instrumented (1%):    {t2:.4f}s | {sampled_ops:,.0f} ops/sec | +{overhead_sampled_us:.2f} µs overhead")

    # --- PART 2: Realistic Scenario (1ms I/O) ---
    iterations_io = 2_000
    print(f"\n[2] Realistic Scenario (1ms I/O Task) - {iterations_io:,} iterations")
    print("-" * 60)

    # 1. Baseline
    t0_io = timeit.timeit(workload_io, number=iterations_io)
    print(f"Baseline (1ms Sleep): {t0_io:.4f}s")

    # 2. Instrumented (100%)
    collector.clear()
    GLOBAL_CONFIG.sample_rate = 1.0
    t1_io = timeit.timeit(instrumented_workload_io, number=iterations_io)

    # Calculate percentage overhead
    # We subtract the raw overhead found in Part 1 to see if it matches,
    # but strictly we just compare t1_io vs t0_io
    overhead_pct = ((t1_io - t0_io) / t0_io) * 100

    print(f"Instrumented (100%):  {t1_io:.4f}s")
    print(f"👉 Relative Overhead: {overhead_pct:.2f}% (Target: < 3%)")

    if overhead_pct < 3.0:
        print("✅ PERFORMANCE PASSED: Overhead is negligible for real workloads.")
    else:
        print("⚠️  PERFORMANCE WARN: Overhead is slightly noticeable.")

    print("=" * 60)

    # Check collector
    traces = len(collector.get_traces())
    print(f"Collector Trace Count: {traces} (Ring Buffer Size: {GLOBAL_CONFIG.max_traces})")


if __name__ == "__main__":
    run_benchmark()
