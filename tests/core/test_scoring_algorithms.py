import math

import pytest

from pypss.core.core import (
    _calculate_branching_entropy_score,
    _calculate_concurrency_chaos_score,
    _calculate_error_volatility_score,
    _calculate_memory_stability_score,
    _calculate_timing_stability_score,
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
    @pytest.mark.parametrize(
        "latencies, expected_check, description",
        [
            ([], lambda s: s == 1.0, "Empty latencies"),
            ([0.5], lambda s: s == 1.0, "Single latency"),
            (
                [0.1, 0.1, 0.1, 0.1, 0.1],
                lambda s: math.isclose(s, 1.0),
                "Perfect stability",
            ),
            (
                [0.1, 0.1, 0.1, 10.0, 0.1],
                lambda s: s < 0.5,
                "High variance",
            ),
            (
                [0.1] * 9 + [1.0],
                lambda s: s < 1.0,
                "Tail latency impact",
            ),
        ],
    )
    def test_timing_stability(self, mock_config, latencies, expected_check, description):
        score = _calculate_timing_stability_score(latencies, mock_config)
        assert expected_check(score), f"Failed: {description}"

    @pytest.mark.parametrize(
        "samples, expected_check, description",
        [
            ([], lambda s: s == 1.0, "Empty samples"),
            ([100.0], lambda s: s == 1.0, "Single sample"),
            (
                [100.0, 100.0, 100.0],
                lambda s: math.isclose(s, 1.0),
                "Perfect stability",
            ),
            ([0.0, 0.0, 0.0], lambda s: math.isclose(s, 1.0), "Zero median and peak"),
            (
                [0.0, 0.0, 100.0],
                lambda s: math.isclose(s, 0.0),
                "Zero median non-zero peak",
            ),
            (
                [100.0, 100.0, 120.0],
                lambda s: s < 1.0,
                "Spike below threshold",
            ),
            (
                [100.0, 100.0, 200.0],
                lambda s: s < 0.5,
                "Spike above threshold",
            ),
            (
                [100.0, 100.0, 200.0, 50.0],
                lambda s: s < 1.0,
                "High variance",
            ),
        ],
    )
    def test_memory_stability(self, mock_config, samples, expected_check, description):
        score = _calculate_memory_stability_score(samples, mock_config)
        assert expected_check(score), f"Failed: {description}"

    @pytest.mark.parametrize(
        "errors, expected_check, description",
        [
            ([False, False, False, False], lambda s: math.isclose(s, 1.0), "No errors"),
            (
                [True, True, True, True],
                lambda s: s < 0.5,
                "All errors",
            ),
            (
                [False, True, False, False, True],
                lambda s: s < 1.0,
                "Mixed errors",
            ),
            (
                [False] * 9 + [True],
                lambda s: s < 1.0,
                "Spike below threshold",
            ),
            (
                [False] * 8 + [True, True],
                lambda s: s < 0.7,
                "Spike above threshold",
            ),
            (
                [False, True, True, False, False],
                lambda s: s < 1.0,
                "Consecutive errors below threshold",
            ),
            (
                [False, True, True, True, False],
                lambda s: s < 0.5,
                "Consecutive errors at threshold",
            ),
            (
                [False, True, True, True, True, False],
                lambda s: s < 0.3,
                "Consecutive errors above threshold",
            ),
        ],
    )
    def test_error_volatility(self, mock_config, errors, expected_check, description):
        score = _calculate_error_volatility_score(errors, mock_config)
        assert expected_check(score), f"Failed: {description}"

    @pytest.mark.parametrize(
        "tags, expected_check, description",
        [
            ([], lambda s: s == 1.0, "Empty tags"),
            (["main"], lambda s: s == 1.0, "Single tag"),
            (["main"] * 10, lambda s: math.isclose(s, 1.0), "Perfect stability"),
            (
                ["branch_a", "branch_b", "branch_a", "branch_c"],
                lambda s: s < 1.0,
                "High entropy",
            ),
            (
                ["a", "b", "c", "d"],
                lambda s: s < 0.5,
                "Max entropy",
            ),
        ],
    )
    def test_branching_entropy(self, tags, expected_check, description):
        score = _calculate_branching_entropy_score(tags)
        assert expected_check(score), f"Failed: {description}"

    @pytest.mark.parametrize(
        "wait_times, expected_check, description",
        [
            ([], lambda s: s == 1.0, "Empty wait times"),
            ([0.005], lambda s: s == 1.0, "Single wait time"),
            (
                [0.0001, 0.0002, 0.00005],
                lambda s: math.isclose(s, 1.0),
                "Negligible wait times",
            ),
            (
                [0.01, 0.01, 0.01, 0.01],
                lambda s: math.isclose(s, 1.0),
                "Constant significant wait times",
            ),
            (
                [0.01, 0.05, 0.02, 0.1],
                lambda s: s < 0.5,
                "Varying significant wait times",
            ),
        ],
    )
    def test_concurrency_chaos(self, mock_config, wait_times, expected_check, description):
        score = _calculate_concurrency_chaos_score(wait_times, mock_config)
        assert expected_check(score), f"Failed: {description}"
