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

    def run(self, report: Dict[str, Any], history: Optional[List[Dict[str, Any]]] = None) -> List[Alert]:
        if not GLOBAL_CONFIG.alerts_enabled:
            return []

        triggered_alerts = []
        for rule in self.rules:
            alert = rule.evaluate(report, history)
            if alert:
                if self.state.should_alert(rule.name, self.cooldown):
                    triggered_alerts.append(alert)
                    self.state.record_alert(rule.name)
                else:
                    logging.info(f"Alert '{rule.name}' suppressed (cooldown).")

        if triggered_alerts:
            for channel in self.channels:
                channel.send_batch(triggered_alerts)

        return triggered_alerts
