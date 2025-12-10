from typing import Any, Dict, List, Optional

from ..utils.config import GLOBAL_CONFIG
from .base import Alert, AlertRule, AlertSeverity


class MetricStabilityRule(AlertRule):
    def __init__(
        self,
        name: str,
        metric_key: str,
        threshold_key: str,
        severity: AlertSeverity = AlertSeverity.WARNING,
        enabled: bool = True,
    ):
        super().__init__(name, enabled=enabled)
        self.metric_key = metric_key
        self.threshold_key = threshold_key
        self.severity = severity

    def evaluate(self, report: Dict[str, Any], history: Optional[List[Dict[str, Any]]] = None) -> Optional[Alert]:
        if not self.enabled:
            return None

        if self.metric_key == "pss":
            current_val = float(report.get("pss", 0.0))
            if current_val > 1.0:
                current_val /= 100.0
        else:
            breakdown = report.get("breakdown", {})
            current_val = float(breakdown.get(self.metric_key, 1.0))

        threshold = getattr(GLOBAL_CONFIG, self.threshold_key, 0.7)

        if current_val < threshold:
            return Alert(
                rule_name=self.name,
                severity=self.severity,
                message=(f"{self.name} detected. Score {current_val:.2f} is below threshold {threshold:.2f}."),
                metric_name=self.metric_key,
                current_value=current_val,
                threshold=threshold,
            )
        return None


class TimingStabilitySurgeRule(MetricStabilityRule):
    def __init__(self):
        super().__init__("Timing Stability Surge", "timing_stability", "alert_threshold_ts")


class MemoryStabilitySpikeRule(MetricStabilityRule):
    def __init__(self):
        super().__init__("Memory Stability Spike", "memory_stability", "alert_threshold_ms")


class ErrorBurstRule(MetricStabilityRule):
    def __init__(self):
        super().__init__(
            "Error Burst",
            "error_volatility",
            "alert_threshold_ev",
            AlertSeverity.CRITICAL,
        )


class EntropyAnomalyRule(MetricStabilityRule):
    def __init__(self):
        super().__init__("Entropy Anomaly", "branching_entropy", "alert_threshold_be")


class ConcurrencySpikeRule(MetricStabilityRule):
    def __init__(self):
        super().__init__("Concurrency Variance Spike", "concurrency_chaos", "alert_threshold_cc")


class StabilityRegressionRule(AlertRule):
    def __init__(self, enabled: bool = True):
        super().__init__("Stability Regression", enabled=enabled)

    def evaluate(self, report: Dict[str, Any], history: Optional[List[Dict[str, Any]]] = None) -> Optional[Alert]:
        if not self.enabled or not history:
            return None

        limit = getattr(GLOBAL_CONFIG, "regression_history_limit", 5)
        threshold_drop = getattr(GLOBAL_CONFIG, "regression_threshold_drop", 10.0)

        recent_history = history[:limit]
        if not recent_history:
            return None

        avg_pss = sum(h["pss"] for h in recent_history) / len(recent_history)
        current_pss = float(report.get("pss", 0.0))

        if current_pss < (avg_pss - threshold_drop):
            return Alert(
                rule_name=self.name,
                severity=AlertSeverity.CRITICAL,
                message=(
                    f"Regression detected! PSS {current_pss:.1f} is significantly lower "
                    f"than average {avg_pss:.1f} (-{threshold_drop})."
                ),
                metric_name="pss",
                current_value=current_pss,
                threshold=avg_pss - threshold_drop,
            )
        return None
