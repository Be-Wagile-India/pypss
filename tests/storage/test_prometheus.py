import pytest
from unittest.mock import MagicMock, patch
from pypss.storage import prometheus


def test_prometheus_init_success():
    with (
        patch.object(prometheus, "PROMETHEUS_AVAILABLE", True),
        patch.object(prometheus, "Gauge", create=True) as MockGauge,
        patch.object(prometheus, "CollectorRegistry", create=True) as MockRegistry,
    ):
        storage = prometheus.PrometheusStorage()

        assert MockRegistry.called
        assert MockGauge.call_count == 6  # 6 metrics defined in init
        assert storage.registry is not None


def test_prometheus_missing_dependency():
    with patch.object(prometheus, "PROMETHEUS_AVAILABLE", False):
        with pytest.raises(ImportError, match="prometheus-client is not installed"):
            prometheus.PrometheusStorage()


def test_prometheus_save_logic():
    with (
        patch.object(prometheus, "PROMETHEUS_AVAILABLE", True),
        patch.object(prometheus, "Gauge", create=True) as MockGauge,
        patch.object(prometheus, "CollectorRegistry", create=True),
        patch.object(prometheus, "push_to_gateway", create=True) as mock_push,
    ):
        # Ensure Gauge() returns a new mock instance each time
        MockGauge.side_effect = lambda *args, **kwargs: MagicMock()

        storage = prometheus.PrometheusStorage(push_gateway="localhost:9091")

        # Capture the specific mock instances attached to the storage
        # Cast to MagicMock to satisfy mypy
        from unittest.mock import Mock
        from typing import cast

        mock_g_pss = cast(Mock, storage.g_pss)
        mock_g_ts = cast(Mock, storage.g_ts)
        mock_g_ms = cast(Mock, storage.g_ms)

        report = {
            "pss": 88.8,
            "breakdown": {
                "timing_stability": 0.9,
                "memory_stability": 0.8,
                "error_volatility": 1.0,
                "branching_entropy": 0.5,
                "concurrency_chaos": 0.7,
            },
        }

        storage.save(report)

        # Verify calls on specific instances
        mock_g_pss.set.assert_called_with(88.8)
        mock_g_ts.set.assert_called_with(0.9)
        mock_g_ms.set.assert_called_with(0.8)

        # Verify push
        mock_push.assert_called_once()


def test_prometheus_push_failure(capsys):
    with (
        patch.object(prometheus, "PROMETHEUS_AVAILABLE", True),
        patch.object(prometheus, "Gauge", create=True),
        patch.object(prometheus, "CollectorRegistry", create=True),
        patch.object(prometheus, "push_to_gateway", create=True) as mock_push,
    ):
        mock_push.side_effect = Exception("Connection refused")

        storage = prometheus.PrometheusStorage(push_gateway="bad_host:9091")

        # Should not raise exception but print error
        storage.save({"pss": 50.0})

        captured = capsys.readouterr()
        assert "Failed to push metrics" in captured.out
        assert "Connection refused" in captured.out


def test_get_history_empty():
    with (
        patch.object(prometheus, "PROMETHEUS_AVAILABLE", True),
        patch.object(prometheus, "Gauge", create=True),
        patch.object(prometheus, "CollectorRegistry", create=True),
    ):
        storage = prometheus.PrometheusStorage()
        assert storage.get_history() == []


def test_prometheus_pull_mode():
    with (
        patch.object(prometheus, "PROMETHEUS_AVAILABLE", True),
        patch.object(prometheus, "Gauge", create=True),
        patch.object(prometheus, "CollectorRegistry", create=True),
        patch.object(prometheus, "start_http_server", create=True) as mock_start,
    ):
        storage = prometheus.PrometheusStorage(http_port=8000)
        mock_start.assert_called_with(8000, registry=storage.registry)
