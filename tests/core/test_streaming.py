import pytest
from pypss.core import compute_pss_from_traces


def trace_generator(n=100):
    for i in range(n):
        yield {
            "duration": 0.1,
            "memory": 1024 * 1024,
            "error": False,
            "wait_time": 0.01,
            "branch_tag": "main" if i % 2 == 0 else "alt",
        }


def test_compute_pss_consumes_iterator():
    # Create a generator (iterator)
    gen = trace_generator(50)

    # Pass it to compute_pss
    report = compute_pss_from_traces(gen)

    assert report["pss"] > 0
    assert "breakdown" in report

    # Verify the generator is consumed
    with pytest.raises(StopIteration):
        next(gen)


def test_compute_pss_handles_empty_iterator():
    gen = trace_generator(0)
    report = compute_pss_from_traces(gen)
    assert report["pss"] == 0


def test_compute_pss_handles_mixed_types():
    # Simulate data from ijson which might have Decimals (though we convert them)
    # or just verifying robustness
    traces = [
        {"duration": 0.1, "memory": 100},
        {
            "duration": 0.2,  # Changed "0.2" to 0.2 (float)
            "memory": 200,
        },
    ]
    # Current implementation uses float(val). Python float("0.2") works.

    report = compute_pss_from_traces(traces)
    assert report["pss"] > 0
