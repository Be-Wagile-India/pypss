from unittest.mock import patch


class TestOTel:
    def test_enable_otel_integration(self):
        # Mock opentelemetry availability
        with patch("pypss.integrations.otel.OTEL_AVAILABLE", True):
            with patch("pypss.integrations.otel.metrics") as mock_metrics:
                from pypss.integrations.otel import enable_otel_integration

                reporter = enable_otel_integration()
                assert reporter
                assert mock_metrics.get_meter.called

                # Check gauge creation
                meter = mock_metrics.get_meter.return_value
                assert meter.create_observable_gauge.called

    def test_otel_callbacks(self):
        # Test the callback logic
        with patch("pypss.integrations.otel.OTEL_AVAILABLE", True):
            with patch("pypss.integrations.otel.metrics"):
                from pypss.integrations.otel import OTelReporter
                from pypss.instrumentation import global_collector

                # Setup data
                global_collector.clear()
                global_collector.add_trace({"duration": 0.1, "error": False})

                reporter = OTelReporter()

                # Test _observe_pss
                from unittest.mock import Mock

                pss_gen = reporter._observe_pss(Mock())
                obs = next(iter(pss_gen))
                assert obs.value > 0

                # Test breakdown callback
                timing_gen = reporter._observe_breakdown("timing_stability")(Mock())
                obs = next(iter(timing_gen))
                assert obs.value > 0
