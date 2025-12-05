from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional
from datetime import datetime


class AlertSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class Alert:
    rule_name: str
    severity: AlertSeverity
    message: str
    metric_name: str
    current_value: float
    threshold: float
    timestamp: float = field(default_factory=lambda: datetime.now().timestamp())
    extra_data: Dict[str, Any] = field(default_factory=dict)


class AlertChannel(ABC):
    """Abstract base class for alert outputs (Slack, Teams, etc.)"""

    @abstractmethod
    def send(self, alert: Alert) -> None:
        pass  # pragma: no cover

    # This is NOT abstract, it has a default implementation.
    def send_batch(self, alerts: List[Alert]) -> None:
        """Send multiple alerts, potentially aggregated."""
        for alert in alerts:
            self.send(alert)


class AlertRule(ABC):
    """Abstract base class for detection logic."""

    def __init__(self, name: str, enabled: bool = True):
        self.name = name
        self.enabled = enabled

    @abstractmethod
    def evaluate(
        self, report: Dict[str, Any], history: Optional[List[Dict[str, Any]]] = None
    ) -> Optional[Alert]:
        """
        Evaluate the rule against the current report (and optionally history).
        Returns an Alert if triggered, or None.
        """
        pass  # pragma: no cover
