import pytest
import time
from unittest import mock
import logging

import pypss  # Import pypss
from pypss.core.error_rate_monitor import (
    ErrorRateMonitor,
)  # Only import the class, not the global instance
from pypss.instrumentation.collectors import FileFIFOCollector
from pypss.core.adaptive_sampler import adaptive_sampler
from pypss.utils.config import GLOBAL_CONFIG


@pytest.fixture(autouse=True)
def setup_teardown_global_state(monkeypatch):
    """Fixture to reset GLOBAL_CONFIG and global monitor instances before and after each test."""

    # Call pypss.init() to ensure global_collector and error_rate_monitor are initialized
    pypss.init()

    # Now pypss.get_global_collector() and pypss.get_error_rate_monitor() are guaranteed to be initialized.

    # Store original values from global error_rate_monitor (which is now initialized)
    _erm = pypss.get_error_rate_monitor()  # Use the getter
    assert _erm is not None
    original_erm_interval = _erm.interval
    original_erm_window_size = _erm.window_size

    # Reset global collector (which is now pypss.get_global_collector())
    _collector = pypss.get_global_collector()
    _collector.clear()

    # Reset global adaptive_sampler (as it's updated by ErrorRateMonitor)
    # Mock this as well to prevent interaction between tests
    mock_adaptive_sampler = mock.Mock(spec=adaptive_sampler)
    monkeypatch.setattr(
        "pypss.core.adaptive_sampler.adaptive_sampler", mock_adaptive_sampler
    )

    yield  # Run the test

    # Restore original values for global error_rate_monitor
    _erm = pypss.get_error_rate_monitor()  # Use the getter
    _erm.interval = original_erm_interval
    _erm.window_size = original_erm_window_size

    # Stop and clear global error_rate_monitor
    if _erm._thread and _erm._thread.is_alive():
        _erm.stop()

    # Clear global collector
    pypss.get_global_collector().clear()

    # Reset global adaptive_sampler (no need to restore mock_adaptive_sampler state, just mock it fresh each time)


class TestErrorRateMonitor:
    def test_initialization(self):
        # Now we can assume global_collector is initialized by the fixture
        assert pypss.get_global_collector() is not None
        monitor = ErrorRateMonitor(collector=pypss.get_global_collector())
        assert monitor.interval == GLOBAL_CONFIG.adaptive_sampler_min_interval
        assert monitor.window_size == 100  # Default if not set by config
        assert not monitor._error_history
        assert monitor._thread is None
        assert not monitor._stop_event.is_set()

    def test_start_stop(self):
        assert pypss.get_global_collector() is not None
        monitor = ErrorRateMonitor(collector=pypss.get_global_collector())
        monitor.start()
        assert monitor._thread is not None
        assert monitor._thread.is_alive()
        monitor.stop()
        if monitor._thread:  # Guard against NoneType
            monitor._thread.join(timeout=1)
            assert not monitor._thread.is_alive()
        assert monitor._stop_event.is_set()

    def test_start_already_running(self, caplog):
        assert pypss.get_global_collector() is not None
        monitor = ErrorRateMonitor(collector=pypss.get_global_collector())
        monitor.start()
        assert monitor._thread is not None
        thread_id_1 = monitor._thread.ident

        with caplog.at_level(logging.INFO):
            monitor.start()
            assert (
                "Error Rate Monitor already running." in caplog.text
            )  # Should log this

        assert monitor._thread is not None
        thread_id_2 = monitor._thread.ident
        assert thread_id_1 == thread_id_2  # Ensure no new thread was started

        monitor.stop()

    def test_error_rate_calculation_no_errors(self, monkeypatch):
        mock_adaptive_sampler = mock.Mock(spec=adaptive_sampler)
        monkeypatch.setattr(
            "pypss.core.error_rate_monitor.adaptive_sampler", mock_adaptive_sampler
        )
        monitor = ErrorRateMonitor(
            collector=pypss.get_global_collector(), interval=0.01, window_size=5
        )

        # Add traces to global_collector to trigger _on_new_trace callback
        pypss.get_global_collector().clear()  # Ensure clean state before adding
        for _ in range(5):
            pypss.get_global_collector().add_trace(
                {"error": False}
            )  # Add 5 non-error traces

        monitor._calculate_and_update_error_rate()

        mock_adaptive_sampler.update_metrics.assert_called_once_with(
            error_rate=0.0, trace_count=5
        )

    def test_error_rate_calculation_some_errors(self, monkeypatch):
        mock_adaptive_sampler = mock.Mock(spec=adaptive_sampler)
        monkeypatch.setattr(
            "pypss.core.error_rate_monitor.adaptive_sampler", mock_adaptive_sampler
        )

        assert pypss.get_global_collector() is not None
        monitor = ErrorRateMonitor(
            collector=pypss.get_global_collector(), interval=0.01, window_size=5
        )

        # Add traces to global_collector to trigger _on_new_trace callback
        # Use the actual global_collector, which will notify the monitor
        pypss.get_global_collector().clear()  # Ensure clean state before adding
        for _ in range(3):
            pypss.get_global_collector().add_trace({"error": False})
        for _ in range(2):
            pypss.get_global_collector().add_trace({"error": True})

        monitor._calculate_and_update_error_rate()

        mock_adaptive_sampler.update_metrics.assert_called_once_with(
            error_rate=0.4, trace_count=5
        )  # 2 errors out of 5 traces

    def test_error_rate_calculation_all_errors(self, monkeypatch):
        mock_adaptive_sampler = mock.Mock(spec=adaptive_sampler)
        monkeypatch.setattr(
            "pypss.core.error_rate_monitor.adaptive_sampler", mock_adaptive_sampler
        )

        assert pypss.get_global_collector() is not None
        monitor = ErrorRateMonitor(
            collector=pypss.get_global_collector(), interval=0.01, window_size=5
        )

        # Add traces to global_collector to trigger _on_new_trace callback
        pypss.get_global_collector().clear()  # Ensure clean state before adding
        for _ in range(5):  # Add 5 errors to fill the window
            pypss.get_global_collector().add_trace({"error": True})

        monitor._calculate_and_update_error_rate()

        mock_adaptive_sampler.update_metrics.assert_called_once_with(
            error_rate=1.0, trace_count=5
        )  # 5 errors out of 5 traces (due to window_size)

    def test_error_rate_monitor_thread_integration(self, monkeypatch):
        # This test ensures the thread runs and calls _calculate_and_update_error_rate
        mock_calc_update = mock.Mock()
        monkeypatch.setattr(
            ErrorRateMonitor, "_calculate_and_update_error_rate", mock_calc_update
        )

        assert pypss.get_global_collector() is not None
        monitor = ErrorRateMonitor(
            collector=pypss.get_global_collector(), interval=0.05, window_size=10
        )  # Pass global_collector; Small interval for quick test
        monitor.start()

        # Give the thread a moment to run at least once
        time.sleep(0.15)  # Should run at least 3 times

        monitor.stop()
        if monitor._thread:  # Guard against NoneType
            monitor._thread.join(timeout=1)

        assert (
            mock_calc_update.call_count >= 2
        )  # Should have been called at least twice

    def test_error_rate_monitor_with_threaded_batch_collector(self, monkeypatch):
        # Mock a FileFIFOCollector (which is a ThreadedBatchCollector subclass)
        # We need to ensure its add_trace calls our _on_new_trace observer
        mock_file_fifo_collector = mock.Mock(spec=FileFIFOCollector)

        # We need to register the monitor's _on_new_trace as an observer on the mock collector
        # This happens implicitly when ErrorRateMonitor is initialized with the mock_file_fifo_collector

        # Mock adaptive_sampler as it will be updated
        mock_adaptive_sampler = mock.Mock(spec=adaptive_sampler)
        monkeypatch.setattr(
            "pypss.core.error_rate_monitor.adaptive_sampler", mock_adaptive_sampler
        )

        # Create ErrorRateMonitor instance, passing the mock collector
        monitor = ErrorRateMonitor(
            collector=mock_file_fifo_collector, interval=0.01, window_size=5
        )

        # Verify registration happened
        mock_file_fifo_collector.register_observer.assert_called_once_with(
            monitor._on_new_trace
        )

        # Simulate adding traces through the mock collector
        # This will trigger monitor._on_new_trace to populate _error_history
        # Since the mock doesn't automatically call observers, we manually call _on_new_trace
        monitor._on_new_trace({"error": False})
        monitor._on_new_trace({"error": True})
        monitor._on_new_trace({"error": False})
        monitor._on_new_trace({"error": True})
        monitor._on_new_trace({"error": False})

        # Now call calculate_and_update_error_rate on the monitor
        monitor._calculate_and_update_error_rate()

        # Assert that adaptive_sampler was updated with the correct error rate (2 errors out of 5)
        mock_adaptive_sampler.update_metrics.assert_called_once_with(
            error_rate=0.4, trace_count=5
        )

        # Ensure unregister is called on stop
        monitor.stop()
        mock_file_fifo_collector.unregister_observer.assert_called_once_with(
            monitor._on_new_trace
        )
