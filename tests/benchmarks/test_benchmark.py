import timeit

import pypss
from pypss.instrumentation import monitor_function
from pypss.utils import GLOBAL_CONFIG


def workload():
    """A minimal workload to measure pure overhead."""
    pass


@monitor_function("bench_op")
def instrumented_workload():
    pass


def run_benchmark(iterations=100_000):
    print(f"🚀 Running Benchmark: {iterations:,} iterations")
    print("=" * 60)

    pypss.init()  # Initialize pypss
    collector = pypss.get_global_collector()  # Get the global collector

    # 1. Baseline
    t0 = timeit.timeit(workload, number=iterations)
    baseline_ops = iterations / t0
    print(f"Baseline (No Instr):  {t0:.4f}s | {baseline_ops:,.0f} ops/sec | 0.00 µs/op")

    # 2. Instrumented (100% Sampling)
    collector.clear()
    GLOBAL_CONFIG.sample_rate = 1.0
    t1 = timeit.timeit(instrumented_workload, number=iterations)
    instr_ops = iterations / t1
    overhead_s = (t1 - t0) / iterations
    overhead_us = overhead_s * 1e6
    print(
        f"Instrumented (100%):  {t1:.4f}s | {instr_ops:,.0f} ops/sec | {overhead_us:.2f} µs/op overhead"
    )

    # 3. Instrumented (1% Sampling)
    collector.clear()
    GLOBAL_CONFIG.sample_rate = 0.01
    t2 = timeit.timeit(instrumented_workload, number=iterations)
    sampled_ops = iterations / t2
    overhead_sampled_s = (t2 - t0) / iterations
    overhead_sampled_us = overhead_sampled_s * 1e6
    print(
        f"Instrumented (1%):    {t2:.4f}s | {sampled_ops:,.0f} ops/sec | {overhead_sampled_us:.2f} µs/op overhead"
    )

    print("=" * 60)
    print(f"Instrumentation Factor: {t1 / t0:.1f}x slower than empty function")
    if t1 / t0 > 100:
        print(
            "⚠️  High overhead detected! (Typical for empty functions, less relevant for real I/O)"
        )

    # Check collector size (should be capped by ring buffer)
    traces = len(collector.get_traces())
    print(
        f"Collector Trace Count: {traces} (Ring Buffer Size: {GLOBAL_CONFIG.max_traces})"
    )


if __name__ == "__main__":
    run_benchmark()
