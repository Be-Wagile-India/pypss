import importlib
import sys
from unittest.mock import MagicMock

import pypss
from pypss.integrations import otel


class TestOtelCoverage:
    def test_otel_missing_import(self, monkeypatch):
        # Mock otel missing
        monkeypatch.setitem(sys.modules, "opentelemetry", None)
        monkeypatch.setitem(sys.modules, "opentelemetry.metrics", None)

        # Reload otel module
        importlib.reload(otel)

        assert otel.OTEL_AVAILABLE is False

        reporter = otel.OTelReporter()
        assert not hasattr(reporter, "meter")

    def test_observe_no_collector(self, monkeypatch):
        # Ensure OTEL is available
        if not otel.OTEL_AVAILABLE:
            importlib.reload(otel)

        monkeypatch.setattr(pypss, "get_global_collector", lambda: None)

        # We need a dummy meter to avoid errors
        mock_meter = MagicMock()
        mock_provider = MagicMock()
        mock_provider.get_meter.return_value = mock_meter

        # Need to mock metrics.get_meter
        monkeypatch.setattr(otel.metrics, "get_meter", lambda *args, **kwargs: mock_meter)

        reporter = otel.OTelReporter(meter_provider=mock_provider)

        # Directly call _compute_snapshot
        report = reporter._compute_snapshot()
        assert report["pss"] == 0
