import pytest

from pypss.alerts.base import Alert, AlertSeverity
from pypss.alerts.rules import (
    ConcurrencySpikeRule,
    EntropyAnomalyRule,
    ErrorBurstRule,
    MemoryStabilitySpikeRule,
    MetricStabilityRule,
    StabilityRegressionRule,
    TimingStabilitySurgeRule,
)
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


@pytest.mark.parametrize(
    "enabled, report_ts, expect_alert",
    [
        (False, 0.6, False),  # Disabled, no alert even if value < threshold
        (True, 0.8, False),  # Enabled, value > threshold (0.7), no alert
        (True, 0.6, True),  # Enabled, value < threshold (0.7), alert expected
    ],
)
def test_metric_stability_rule(enabled, report_ts, expect_alert):
    rule = MetricStabilityRule(
        "Test Rule",
        "timing_stability",
        "alert_threshold_ts",
        severity=AlertSeverity.WARNING,
        enabled=enabled,
    )
    report = create_mock_report(ts=report_ts)
    alert = rule.evaluate(report)

    if expect_alert:
        assert isinstance(alert, Alert)
        assert alert.rule_name == "Test Rule"
        assert alert.current_value == report_ts
        assert alert.threshold == 0.7
    else:
        assert alert is None


def test_metric_stability_rule_trigger_pss():
    rule = MetricStabilityRule("Test Rule PSS", "pss", "alert_threshold_ts")  # Using TS threshold for PSS
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


@pytest.mark.parametrize(
    "enabled, report_pss, history_pss_list, expect_alert",
    [
        (False, 80, [90], False),  # Disabled
        (True, 100, [], False),  # No history
        (True, 85, [95, 90], False),  # Stable: avg=92.5, drop=7.5 < 10
        (True, 80, [95, 90], True),  # Regressed: avg=92.5, drop=12.5 > 10
        (True, 80, [95], True),  # Short history: avg=95, drop=15 > 10
    ],
)
def test_stability_regression_rule(enabled, report_pss, history_pss_list, expect_alert):
    rule = StabilityRegressionRule(enabled=enabled)

    history = [create_mock_report(pss=p) for p in history_pss_list]
    report = create_mock_report(pss=report_pss)

    alert = rule.evaluate(report, history=history)

    if expect_alert:
        assert isinstance(alert, Alert)
        assert alert.rule_name == "Stability Regression"
        if len(history_pss_list) > 0:
            avg_pss = sum(history_pss_list) / len(history_pss_list)
            assert f"average {avg_pss}" in alert.message
    else:
        assert alert is None
