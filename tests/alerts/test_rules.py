import pytest
from pypss.alerts.rules import (
    MetricStabilityRule,
    TimingStabilitySurgeRule,
    MemoryStabilitySpikeRule,
    ErrorBurstRule,
    EntropyAnomalyRule,
    ConcurrencySpikeRule,
    StabilityRegressionRule,
)
from pypss.alerts.base import Alert, AlertSeverity
from pypss.utils.config import GLOBAL_CONFIG


@pytest.fixture(autouse=True)
def mock_config_for_rules():
    old_ts = GLOBAL_CONFIG.alert_threshold_ts
    old_ms = GLOBAL_CONFIG.alert_threshold_ms
    old_ev = GLOBAL_CONFIG.alert_threshold_ev
    old_be = GLOBAL_CONFIG.alert_threshold_be
    old_cc = GLOBAL_CONFIG.alert_threshold_cc
    old_reg_limit = GLOBAL_CONFIG.regression_history_limit
    old_reg_drop = GLOBAL_CONFIG.regression_threshold_drop

    # Set default thresholds for testing
    GLOBAL_CONFIG.alert_threshold_ts = 0.7
    GLOBAL_CONFIG.alert_threshold_ms = 0.7
    GLOBAL_CONFIG.alert_threshold_ev = 0.7
    GLOBAL_CONFIG.alert_threshold_be = 0.7
    GLOBAL_CONFIG.alert_threshold_cc = 0.7
    GLOBAL_CONFIG.regression_history_limit = 5
    GLOBAL_CONFIG.regression_threshold_drop = 10.0
    yield
    GLOBAL_CONFIG.alert_threshold_ts = old_ts
    GLOBAL_CONFIG.alert_threshold_ms = old_ms
    GLOBAL_CONFIG.alert_threshold_ev = old_ev
    GLOBAL_CONFIG.alert_threshold_be = old_be
    GLOBAL_CONFIG.alert_threshold_cc = old_cc
    GLOBAL_CONFIG.regression_history_limit = old_reg_limit
    GLOBAL_CONFIG.regression_threshold_drop = old_reg_drop


def create_mock_report(pss=100, ts=1.0, ms=1.0, ev=1.0, be=1.0, cc=1.0):
    return {
        "pss": pss,
        "breakdown": {
            "timing_stability": ts,
            "memory_stability": ms,
            "error_volatility": ev,
            "branching_entropy": be,
            "concurrency_chaos": cc,
        },
    }


# MetricStabilityRule base tests
def test_metric_stability_rule_not_enabled():
    rule = MetricStabilityRule(
        "Test Rule",
        "pss",
        "alert_threshold_ts",
        severity=AlertSeverity.WARNING,
        enabled=False,
    )
    report = create_mock_report()
    assert rule.evaluate(report) is None


def test_metric_stability_rule_no_trigger():
    rule = MetricStabilityRule("Test Rule", "timing_stability", "alert_threshold_ts")
    report = create_mock_report(ts=0.8)  # Above threshold 0.7
    assert rule.evaluate(report) is None


def test_metric_stability_rule_trigger():
    rule = MetricStabilityRule("Test Rule", "timing_stability", "alert_threshold_ts")
    report = create_mock_report(ts=0.6)  # Below threshold 0.7
    alert = rule.evaluate(report)
    assert isinstance(alert, Alert)
    assert alert.rule_name == "Test Rule"
    assert alert.current_value == 0.6
    assert alert.threshold == 0.7


def test_metric_stability_rule_trigger_pss():
    rule = MetricStabilityRule(
        "Test Rule PSS", "pss", "alert_threshold_ts"
    )  # Using TS threshold for PSS
    GLOBAL_CONFIG.alert_threshold_ts = 70.0  # Set PSS threshold for this test
    report = create_mock_report(pss=65)  # Below 70
    alert = rule.evaluate(report)
    assert isinstance(alert, Alert)
    assert alert.current_value == 0.65  # PSS is normalized
    assert alert.threshold == 70.0  # Fixed assertion


# Specific Metric Rules (just ensure they instantiate and call base correctly)
def test_timing_stability_surge_rule():
    rule = TimingStabilitySurgeRule()
    assert rule.name == "Timing Stability Surge"
    assert rule.metric_key == "timing_stability"


def test_memory_stability_spike_rule():
    rule = MemoryStabilitySpikeRule()
    assert rule.name == "Memory Stability Spike"
    assert rule.metric_key == "memory_stability"


def test_error_burst_rule():
    rule = ErrorBurstRule()
    assert rule.name == "Error Burst"
    assert rule.metric_key == "error_volatility"
    assert rule.severity == AlertSeverity.CRITICAL


def test_entropy_anomaly_rule():
    rule = EntropyAnomalyRule()
    assert rule.name == "Entropy Anomaly"
    assert rule.metric_key == "branching_entropy"


def test_concurrency_spike_rule():
    rule = ConcurrencySpikeRule()
    assert rule.name == "Concurrency Variance Spike"
    assert rule.metric_key == "concurrency_chaos"


# StabilityRegressionRule tests
def test_regression_rule_not_enabled():
    rule = StabilityRegressionRule(enabled=False)
    report = create_mock_report()
    history = [create_mock_report(pss=90)]
    assert rule.evaluate(report, history) is None


def test_regression_rule_no_history():
    rule = StabilityRegressionRule()
    report = create_mock_report()
    assert rule.evaluate(report, history=[]) is None


def test_regression_rule_stable_history():
    rule = StabilityRegressionRule()
    history = [create_mock_report(pss=95), create_mock_report(pss=90)]  # Avg 92.5
    report = create_mock_report(pss=85)  # Drop of 7.5, not enough for threshold 10
    assert rule.evaluate(report, history=history) is None


def test_regression_rule_detected():
    rule = StabilityRegressionRule()
    history = [create_mock_report(pss=95), create_mock_report(pss=90)]  # Avg 92.5
    report = create_mock_report(pss=80)  # Drop of 12.5, triggers (92.5 - 10 = 82.5)
    alert = rule.evaluate(report, history=history)
    assert isinstance(alert, Alert)
    assert alert.rule_name == "Stability Regression"
    assert alert.severity == AlertSeverity.CRITICAL
    assert "significantly lower than average 92.5" in alert.message
    assert alert.current_value == 80.0
    assert alert.threshold == 82.5


def test_regression_rule_history_too_short():
    rule = StabilityRegressionRule()
    history = [
        create_mock_report(pss=95)
    ]  # Only 1 run, but it's enough to calculate average.
    report = create_mock_report(
        pss=80
    )  # Triggers regression: 80 < (95 - 10) => 80 < 85
    alert = rule.evaluate(report, history=history)
    assert isinstance(alert, Alert)
    assert alert.rule_name == "Stability Regression"
    assert alert.current_value == 80.0
    assert alert.threshold == 85.0
