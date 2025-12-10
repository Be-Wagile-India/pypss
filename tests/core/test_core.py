from pypss.core import compute_pss_from_traces


class TestCore:
    def test_compute_pss_empty(self):
        # Should handle empty traces gracefully
        report = compute_pss_from_traces([])
        assert report["pss"] == 0
        assert report["breakdown"]["timing_stability"] == 0

    def test_compute_pss_perfect_run(self):
        # 10 traces, exact same duration, no errors, same branch
        traces = [{"duration": 0.1, "memory": 1000, "error": False, "branch_tag": "main"} for _ in range(10)]

        report = compute_pss_from_traces(traces)

        # Perfect stability should be close to 100
        # Note: Depending on weights (which sum to 1.0), score should be 100.
        # TS: CV=0 -> score=1. Tail=1 -> score=1. Total TS=1.
        # MS: Std=0, Peak/Median=1 -> metric=0 -> score=1.
        # EV: errors=0 -> score=1.
        # BE: entropy=0 -> score=1.
        # CC: constant 1.

        assert report["pss"] == 100
        assert report["breakdown"]["timing_stability"] == 1.0
        assert report["breakdown"]["error_volatility"] == 1.0

    def test_compute_pss_with_errors(self):
        # 50% failure rate
        traces = []
        for i in range(10):
            traces.append(
                {
                    "duration": 0.1,
                    "memory": 1000,
                    "error": (i % 2 == 0),  # True, False, True...
                    "branch_tag": "main",
                }
            )

        report = compute_pss_from_traces(traces)

        # Error volatility score should be lower than 1.0
        ev = report["breakdown"]["error_volatility"]
        assert ev < 1.0
        # PSS should definitely not be 100
        assert report["pss"] < 100

    def test_compute_pss_high_variance(self):
        # Extreme timing jitter: 0.1 vs 10.0
        traces = [
            {"duration": 0.1, "memory": 1000, "error": False, "branch_tag": "main"},
            {"duration": 10.0, "memory": 1000, "error": False, "branch_tag": "main"},
        ]

        report = compute_pss_from_traces(traces)
        ts = report["breakdown"]["timing_stability"]

        # CV will be high, so TS should be low
        assert ts < 0.9
