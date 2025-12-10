import logging
from typing import Any, Dict, List, Optional

from ..utils.config import GLOBAL_CONFIG
from .base import Alert, AlertChannel, AlertRule
from .channels import AlertmanagerChannel, SlackChannel, TeamsChannel, WebhookChannel
from .rules import (
    ConcurrencySpikeRule,
    EntropyAnomalyRule,
    ErrorBurstRule,
    MemoryStabilitySpikeRule,
    StabilityRegressionRule,
    TimingStabilitySurgeRule,
)
from .state import AlertState


class AlertEngine:
    def __init__(self) -> None:
        self.rules: List[AlertRule] = [
            TimingStabilitySurgeRule(),
            MemoryStabilitySpikeRule(),
            ErrorBurstRule(),
            EntropyAnomalyRule(),
            ConcurrencySpikeRule(),
            StabilityRegressionRule(),
        ]

        # Load custom rules
        from .rules import CustomRule

        for rule_config in GLOBAL_CONFIG.custom_alert_rules:
            self.rules.append(CustomRule(rule_config))

        self.channels: List[AlertChannel] = []
        self.state = AlertState()
        self.cooldown = 3600
        self._init_channels()
        self._validate_config()

    def _init_channels(self) -> None:
        conf = GLOBAL_CONFIG
        if not conf.alerts_enabled:
            return

        if conf.alerts_slack_webhook:
            self.channels.append(SlackChannel(conf.alerts_slack_webhook))
        if conf.alerts_teams_webhook:
            self.channels.append(TeamsChannel(conf.alerts_teams_webhook))
        if conf.alerts_generic_webhook:
            self.channels.append(WebhookChannel(conf.alerts_generic_webhook))
        if conf.alerts_alertmanager_url:
            self.channels.append(AlertmanagerChannel(conf.alerts_alertmanager_url))

    def _validate_config(self) -> None:
        if GLOBAL_CONFIG.alerts_enabled and not self.channels:
            logging.warning("Alerting enabled but no channels configured in pypss.toml!")

    def run(
        self,
        report: Dict[str, Any],
        history: Optional[List[Dict[str, Any]]] = None,
        module_scores: Optional[Dict[str, Any]] = None,
    ) -> List[Alert]:
        if not GLOBAL_CONFIG.alerts_enabled:
            return []

        triggered_alerts = []
        for rule in self.rules:
            result = rule.evaluate(report, history, module_scores)

            alerts_to_process = []
            if isinstance(result, list):
                alerts_to_process = result
            elif result:
                alerts_to_process = [result]

            for alert in alerts_to_process:
                # Use a unique key for deduplication including module if present
                dedup_key = rule.name
                if alert.extra_data and "module" in alert.extra_data:
                    dedup_key += f":{alert.extra_data['module']}"

                if self.state.should_alert(dedup_key, self.cooldown):
                    triggered_alerts.append(alert)
                    self.state.record_alert(dedup_key)
                else:
                    logging.info(f"Alert '{dedup_key}' suppressed (cooldown).")

        if triggered_alerts:
            for channel in self.channels:
                channel.send_batch(triggered_alerts)

        return triggered_alerts
