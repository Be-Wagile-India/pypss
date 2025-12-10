import time
from unittest import mock

import pytest

from pypss.core.adaptive_sampler import AdaptiveSampler
from pypss.utils.config import GLOBAL_CONFIG


@pytest.fixture
def mock_time_fixture():
    with mock.patch("time.time") as mock_time:
        mock_time.return_value = 1.0
        yield mock_time


@pytest.fixture(autouse=True)
def setup_teardown_global_config(monkeypatch, mock_time_fixture):
    """Fixture to reset GLOBAL_CONFIG before and after each test."""

    # Store original values from GLOBAL_CONFIG
    original_sample_rate = GLOBAL_CONFIG.sample_rate
    original_adaptive_sampler_min_interval = GLOBAL_CONFIG.adaptive_sampler_min_interval
    original_adaptive_sampler_lag_threshold = GLOBAL_CONFIG.adaptive_sampler_lag_threshold
    original_adaptive_sampler_churn_threshold = GLOBAL_CONFIG.adaptive_sampler_churn_threshold
    original_adaptive_sampler_error_threshold = GLOBAL_CONFIG.adaptive_sampler_error_threshold
    original_adaptive_sampler_increase_step = GLOBAL_CONFIG.adaptive_sampler_increase_step
    original_adaptive_sampler_decrease_step = GLOBAL_CONFIG.adaptive_sampler_decrease_step
    original_adaptive_sampler_max_rate = GLOBAL_CONFIG.adaptive_sampler_max_rate
    original_adaptive_sampler_min_rate = GLOBAL_CONFIG.adaptive_sampler_min_rate
    original_adaptive_sampler_mode = GLOBAL_CONFIG.adaptive_sampler_mode
    original_adaptive_sampler_high_qps_threshold = GLOBAL_CONFIG.adaptive_sampler_high_qps_threshold

    # Ensure GLOBAL_CONFIG defaults for testing are set *before* creating fresh_adaptive_sampler
    GLOBAL_CONFIG.sample_rate = 0.5
    GLOBAL_CONFIG.adaptive_sampler_min_interval = 0.1
    GLOBAL_CONFIG.adaptive_sampler_lag_threshold = 0.1
    GLOBAL_CONFIG.adaptive_sampler_churn_threshold = 10.0
    GLOBAL_CONFIG.adaptive_sampler_error_threshold = 0.1
    GLOBAL_CONFIG.adaptive_sampler_increase_step = 0.1
    GLOBAL_CONFIG.adaptive_sampler_decrease_step = 0.05
    GLOBAL_CONFIG.adaptive_sampler_max_rate = 1.0
    GLOBAL_CONFIG.adaptive_sampler_min_rate = 0.01
    GLOBAL_CONFIG.adaptive_sampler_mode = "balanced"
    GLOBAL_CONFIG.adaptive_sampler_high_qps_threshold = 100.0

    # Use monkeypatch to replace the global adaptive_sampler instance with a fresh one for each test
    fresh_adaptive_sampler = AdaptiveSampler()
    fresh_adaptive_sampler._last_adjustment_time = time.time()  # Use patched time.time from mock_time_fixture
    fresh_adaptive_sampler._last_trace_count_time = time.time()

    monkeypatch.setattr("pypss.core.adaptive_sampler.adaptive_sampler", fresh_adaptive_sampler)

    yield fresh_adaptive_sampler  # Yield the mocked adaptive_sampler instance

    # Restore original values
    GLOBAL_CONFIG.sample_rate = original_sample_rate
    GLOBAL_CONFIG.adaptive_sampler_min_interval = original_adaptive_sampler_min_interval
    GLOBAL_CONFIG.adaptive_sampler_lag_threshold = original_adaptive_sampler_lag_threshold
    GLOBAL_CONFIG.adaptive_sampler_churn_threshold = original_adaptive_sampler_churn_threshold
    GLOBAL_CONFIG.adaptive_sampler_error_threshold = original_adaptive_sampler_error_threshold
    GLOBAL_CONFIG.adaptive_sampler_increase_step = original_adaptive_sampler_increase_step
    GLOBAL_CONFIG.adaptive_sampler_decrease_step = original_adaptive_sampler_decrease_step
    GLOBAL_CONFIG.adaptive_sampler_max_rate = original_adaptive_sampler_max_rate
    GLOBAL_CONFIG.adaptive_sampler_min_rate = original_adaptive_sampler_min_rate
    GLOBAL_CONFIG.adaptive_sampler_mode = original_adaptive_sampler_mode
    GLOBAL_CONFIG.adaptive_sampler_high_qps_threshold = original_adaptive_sampler_high_qps_threshold


class TestAdaptiveSampler:
    def test_initialization(self):
        sampler = AdaptiveSampler()
        assert sampler._current_sample_rate == GLOBAL_CONFIG.sample_rate
        assert "lag" in sampler._last_metrics
        assert "churn_rate" in sampler._last_metrics
        assert "error_rate" in sampler._last_metrics
        assert "qps" in sampler._last_metrics

    def test_update_metrics_stores_metrics(self):
        sampler = AdaptiveSampler()
        sampler.update_metrics(lag=0.5, churn_rate=20.0, error_rate=0.2, custom_metric=100)
        assert sampler._last_metrics["lag"] == 0.5
        assert sampler._last_metrics["churn_rate"] == 20.0
        assert sampler._last_metrics["error_rate"] == 0.2
        assert sampler._last_metrics["custom_metric"] == 100

    def test_qps_calculation(self, mock_time_fixture):
        sampler = AdaptiveSampler()
        sampler._last_trace_count_time = mock_time_fixture.return_value  # Current time 1.0

        # Advance time by 1 second
        mock_time_fixture.return_value += 1.0

        sampler.update_metrics(trace_count=100)
        assert sampler._last_metrics["qps"] == 100.0

    def test_adjust_sample_rate_increases_on_high_lag(self, mock_time_fixture):
        # mock_time_fixture.return_value is already 1.0 from the fixture itself.
        sampler = AdaptiveSampler()

        # Advance time to allow adjustment
        mock_time_fixture.return_value += GLOBAL_CONFIG.adaptive_sampler_min_interval + 0.1

        initial_rate = GLOBAL_CONFIG.sample_rate
        sampler.update_metrics(lag=GLOBAL_CONFIG.adaptive_sampler_lag_threshold + 0.1)

        expected_rate = min(
            GLOBAL_CONFIG.adaptive_sampler_max_rate,
            initial_rate + GLOBAL_CONFIG.adaptive_sampler_increase_step,
        )
        assert sampler._current_sample_rate == pytest.approx(expected_rate)
        assert GLOBAL_CONFIG.sample_rate == pytest.approx(expected_rate)

    def test_mode_high_load(self, mock_time_fixture):
        sampler = AdaptiveSampler()
        GLOBAL_CONFIG.adaptive_sampler_mode = "high_load"
        GLOBAL_CONFIG.adaptive_sampler_high_qps_threshold = 100.0

        mock_time_fixture.return_value += GLOBAL_CONFIG.adaptive_sampler_min_interval + 0.1

        # Simulate high QPS (via manual update for test, bypassing internal calc)
        sampler._last_metrics["qps"] = 200.0
        sampler._adjust_sample_rate()

        # Should drop to min rate
        assert sampler._current_sample_rate == GLOBAL_CONFIG.adaptive_sampler_min_rate

    def test_mode_error_triggered(self, mock_time_fixture):
        sampler = AdaptiveSampler()
        GLOBAL_CONFIG.adaptive_sampler_mode = "error_triggered"

        mock_time_fixture.return_value += GLOBAL_CONFIG.adaptive_sampler_min_interval + 0.1

        # High error rate
        sampler.update_metrics(error_rate=GLOBAL_CONFIG.adaptive_sampler_error_threshold + 0.1)

        # Should jump to max rate
        assert sampler._current_sample_rate == GLOBAL_CONFIG.adaptive_sampler_max_rate

    def test_mode_surge(self, mock_time_fixture):
        sampler = AdaptiveSampler()
        GLOBAL_CONFIG.adaptive_sampler_mode = "surge"

        mock_time_fixture.return_value += GLOBAL_CONFIG.adaptive_sampler_min_interval + 0.1

        # High lag
        sampler.update_metrics(lag=GLOBAL_CONFIG.adaptive_sampler_lag_threshold + 0.1)

        # Should jump to max rate
        assert sampler._current_sample_rate == GLOBAL_CONFIG.adaptive_sampler_max_rate

    def test_mode_low_noise(self, mock_time_fixture):
        sampler = AdaptiveSampler()
        GLOBAL_CONFIG.adaptive_sampler_mode = "low_noise"
        current_rate = sampler._current_sample_rate

        mock_time_fixture.return_value += GLOBAL_CONFIG.adaptive_sampler_min_interval + 0.1

        # Very stable metrics
        sampler.update_metrics(
            lag=GLOBAL_CONFIG.adaptive_sampler_lag_threshold / 4,
            churn_rate=GLOBAL_CONFIG.adaptive_sampler_churn_threshold / 4,
            error_rate=GLOBAL_CONFIG.adaptive_sampler_error_threshold / 4,
        )

        # Should decrease
        expected_rate = max(
            GLOBAL_CONFIG.adaptive_sampler_min_rate,
            current_rate - GLOBAL_CONFIG.adaptive_sampler_decrease_step,
        )
        assert sampler._current_sample_rate == pytest.approx(expected_rate)

    def test_adjust_sample_rate_decreases_on_low_metrics(self, mock_time_fixture):
        # mock_time_fixture.return_value is already 1.0
        sampler = AdaptiveSampler()

        initial_rate_before_increase = sampler._current_sample_rate  # Capture initial rate before increase

        # Advance time to allow adjustment and trigger increase
        mock_time_fixture.return_value += GLOBAL_CONFIG.adaptive_sampler_min_interval + 0.1
        sampler.update_metrics(lag=GLOBAL_CONFIG.adaptive_sampler_lag_threshold + 0.1)

        increased_rate = sampler._current_sample_rate
        assert increased_rate == pytest.approx(
            min(
                GLOBAL_CONFIG.adaptive_sampler_max_rate,
                initial_rate_before_increase + GLOBAL_CONFIG.adaptive_sampler_increase_step,
            )
        )
        assert GLOBAL_CONFIG.sample_rate == pytest.approx(increased_rate)  # Ensure global config updated

        # Advance time to allow next adjustment and trigger decrease
        mock_time_fixture.return_value += GLOBAL_CONFIG.adaptive_sampler_min_interval + 0.1

        sampler.update_metrics(
            lag=GLOBAL_CONFIG.adaptive_sampler_lag_threshold / 4,
            churn_rate=GLOBAL_CONFIG.adaptive_sampler_churn_threshold / 4,
            error_rate=GLOBAL_CONFIG.adaptive_sampler_error_threshold / 4,
        )

        expected_rate_after_decrease = max(
            GLOBAL_CONFIG.adaptive_sampler_min_rate,
            increased_rate - GLOBAL_CONFIG.adaptive_sampler_decrease_step,
        )
        assert sampler._current_sample_rate == pytest.approx(expected_rate_after_decrease)
        assert GLOBAL_CONFIG.sample_rate == pytest.approx(expected_rate_after_decrease)

    def test_adjust_sample_rate_no_change_partial_low_metrics(self, mock_time_fixture):
        # mock_time_fixture.return_value is already 1.0
        sampler = AdaptiveSampler()
        # initial_rate_before_increase is not used, removed to fix F841

        # Advance time to allow adjustment and trigger increase (to allow for subsequent no-change)
        mock_time_fixture.return_value += GLOBAL_CONFIG.adaptive_sampler_min_interval + 0.1
        sampler.update_metrics(lag=GLOBAL_CONFIG.adaptive_sampler_lag_threshold + 0.1)

        increased_rate = sampler._current_sample_rate

        # Advance time for next adjustment
        mock_time_fixture.return_value += GLOBAL_CONFIG.adaptive_sampler_min_interval + 0.1

        # Set some metrics low, but not all three, and ensure no increase condition is met
        sampler.update_metrics(
            lag=GLOBAL_CONFIG.adaptive_sampler_lag_threshold / 4,  # Low, contribute to decrease_score
            churn_rate=GLOBAL_CONFIG.adaptive_sampler_churn_threshold
            / 1.5,  # Normal, does not trigger increase or decrease
            error_rate=GLOBAL_CONFIG.adaptive_sampler_error_threshold / 4,  # Low, contribute to decrease_score
        )

        # Expect no change because decrease_score is not 3
        assert sampler._current_sample_rate == pytest.approx(increased_rate)
        assert GLOBAL_CONFIG.sample_rate == pytest.approx(increased_rate)

    def test_global_adaptive_sampler_instance(self, mock_time_fixture, setup_teardown_global_config):  # Accept fixture
        # mock_time_fixture.return_value is already 1.0
        # The fixture 'setup_teardown_global_config' yields the monkeypatched adaptive_sampler instance.
        # We can use it directly from the fixture argument.
        test_sampler = setup_teardown_global_config

        # Ensure the global instance is working
        initial_rate = GLOBAL_CONFIG.sample_rate  # This GLOBAL_CONFIG is also managed by the fixture

        mock_time_fixture.return_value += GLOBAL_CONFIG.adaptive_sampler_min_interval + 0.1
        test_sampler.update_metrics(lag=GLOBAL_CONFIG.adaptive_sampler_lag_threshold + 0.1)

        expected_rate = min(
            GLOBAL_CONFIG.adaptive_sampler_max_rate,
            initial_rate + GLOBAL_CONFIG.adaptive_sampler_increase_step,
        )
        assert test_sampler._current_sample_rate == pytest.approx(expected_rate)
        assert GLOBAL_CONFIG.sample_rate == pytest.approx(expected_rate)
