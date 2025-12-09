import pytest
from unittest.mock import MagicMock, patch
from typing import Dict, Optional  # Add Dict, Optional
from pypss.storage import (
    get_storage_backend,
    check_regression,
    SQLiteStorage,
    PrometheusStorage,
    StorageBackend,
)


def test_get_storage_backend_sqlite(tmp_path):
    config: Dict[str, str] = {
        "storage_backend": "sqlite",
        "storage_uri": str(tmp_path / "db.sqlite"),
    }  # Added type annotation
    backend = get_storage_backend(config)
    assert isinstance(backend, SQLiteStorage)
    assert backend.db_path == str(tmp_path / "db.sqlite")


def test_get_storage_backend_default():
    config: Dict[str, str] = {}  # Added type annotation
    backend = get_storage_backend(config)
    assert isinstance(backend, SQLiteStorage)
    assert backend.db_path == "pypss_history.db"


def test_get_storage_backend_prometheus():
    # Mock PROMETHEUS_AVAILABLE = True in the module where PrometheusStorage is defined
    with (
        patch("pypss.storage.prometheus.PROMETHEUS_AVAILABLE", True),
        patch("pypss.storage.prometheus.Gauge", create=True),
        patch("pypss.storage.prometheus.CollectorRegistry", create=True),
    ):
        config: Dict[str, str] = {
            "storage_backend": "prometheus",
            "storage_uri": "localhost:9091",
        }  # Added type annotation
        backend = get_storage_backend(config)
        assert isinstance(backend, PrometheusStorage)
        assert backend.push_gateway == "localhost:9091"


def test_get_storage_backend_invalid():
    config = {"storage_backend": "unknown"}
    with pytest.raises(ValueError, match="Unknown storage backend"):
        get_storage_backend(config)


def test_check_regression_no_history():
    storage = MagicMock(spec=StorageBackend)
    storage.get_history.return_value = []

    report = {"pss": 80}
    result = check_regression(report, storage)
    assert result is None


def test_check_regression_stable():
    storage = MagicMock(spec=StorageBackend)
    # Avg 90
    storage.get_history.return_value = [{"pss": 90}, {"pss": 90}]

    report = {"pss": 85}  # Drop of 5 < threshold 10
    result = check_regression(report, storage, threshold_drop=10)
    assert result is None


def test_check_regression_detected():
    storage = MagicMock(spec=StorageBackend)
    # Avg 90
    storage.get_history.return_value = [{"pss": 90}, {"pss": 90}]

    report = {"pss": 70}  # Drop of 20 > threshold 10
    result = check_regression(report, storage, threshold_drop=10)
    assert result is not None  # Ensure result is not None before checking its content
    assert "REGRESSION DETECTED" in result
    assert "Current PSS (70.0)" in result
    assert "average (90.0)" in result


def test_check_regression_exception():
    storage = MagicMock(spec=StorageBackend)
    storage.get_history.side_effect = Exception("DB Error")

    report = {"pss": 80}
    result = check_regression(report, storage)
    assert result is None


def test_get_storage_backend_prometheus_pull_default_port():
    with (
        patch("pypss.storage.prometheus.PROMETHEUS_AVAILABLE", True),
        patch("pypss.storage.prometheus.Gauge", create=True),
        patch("pypss.storage.prometheus.CollectorRegistry", create=True),
    ):
        config: Dict[str, Optional[str]] = {
            "storage_backend": "prometheus",
            "storage_uri": None,  # URI is None
            "storage_mode": "pull",  # Explicitly set mode to pull
        }
        backend = get_storage_backend(config)
        assert isinstance(backend, PrometheusStorage)
        # Expected default port when uri is None for pull mode
        assert backend.http_port == 8000


def test_get_storage_backend_prometheus_pull_invalid_uri():
    with (
        patch("pypss.storage.prometheus.PROMETHEUS_AVAILABLE", True),
        patch("pypss.storage.prometheus.Gauge", create=True),
        patch("pypss.storage.prometheus.CollectorRegistry", create=True),
    ):
        config: Dict[str, str] = {
            "storage_backend": "prometheus",
            "storage_uri": "invalid_port_string",  # Invalid URI
            "storage_mode": "pull",  # Explicitly set mode to pull
        }
        backend = get_storage_backend(config)
        assert isinstance(backend, PrometheusStorage)
        # Expected default port when uri is invalid for pull mode
        assert backend.http_port == 8000
