import click  # Add click import
import sys  # Add sys import

from ..tuning.profiler import Profiler
from ..tuning.injector import FaultInjector
from ..tuning.optimizer import ConfigOptimizer
from .utils import load_traces  # Import load_traces from utils


@click.command()
@click.option(
    "--baseline",
    type=click.Path(exists=True),
    required=True,
    help="Path to the baseline (healthy) JSON trace file.",
)
@click.option(
    "--output",
    type=click.Path(),
    default="pypss_tuned.toml",
    help="Path to save the optimized configuration.",
)
@click.option(
    "--iterations",
    type=int,
    default=50,
    help="Number of optimization iterations.",
)
def tune(baseline, output, iterations):
    """
    Auto-tune PyPSS configuration based on baseline traces.

    This command analyzes your 'healthy' traces, generates synthetic 'faulty' traces
    (latency spikes, memory leaks, error bursts), and finds the best parameters
    to maximize the score difference between them.
    """
    click.echo(f"📂 Loading baseline traces from {baseline}...")
    baseline_traces = load_traces(baseline)

    if not baseline_traces:
        click.echo("⚠️  No traces found in baseline file. Cannot tune.", err=True)
        sys.exit(1)

    click.echo(f"   Loaded {len(baseline_traces)} traces.")

    # 1. Profile Baseline
    click.echo("\n📊 Profiling Baseline...")
    profiler = Profiler(baseline_traces)
    profile = profiler.profile()

    click.echo(f"   Latency P95: {profile.latency_p95:.4f}s")
    click.echo(f"   Latency P99: {profile.latency_p99:.4f}s")
    click.echo(f"   Memory Mean: {profile.memory_mean / 1024 / 1024:.2f} MB")
    click.echo(f"   Error Rate:  {profile.error_rate * 100:.2f}%")

    if profile.error_rate > 0.05:
        click.echo("⚠️  Warning: Baseline has > 5% errors. Tuning might be inaccurate.")

    # 2. Generate Faults
    click.echo("\n🦠 Generating Synthetic Faults...")
    injector = FaultInjector(baseline_traces)

    faulty_map = {}

    # Latency Faults
    faulty_map["latency_jitter"] = injector.inject_latency_jitter(
        magnitude=3.0, probability=0.3
    )
    click.echo(
        f"   Generated {len(faulty_map['latency_jitter'])} traces with Latency Jitter (3x)."
    )

    # Memory Faults
    faulty_map["memory_leak"] = injector.inject_memory_leak(
        growth_rate=1024 * 50
    )  # 50KB per step
    click.echo(
        f"   Generated {len(faulty_map['memory_leak'])} traces with Memory Leaks."
    )

    # Error Faults
    faulty_map["error_burst"] = injector.inject_error_burst(burst_size=5, burst_count=3)
    click.echo(
        f"   Generated {len(faulty_map['error_burst'])} traces with Error Bursts."
    )

    # Thread Starvation
    faulty_map["thread_starvation"] = injector.inject_thread_starvation(lag_seconds=0.1)
    click.echo(
        f"   Generated {len(faulty_map['thread_starvation'])} traces with Thread Starvation."
    )

    # 3. Optimize
    click.echo(f"\n🧠 Optimizing Parameters ({iterations} iterations)...")
    optimizer = ConfigOptimizer(baseline_traces, faulty_map)

    best_config, best_loss = optimizer.optimize(iterations=iterations)

    click.echo("\n✅ Optimization Complete!")
    click.echo("   Best Parameters found:")
    click.echo(f"   - alpha (Timing CV sensitivity): {best_config.alpha:.2f}")
    click.echo(f"   - beta (Tail sensitivity):       {best_config.beta:.2f}")
    click.echo(f"   - gamma (Memory sensitivity):    {best_config.gamma:.2f}")
    click.echo(
        f"   - mem_spike_threshold_ratio:     {best_config.mem_spike_threshold_ratio:.2f}"
    )
    click.echo(
        f"   - concurrency_wait_threshold:    {best_config.concurrency_wait_threshold:.4f}"
    )

    # 4. Save
    click.echo(f"\n💾 Saving configuration to {output}...")
    best_config.save(output)
    click.echo("Done.")
