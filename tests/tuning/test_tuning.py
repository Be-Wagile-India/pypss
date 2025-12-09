import pytest
import math
from pypss.tuning.profiler import Profiler
from pypss.tuning.injector import FaultInjector
from pypss.tuning.optimizer import ConfigOptimizer


@pytest.fixture
def baseline_traces():
    traces = []
    # Create 100 stable traces
    for i in range(100):
        traces.append(
            {
                "trace_id": f"t-{i}",
                "duration": 0.05,  # 50ms (stable)
                "memory": 1024 * 1024 * 10,  # 10MB
                "memory_diff": 0,
                "error": False,
                "wait_time": 0.0001,
                "timestamp": 1000 + i,
            }
        )
    return traces


def test_profiler(baseline_traces):
    profiler = Profiler(baseline_traces)
    profile = profiler.profile()

    assert profile.total_traces == 100
    assert math.isclose(profile.latency_mean, 0.05)
    assert math.isclose(profile.latency_p95, 0.05)
    assert profile.error_rate == 0.0
    assert profile.memory_mean == 1024 * 1024 * 10


def test_injector_latency(baseline_traces):
    injector = FaultInjector(baseline_traces)
    # Inject jitter with 100% probability for testing
    faulty = injector.inject_latency_jitter(magnitude=2.0, probability=1.0)

    assert len(faulty) == 100
    # Original duration 0.05. Max jitter 2.0x -> 0.10.
    # Check that at least one is > 0.05
    assert any(t["duration"] > 0.05 for t in faulty)


def test_injector_error(baseline_traces):
    injector = FaultInjector(baseline_traces)
    faulty = injector.inject_error_burst(burst_size=10, burst_count=1)

    errors = [t for t in faulty if t["error"]]
    assert len(errors) == 10


def test_optimizer(baseline_traces):
    injector = FaultInjector(baseline_traces)

    faulty_map = {
        "latency": injector.inject_latency_jitter(magnitude=5.0, probability=1.0),
        "errors": injector.inject_error_burst(burst_size=20),
    }

    optimizer = ConfigOptimizer(baseline_traces, faulty_map)

    # Run a few iterations
    best_config, best_loss = optimizer.optimize(iterations=10)

    # Check that we got a valid config object
    assert best_config is not None
    assert isinstance(best_loss, float)

    # We can't strictly assert the loss value without knowing the starting point,
    # but we can check that it didn't crash and produced reasonable values.
    assert best_config.alpha >= 0.5
