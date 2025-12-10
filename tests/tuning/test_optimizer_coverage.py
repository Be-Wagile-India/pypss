import pytest  # noqa: F401
from skopt import gp_minimize  # noqa: F401

from pypss.tuning.optimizer import ConfigOptimizer
from pypss.utils.config import PSSConfig


class TestOptimizerCoverage:
    def test_compute_score_empty_traces(self):
        optimizer = ConfigOptimizer([], {})
        score, breakdown = optimizer._compute_score([], PSSConfig())
        assert score == 0.0
        assert breakdown["ts_score"] == 0.0

    def test_compute_score_system_metrics(self):
        optimizer = ConfigOptimizer([], {})
        traces = [
            {"system_metric": True, "metadata": {"lag": 0.1}},
            {"system_metric": True, "metadata": {"lag": 0.2}},
        ]
        # Need some wait times to trigger CC score calc properly?
        # _calculate_concurrency_chaos_score handles empty wait_times if system_metrics is present?
        # Let's add some dummy wait times too just in case
        traces.extend([{"wait_time": 0.0}, {"wait_time": 0.0}])

        score, breakdown = optimizer._compute_score(traces, PSSConfig())
        assert breakdown["cc_score"] > 0  # Should have some score
        assert breakdown["cc_score"] <= 1.0

    def test_calculate_loss_penalty(self):
        # Create a scenario where faulty trace has HIGH score (bad detection)
        # to trigger the penalty branch

        # Baseline: Perfect traces
        baseline = [{"duration": 0.1, "memory": 100, "wait_time": 0.0, "error": False}] * 10

        # Faulty: Also perfect traces (so score is high, detection fails)
        faulty = [{"duration": 0.1, "memory": 100, "wait_time": 0.0, "error": False}] * 10

        optimizer = ConfigOptimizer(baseline, {"latency_jitter": faulty})

        loss = optimizer.calculate_loss(PSSConfig())

        # Loss should be high because faulty traces have high score (detection failed)
        # We expect penalty
        assert loss > 0

    def test_optimize_short_run(self):
        optimizer = ConfigOptimizer([], {})
        # Run with very few iterations to cover the optimization loop
        # We need at least 1 iteration
        # Mock gp_minimize? Or just run it. It's using skopt.
        # skopt might be slow or not installed?
        # If installed, run it.

        # The 'try...except ImportError' is now only for the gp_minimize call.
        # This allows the import to happen at module level if skopt is installed.
        config, loss = optimizer.optimize(iterations=12)
        assert isinstance(config, PSSConfig)
