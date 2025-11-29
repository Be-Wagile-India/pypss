import pytest
import math

from pypss.core.core import (
    _calculate_timing_stability_score,
    _calculate_memory_stability_score,
    _calculate_error_volatility_score,
    _calculate_branching_entropy_score,
    _calculate_concurrency_chaos_score,
)
from pypss.utils.config import PSSConfig


# Mock configuration for consistent testing
@pytest.fixture
def mock_config():
    config = PSSConfig()
    config.alpha = 2.0
    config.beta = 1.0
    config.gamma = 2.0
    config.delta = 1.0
    config.mem_spike_threshold_ratio = 1.5
    config.error_spike_threshold = 0.1
    config.consecutive_error_threshold = 3
    config.concurrency_wait_threshold = 0.001
    return config


class TestScoringAlgorithms:
    # Test cases for _calculate_timing_stability_score
    def test_timing_stability_empty_latencies(self, mock_config):
        assert _calculate_timing_stability_score([], mock_config) == 1.0

    def test_timing_stability_single_latency(self, mock_config):
        assert _calculate_timing_stability_score([0.5], mock_config) == 1.0

    def test_timing_stability_perfect_stability(self, mock_config):
        latencies = [0.1, 0.1, 0.1, 0.1, 0.1]
        score = _calculate_timing_stability_score(latencies, mock_config)
        assert math.isclose(score, 1.0)

    def test_timing_stability_high_variance(self, mock_config):
        latencies = [0.1, 0.1, 0.1, 10.0, 0.1]
        score = _calculate_timing_stability_score(latencies, mock_config)
        assert score < 1.0
        assert score < 0.5  # Should be significantly penalized

    def test_timing_stability_tail_latency_impact(self, mock_config):
        latencies = [0.1] * 9 + [1.0]  # 90% at 0.1, 10% at 1.0
        score = _calculate_timing_stability_score(latencies, mock_config)
        assert score < 1.0
        # More specific assertion can be added if a precise range is known

    # Test cases for _calculate_memory_stability_score
    def test_memory_stability_empty_samples(self, mock_config):
        assert _calculate_memory_stability_score([], mock_config) == 1.0

    def test_memory_stability_single_sample(self, mock_config):
        assert _calculate_memory_stability_score([100.0], mock_config) == 1.0

    def test_memory_stability_perfect_stability(self, mock_config):
        samples = [100.0, 100.0, 100.0]
        score = _calculate_memory_stability_score(samples, mock_config)
        assert math.isclose(score, 1.0)

    def test_memory_stability_zero_median_and_peak(self, mock_config):
        samples = [0.0, 0.0, 0.0]
        score = _calculate_memory_stability_score(samples, mock_config)
        assert math.isclose(score, 1.0)

    def test_memory_stability_zero_median_non_zero_peak(self, mock_config):
        samples = [0.0, 0.0, 100.0]
        score = _calculate_memory_stability_score(samples, mock_config)
        assert math.isclose(score, 0.0)  # Should be heavily penalized

    def test_memory_stability_with_spike_below_threshold(self, mock_config):
        # Peak / Median = 120 / 100 = 1.2, which is < 1.5 threshold
        samples = [100.0, 100.0, 120.0]
        score = _calculate_memory_stability_score(samples, mock_config)
        # Should be slightly lower than 1 due to std dev, but no spike penalty
        assert score < 1.0

    def test_memory_stability_with_spike_above_threshold(self, mock_config):
        # Peak / Median = 200 / 100 = 2.0, which is > 1.5 threshold
        samples = [100.0, 100.0, 200.0]
        score = _calculate_memory_stability_score(samples, mock_config)
        # Should be significantly lower due to spike penalty
        assert score < 0.5

    def test_memory_stability_high_variance(self, mock_config):
        samples = [100.0, 100.0, 200.0, 50.0]
        score = _calculate_memory_stability_score(samples, mock_config)
        assert score < 1.0

    # Test cases for _calculate_error_volatility_score
    def test_error_volatility_no_errors(self, mock_config):
        errors = [False, False, False, False]
        score = _calculate_error_volatility_score(errors, mock_config)
        assert math.isclose(score, 1.0)

    def test_error_volatility_all_errors(self, mock_config):
        errors = [True, True, True, True]
        score = _calculate_error_volatility_score(errors, mock_config)
        assert score < 1.0
        assert score < 0.5  # Should be heavily penalized

    def test_error_volatility_mixed_errors(self, mock_config):
        errors = [False, True, False, False, True]
        score = _calculate_error_volatility_score(errors, mock_config)
        assert score < 1.0

    def test_error_volatility_spike_below_threshold(self, mock_config):
        # Error rate = 1/10 = 0.1, which is not > conf.error_spike_threshold (0.1)
        errors = [False] * 9 + [True]
        score = _calculate_error_volatility_score(errors, mock_config)
        assert score < 1.0

    def test_error_volatility_spike_above_threshold(self, mock_config):
        # Error rate = 2/10 = 0.2, which is > conf.error_spike_threshold (0.1)
        errors = [False] * 8 + [True, True]
        score = _calculate_error_volatility_score(errors, mock_config)
        # Should be significantly penalized by spike
        assert score < 0.7

    def test_error_volatility_consecutive_errors_below_threshold(self, mock_config):
        # Max consecutive = 2, threshold = 3
        errors = [False, True, True, False, False]
        score = _calculate_error_volatility_score(errors, mock_config)
        assert score < 1.0

    def test_error_volatility_consecutive_errors_at_threshold(self, mock_config):
        # Max consecutive = 3, threshold = 3
        errors = [False, True, True, True, False]
        score = _calculate_error_volatility_score(errors, mock_config)
        assert score < 0.5  # Should be significantly penalized

    def test_error_volatility_consecutive_errors_above_threshold(self, mock_config):
        # Max consecutive = 4, threshold = 3
        errors = [False, True, True, True, True, False]
        score = _calculate_error_volatility_score(errors, mock_config)
        assert score < 0.3  # Even more significantly penalized

    # Test cases for _calculate_branching_entropy_score
    def test_branching_entropy_empty_tags(self):
        assert _calculate_branching_entropy_score([]) == 1.0

    def test_branching_entropy_single_tag(self):
        assert _calculate_branching_entropy_score(["main"]) == 1.0

    def test_branching_entropy_perfect_stability(self):
        tags = ["main"] * 10
        score = _calculate_branching_entropy_score(tags)
        assert math.isclose(score, 1.0)

    def test_branching_entropy_high_entropy(self):
        tags = ["branch_a", "branch_b", "branch_a", "branch_c"]
        score = _calculate_branching_entropy_score(tags)
        assert score < 1.0

    def test_branching_entropy_max_entropy(self):
        tags = ["a", "b", "c", "d"]
        score = _calculate_branching_entropy_score(tags)
        # With 4 unique branches, entropy will be high, score should be low
        assert score < 0.5

    # Test cases for _calculate_concurrency_chaos_score
    def test_concurrency_chaos_empty_wait_times(self, mock_config):
        assert _calculate_concurrency_chaos_score([], mock_config) == 1.0

    def test_concurrency_chaos_single_wait_time(self, mock_config):
        assert _calculate_concurrency_chaos_score([0.005], mock_config) == 1.0

    def test_concurrency_chaos_negligible_wait_times(self, mock_config):
        wait_times = [0.0001, 0.0002, 0.00005]  # All below threshold 0.001
        score = _calculate_concurrency_chaos_score(wait_times, mock_config)
        assert math.isclose(score, 1.0)

    def test_concurrency_chaos_constant_significant_wait_times(self, mock_config):
        wait_times = [0.01, 0.01, 0.01, 0.01]  # Above threshold, but no chaos
        score = _calculate_concurrency_chaos_score(wait_times, mock_config)
        assert math.isclose(score, 1.0)

    def test_concurrency_chaos_varying_significant_wait_times(self, mock_config):
        wait_times = [0.01, 0.05, 0.02, 0.1]  # Above threshold, with chaos
        score = _calculate_concurrency_chaos_score(wait_times, mock_config)
        assert score < 1.0
        assert score < 0.5  # Should be penalized
