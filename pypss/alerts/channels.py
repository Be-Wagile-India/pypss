import atexit
import json
import queue
import sys
import threading
import time
import urllib.request
from typing import Any, Dict, List, Optional, Union
from unittest.mock import MagicMock

from .base import Alert, AlertChannel, AlertSeverity

_alert_queue: queue.Queue = queue.Queue()
_sender_thread: Optional[threading.Thread] = None
_shutdown_event = threading.Event()
_mock_urlopen_for_tests: Optional[MagicMock] = None


def _sender_loop():
    while not _shutdown_event.is_set():
        try:
            url, data, headers, max_retries = _alert_queue.get(timeout=1)

            urlopen_func = _mock_urlopen_for_tests if _mock_urlopen_for_tests is not None else urllib.request.urlopen

            for attempt in range(max_retries):
                try:
                    req = urllib.request.Request(url, data=data, headers=headers)
                    with urlopen_func(req, timeout=10) as response:
                        status_code = getattr(response, "status", 200)
                        if 200 <= status_code < 300:
                            break
                except Exception as e:
                    if attempt == max_retries - 1:
                        print(
                            f"⚠️ Failed to send alert to {url} after {max_retries} attempts: {e}",
                            file=sys.stderr,
                        )
                    else:
                        time.sleep(1 * (attempt + 1))
            _alert_queue.task_done()
        except queue.Empty:
            continue
        except Exception as e:
            print(
                f"⚠️ An unexpected error occurred in alert sender loop: {e}",
                file=sys.stderr,
            )


def _start_sender_thread_once():
    global _sender_thread
    if _sender_thread is None or not _sender_thread.is_alive():
        _sender_thread = threading.Thread(target=_sender_loop, daemon=True)
        _sender_thread.start()
        if "pytest" not in sys.modules:
            atexit.register(_shutdown_sender_thread)


def _shutdown_sender_thread():
    global _mock_urlopen_for_tests
    _shutdown_event.set()
    _alert_queue.join()
    if _sender_thread and _sender_thread.is_alive():
        _sender_thread.join(timeout=5)
        if _sender_thread.is_alive():
            print("⚠️ Alert sender thread did not shut down cleanly.", file=sys.stderr)
    _mock_urlopen_for_tests = None


class WebhookChannel(AlertChannel):
    def __init__(self, url: str, max_retries: int = 3):
        self.url = url
        self.max_retries = max_retries
        _start_sender_thread_once()

    def send(self, alert: Alert) -> None:
        payload = {
            "rule": alert.rule_name,
            "severity": alert.severity.value,
            "message": alert.message,
            "metric": alert.metric_name,
            "value": alert.current_value,
            "threshold": alert.threshold,
            "timestamp": alert.timestamp,
        }
        self._post(payload)

    def send_batch(self, alerts: List[Alert]) -> None:
        for alert in alerts:
            self.send(alert)

    def _post(self, payload: Union[Dict[str, Any], List[Any]]) -> None:
        if not self.url:
            return
        data = json.dumps(payload).encode("utf-8")
        _alert_queue.put((self.url, data, {"Content-Type": "application/json"}, self.max_retries))


class SlackChannel(WebhookChannel):
    def __init__(self, url: str, max_retries: int = 3):
        super().__init__(url, max_retries)

    def send(self, alert: Alert) -> None:
        color = (
            "#36a64f"
            if alert.severity == AlertSeverity.INFO
            else "#ffcc00"
            if alert.severity == AlertSeverity.WARNING
            else "#ff0000"
        )
        payload = {
            "text": f"*{alert.severity.value.upper()}: {alert.rule_name}*",
            "attachments": [
                {
                    "color": color,
                    "fields": [
                        {"title": "Message", "value": alert.message, "short": False},
                        {
                            "title": "Metric",
                            "value": f"{alert.metric_name}: {alert.current_value:.2f}",
                            "short": True,
                        },
                        {
                            "title": "Threshold",
                            "value": f"{alert.threshold}",
                            "short": True,
                        },
                    ],
                }
            ],
        }
        self._post(payload)


class TeamsChannel(WebhookChannel):
    def __init__(self, url: str, max_retries: int = 3):
        super().__init__(url, max_retries)

    def send(self, alert: Alert) -> None:
        theme_color = (
            "00FF00"
            if alert.severity == AlertSeverity.INFO
            else "FFFF00"
            if alert.severity == AlertSeverity.WARNING
            else "FF0000"
        )
        payload = {
            "@type": "MessageCard",
            "@context": "http://schema.org/extensions",
            "themeColor": theme_color,
            "summary": f"{alert.severity.value.upper()}: {alert.rule_name}",
            "sections": [
                {
                    "activityTitle": (f"{alert.severity.value.upper()}: {alert.rule_name}"),
                    "activitySubtitle": alert.message,
                    "facts": [
                        {"name": "Metric", "value": alert.metric_name},
                        {"name": "Value", "value": f"{alert.current_value:.2f}"},
                        {"name": "Threshold", "value": str(alert.threshold)},
                    ],
                    "markdown": True,
                }
            ],
        }
        self._post(payload)


class AlertmanagerChannel(WebhookChannel):
    def __init__(self, url: str, max_retries: int = 3):
        super().__init__(url, max_retries)

    def send(self, alert: Alert) -> None:
        self.send_batch([alert])

    def send_batch(self, alerts: List[Alert]) -> None:
        if not alerts:
            return
        payload = []
        for alert in alerts:
            payload.append(
                {
                    "labels": {
                        "alertname": alert.rule_name,
                        "severity": alert.severity.value,
                        "service": "pypss",
                    },
                    "annotations": {
                        "summary": alert.message,
                        "value": str(alert.current_value),
                        "threshold": str(alert.threshold),
                    },
                }
            )
        self._post(payload)
