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

    def evaluate(
        self,
        report: Dict[str, Any],
        history: Optional[List[Dict[str, Any]]] = None,
        module_scores: Optional[Dict[str, Any]] = None,
    ) -> Optional[Alert]:
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

    def evaluate(
        self,
        report: Dict[str, Any],
        history: Optional[List[Dict[str, Any]]] = None,
        module_scores: Optional[Dict[str, Any]] = None,
    ) -> Optional[Alert]:
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


class CustomRule(AlertRule):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config.get("name", "Custom Rule"), enabled=config.get("enabled", True))
        self.config = config
        self.severity = AlertSeverity(config.get("severity", "warning"))

    def evaluate(
        self,
        report: Dict[str, Any],
        history: Optional[List[Dict[str, Any]]] = None,
        module_scores: Optional[Dict[str, Any]] = None,
    ) -> Optional[List[Alert]]:
        from typing import Union  # noqa: F401

        if not self.enabled:
            return None

        conditions = self.config.get("conditions", [])
        if not conditions:
            return None

        alerts = []
        module_pattern = self.config.get("module_pattern")

        if module_pattern and module_scores:
            import re

            try:
                pattern = re.compile(module_pattern)
            except re.error:
                return None

            for module_name, scores_data in module_scores.items():
                if pattern.match(module_name):
                    # Combine PSS and breakdown into a flat dict for evaluation
                    flat_metrics = {"pss": scores_data.get("pss", 0)}
                    flat_metrics.update(scores_data.get("breakdown", {}))

                    if self._check_conditions(flat_metrics, conditions):
                        alerts.append(
                            Alert(
                                rule_name=self.name,
                                severity=self.severity,
                                message=f"{self.name}: Module '{module_name}' matched conditions.",
                                metric_name="custom",
                                current_value=0,  # Placeholder
                                threshold=0,
                                extra_data={"module": module_name},
                            )
                        )
        elif not module_pattern:
            # Global check
            flat_metrics = {"pss": report.get("pss", 0)}
            flat_metrics.update(report.get("breakdown", {}))

            if self._check_conditions(flat_metrics, conditions):
                alerts.append(
                    Alert(
                        rule_name=self.name,
                        severity=self.severity,
                        message=f"{self.name}: Global metrics matched conditions.",
                        metric_name="custom",
                        current_value=0,
                        threshold=0,
                    )
                )

        return alerts if alerts else None

    def _check_conditions(self, metrics: Dict[str, float], conditions: List[Dict[str, Any]]) -> bool:
        for cond in conditions:
            metric_key = cond.get("metric")
            if not isinstance(metric_key, str):
                continue
            operator = cond.get("operator")
            try:
                threshold = float(cond.get("value", 0))
            except (ValueError, TypeError):
                continue

            val = float(metrics.get(metric_key, 0))

            if operator == "<" and not (val < threshold):
                return False
            if operator == "<=" and not (val <= threshold):
                return False
            if operator == ">" and not (val > threshold):
                return False
            if operator == ">=" and not (val >= threshold):
                return False
            if operator == "==" and not (val == threshold):
                return False

        return True
