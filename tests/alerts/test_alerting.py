import pytest
from unittest.mock import MagicMock, patch
import json
import urllib.error
# import socket # To mock socket.socket for network calls - NO LONGER NEEDED


from pypss.alerts.engine import AlertEngine
from pypss.alerts.base import AlertChannel, Alert, AlertSeverity
from pypss.alerts.channels import (
    WebhookChannel,
    SlackChannel,
    TeamsChannel,
    AlertmanagerChannel,
    _alert_queue,  # Import the queue
    _shutdown_event,  # Import the event
    _shutdown_sender_thread,  # Import the shutdown function for cleanup
)
from pypss.utils.config import GLOBAL_CONFIG


# Mock atexit for test isolation
@pytest.fixture(autouse=True)
def mock_atexit_register_and_unregister():
    # Patch atexit.register at the module level for the modules under test
    with (
        patch("pypss.alerts.channels.atexit.register") as mock_channels_register,
        patch("pypss.alerts.state.atexit.register") as mock_state_register,
        patch("atexit.unregister") as mock_unregister,
    ):  # Unregister is global
        yield mock_channels_register, mock_state_register, mock_unregister


# Ensure the sender thread is cleanly shut down between tests
@pytest.fixture(autouse=True)
def cleanup_sender_thread(mock_atexit_register_and_unregister):
    mock_channels_register, mock_state_register, mock_unregister = (
        mock_atexit_register_and_unregister
    )
    yield
    # Ensure queue is empty and thread is shut down after each test
    while not _alert_queue.empty():
        _alert_queue.get()
        _alert_queue.task_done()
    _shutdown_event.set()
    _shutdown_sender_thread()
    _shutdown_event.clear()  # Reset for next test

    # Crucially, ensure atexit handler for _shutdown_sender_thread is unregistered
    # and re-register original _shutdown_sender_thread for non-test runs
    mock_unregister.reset_mock()  # Clean mock for next test


@pytest.fixture
def mock_config():
    old_alerts_enabled = GLOBAL_CONFIG.alerts_enabled
    old_slack_webhook = GLOBAL_CONFIG.alerts_slack_webhook
    old_teams_webhook = GLOBAL_CONFIG.alerts_teams_webhook
    old_generic_webhook = GLOBAL_CONFIG.alerts_generic_webhook
    old_alertmanager_url = GLOBAL_CONFIG.alerts_alertmanager_url

    GLOBAL_CONFIG.alerts_enabled = True
    GLOBAL_CONFIG.alerts_slack_webhook = "http://mock-slack"
    GLOBAL_CONFIG.alerts_teams_webhook = "http://mock-teams"
    GLOBAL_CONFIG.alerts_generic_webhook = "http://mock-generic"
    GLOBAL_CONFIG.alerts_alertmanager_url = "http://mock-alertmanager"

    yield  # This is where the test function runs

    GLOBAL_CONFIG.alerts_enabled = old_alerts_enabled
    GLOBAL_CONFIG.alerts_slack_webhook = old_slack_webhook
    GLOBAL_CONFIG.alerts_teams_webhook = old_teams_webhook
    GLOBAL_CONFIG.alerts_generic_webhook = old_generic_webhook
    GLOBAL_CONFIG.alerts_alertmanager_url = old_alertmanager_url


# Patch time.sleep globally for alerting tests to speed them up
@pytest.fixture(autouse=True)
def mock_global_sleep():
    with patch("time.sleep"):
        yield


# Robust urllib.request mocking
@pytest.fixture(autouse=True)
def mock_urllib_request():
    global _mock_urlopen_for_tests  # Access the global variable

    mock_urlopen_func = MagicMock()
    mock_response_context = MagicMock()
    mock_response_context.status = 200
    mock_urlopen_func.return_value.__enter__.return_value = mock_response_context

    with patch("urllib.request.Request") as mock_request_cls:
        # Patch urllib.request.urlopen in the main thread (for direct calls)
        with patch("urllib.request.urlopen", new=mock_urlopen_func):
            # Set the global variable for the sender thread to pick up
            _mock_urlopen_for_tests = mock_urlopen_func
            yield mock_request_cls, mock_urlopen_func
            # Clean up the global mock after the test
            _mock_urlopen_for_tests = None


# Original test_alert_engine_triggers
def test_alert_engine_triggers(
    mock_config, tmp_path, mock_urllib_request
):  # Added mock_urllib_request
    mock_request_cls, mock_urlopen_func = mock_urllib_request  # Unpack fixture
    report = {
        "pss": 50,
        "breakdown": {
            "timing_stability": 0.5,  # Below default 0.7
            "memory_stability": 0.9,
            "error_volatility": 0.9,
            "branching_entropy": 0.9,
            "concurrency_chaos": 0.9,
        },
    }

    # Patch STATE_FILE to avoid interference from previous runs (deduplication)
    with patch("pypss.alerts.state.STATE_FILE", str(tmp_path / "state.json")):
        # with patch("urllib.request.urlopen") as mock_urlopen: # Mocked by fixture now
        engine = AlertEngine()
        alerts = engine.run(report)
        _alert_queue.join()  # Wait for alerts to be sent

        assert len(alerts) >= 1
        assert alerts[0].rule_name == "Timing Stability Surge"
        assert mock_urlopen_func.called  # Assert on fixture's mock


# Original test_alert_engine_disabled
def test_alert_engine_disabled():
    # Explicitly disable
    GLOBAL_CONFIG.alerts_enabled = False
    report = {"pss": 0, "breakdown": {}}

    engine = AlertEngine()
    alerts = engine.run(report)
    assert len(alerts) == 0


# MockAlertChannel and test_alert_channel_send_batch
class MockAlertChannel(AlertChannel):
    def __init__(self):
        self.sent_alerts = []

    def send(self, alert: Alert) -> None:
        self.sent_alerts.append(alert)


def test_alert_channel_send_batch():
    channel = MockAlertChannel()
    alerts = [
        Alert(
            rule_name="Test1",
            severity=AlertSeverity.INFO,
            message="Msg1",
            metric_name="M1",
            current_value=1.0,
            threshold=0.5,
        ),
        Alert(
            rule_name="Test2",
            severity=AlertSeverity.WARNING,
            message="Msg2",
            metric_name="M2",
            current_value=0.8,
            threshold=0.6,
        ),
    ]
    channel.send_batch(alerts)
    assert len(channel.sent_alerts) == 2
    assert channel.sent_alerts[0].rule_name == "Test1"
    assert channel.sent_alerts[1].rule_name == "Test2"


# Channel tests
def test_webhook_channel_send_success(mock_urllib_request):  # Pass fixture
    mock_request_cls, mock_urlopen_func = mock_urllib_request
    channel = WebhookChannel("http://mock-webhook.com", max_retries=1)
    alert = Alert(
        rule_name="Test",
        severity=AlertSeverity.INFO,
        message="Msg",
        metric_name="M1",
        current_value=1.0,
        threshold=0.5,
    )

    channel.send(alert)
    _alert_queue.join()  # Wait for background sender to process
    mock_urlopen_func.assert_called_once()  # Assert on fixture's mock


def test_webhook_channel_send_failure(capsys, mock_urllib_request):  # Pass fixture
    mock_request_cls, mock_urlopen_func = mock_urllib_request
    channel = WebhookChannel("http://mock-webhook.com/fail", max_retries=1)
    alert = Alert(
        rule_name="Test",
        severity=AlertSeverity.INFO,
        message="Msg",
        metric_name="M1",
        current_value=1.0,
        threshold=0.5,
    )

    mock_urlopen_func.side_effect = urllib.error.URLError("Connection refused")
    channel.send(alert)
    _alert_queue.join()  # Wait for retries to finish
    captured = capsys.readouterr()
    assert "Failed to send alert" in captured.out


def test_webhook_channel_empty_url_with_mock(mock_urllib_request):  # New test
    mock_request_cls, mock_urlopen_func = mock_urllib_request
    channel = WebhookChannel("", max_retries=1)  # Empty URL
    alert = Alert(
        rule_name="Test",
        severity=AlertSeverity.INFO,
        message="Msg",
        metric_name="M1",
        current_value=1.0,
        threshold=0.5,
    )
    channel.send(alert)
    _alert_queue.join()  # Should process and ignore
    mock_urlopen_func.assert_not_called()  # Should not attempt to open URL


def test_slack_channel_send(mock_urllib_request):  # Pass fixture
    mock_request_cls, mock_urlopen_func = mock_urllib_request
    channel = SlackChannel("http://mock-slack.com", max_retries=1)
    alert = Alert(
        rule_name="Slack Test",
        severity=AlertSeverity.CRITICAL,
        message="Something critical",
        metric_name="Error Volatility",
        current_value=0.4,
        threshold=0.7,
    )

    channel.send(alert)
    _alert_queue.join()
    mock_urlopen_func.assert_called_once()
    call_args = mock_request_cls.call_args.kwargs  # Get kwargs from Request call
    payload = json.loads(call_args["data"].decode())  # Access data from kwargs
    assert "CRITICAL" in payload["text"]
    assert payload["attachments"][0]["color"] == "#ff0000"


def test_slack_channel_send_warning(mock_urllib_request):  # New test for warning color
    mock_request_cls, mock_urlopen_func = mock_urllib_request
    channel = SlackChannel("http://mock-slack.com", max_retries=1)
    alert = Alert(
        rule_name="Slack Test Warn",
        severity=AlertSeverity.WARNING,
        message="Something might be wrong",
        metric_name="Timing Stability",
        current_value=0.6,
        threshold=0.7,
    )
    channel.send(alert)
    _alert_queue.join()
    mock_urlopen_func.assert_called_once()
    call_args = mock_request_cls.call_args.kwargs
    payload = json.loads(call_args["data"].decode())
    assert payload["attachments"][0]["color"] == "#ffcc00"


def test_slack_channel_send_info(mock_urllib_request):  # New test for info color
    mock_request_cls, mock_urlopen_func = mock_urllib_request
    channel = SlackChannel("http://mock-slack.com", max_retries=1)
    alert = Alert(
        rule_name="Slack Test Info",
        severity=AlertSeverity.INFO,
        message="All good",
        metric_name="PSS",
        current_value=0.95,
        threshold=0.90,
    )
    channel.send(alert)
    _alert_queue.join()
    mock_urlopen_func.assert_called_once()
    call_args = mock_request_cls.call_args.kwargs
    payload = json.loads(call_args["data"].decode())
    assert payload["attachments"][0]["color"] == "#36a64f"


def test_teams_channel_send(mock_urllib_request):  # Pass fixture
    mock_request_cls, mock_urlopen_func = mock_urllib_request
    channel = TeamsChannel("http://mock-teams.com", max_retries=1)
    alert = Alert(
        rule_name="Teams Test",
        severity=AlertSeverity.WARNING,
        message="Watch out",
        metric_name="Memory",
        current_value=0.6,
        threshold=0.8,
    )

    channel.send(alert)
    _alert_queue.join()
    mock_urlopen_func.assert_called_once()
    call_args = mock_request_cls.call_args.kwargs
    payload = json.loads(call_args["data"].decode())
    assert payload["@type"] == "MessageCard"
    assert payload["themeColor"] == "FFFF00"


def test_teams_channel_send_info(mock_urllib_request):  # New test for info color
    mock_request_cls, mock_urlopen_func = mock_urllib_request
    channel = TeamsChannel("http://mock-teams.com", max_retries=1)
    alert = Alert(
        rule_name="Teams Test Info",
        severity=AlertSeverity.INFO,
        message="All good",
        metric_name="PSS",
        current_value=0.95,
        threshold=0.90,
    )
    channel.send(alert)
    _alert_queue.join()
    mock_urlopen_func.assert_called_once()
    call_args = mock_request_cls.call_args.kwargs
    payload = json.loads(call_args["data"].decode())
    assert payload["themeColor"] == "00FF00"


def test_teams_channel_send_critical(
    mock_urllib_request,
):  # New test for critical color
    mock_request_cls, mock_urlopen_func = mock_urllib_request
    channel = TeamsChannel("http://mock-teams.com", max_retries=1)
    alert = Alert(
        rule_name="Teams Test Critical",
        severity=AlertSeverity.CRITICAL,
        message="System down",
        metric_name="Error Volatility",
        current_value=0.1,
        threshold=0.7,
    )
    channel.send(alert)
    _alert_queue.join()
    mock_urlopen_func.assert_called_once()
    call_args = mock_request_cls.call_args.kwargs
    payload = json.loads(call_args["data"].decode())
    assert payload["themeColor"] == "FF0000"


def test_alertmanager_channel_send_batch(mock_urllib_request):  # Pass fixture
    mock_request_cls, mock_urlopen_func = mock_urllib_request
    channel = AlertmanagerChannel("http://mock-alertmanager.com", max_retries=1)
    alerts = [
        Alert(
            rule_name="AM Test1",
            severity=AlertSeverity.INFO,
            message="Msg1",
            metric_name="M1",
            current_value=1.0,
            threshold=0.5,
        ),
        Alert(
            rule_name="AM Test2",
            severity=AlertSeverity.CRITICAL,
            message="Msg2",
            metric_name="M2",
            current_value=0.8,
            threshold=0.6,
        ),
    ]

    channel.send_batch(alerts)
    _alert_queue.join()
    mock_urlopen_func.assert_called_once()
    call_args = mock_request_cls.call_args.kwargs
    payload = json.loads(call_args["data"].decode())
    assert isinstance(payload, list)
    assert len(payload) == 2
    assert payload[0]["labels"]["alertname"] == "AM Test1"
    assert payload[1]["labels"]["severity"] == "critical"
