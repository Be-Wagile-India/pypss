import pytest
import time
from unittest import mock
import logging

from pypss.core.error_rate_monitor import ErrorRateMonitor, error_rate_monitor
from pypss.instrumentation.collectors import global_collector, FileFIFOCollector
from pypss.core.adaptive_sampler import adaptive_sampler
from pypss.utils.config import GLOBAL_CONFIG


@pytest.fixture(autouse=True)
def setup_teardown_global_state(monkeypatch):
    """Fixture to reset GLOBAL_CONFIG and global monitor instances before and after each test."""

    # Store original values from global error_rate_monitor
    original_erm_interval = error_rate_monitor.interval
    original_erm_window_size = error_rate_monitor.window_size
    original_erm_collector = error_rate_monitor.collector  # Store original collector

    # Create a fresh ErrorRateMonitor instance for testing
    fresh_error_rate_monitor = ErrorRateMonitor(
        collector=global_collector, interval=0.1, window_size=10
    )

    # Use monkeypatch to replace the global error_rate_monitor instance
    monkeypatch.setattr(
        "pypss.core.error_rate_monitor.error_rate_monitor", fresh_error_rate_monitor
    )

    # Reset global collector
    global_collector.clear()

    # Reset global adaptive_sampler (as it's updated by ErrorRateMonitor)
    adaptive_sampler._current_sample_rate = (
        GLOBAL_CONFIG.sample_rate
    )  # Assuming sample_rate is default
    adaptive_sampler._last_metrics = {
        "lag": 0.0,
        "churn_rate": 0.0,
        "error_rate": 0.0,
    }

    yield  # Run the test

    # Restore original values for global error_rate_monitor
    error_rate_monitor.interval = original_erm_interval
    error_rate_monitor.window_size = original_erm_window_size
    error_rate_monitor.collector = original_erm_collector  # Restore original collector

    # Stop and clear global error_rate_monitor (the original one)
    # The monkeypatched one's stop method should be called by the test if it starts it
    # We still want to stop any potentially running original global instance
    if error_rate_monitor._thread and error_rate_monitor._thread.is_alive():
        error_rate_monitor.stop()  # This calls unregister_observer, sets stop_event, joins thread

    # Clear global collector
    global_collector.clear()

    # Reset global adaptive_sampler
    adaptive_sampler._current_sample_rate = GLOBAL_CONFIG.sample_rate
    adaptive_sampler._last_metrics = {
        "lag": 0.0,
        "churn_rate": 0.0,
        "error_rate": 0.0,
    }


class TestErrorRateMonitor:
    def test_initialization(self):
        monitor = ErrorRateMonitor(collector=global_collector)  # Pass global_collector
        assert monitor.interval == 5.0  # Default if not set by config
        assert monitor.window_size == 100  # Default if not set by config
        assert not monitor._error_history
        assert monitor._thread is None
        assert not monitor._stop_event.is_set()

    def test_start_stop(self):
        monitor = ErrorRateMonitor(collector=global_collector)  # Pass global_collector
        monitor.start()
        assert monitor._thread is not None
        assert monitor._thread.is_alive()
        monitor.stop()
        if monitor._thread:  # Guard against NoneType
            monitor._thread.join(timeout=1)
            assert not monitor._thread.is_alive()
        assert monitor._stop_event.is_set()

    def test_start_already_running(self, caplog):
        monitor = ErrorRateMonitor(collector=global_collector)  # Pass global_collector
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
        # Mock adaptive_sampler to check if update_metrics is called
        mock_adaptive_sampler = mock.Mock(spec=adaptive_sampler)
        monkeypatch.setattr(
            "pypss.core.error_rate_monitor.adaptive_sampler", mock_adaptive_sampler
        )

        monitor = ErrorRateMonitor(
            collector=global_collector, interval=0.01, window_size=5
        )  # Pass global_collector

        # Add traces to global_collector to trigger _on_new_trace callback
        global_collector.clear()  # Ensure clean state before adding
        for _ in range(5):
            global_collector.add_trace({"error": False})  # Add 5 non-error traces

        monitor._calculate_and_update_error_rate()

        mock_adaptive_sampler.update_metrics.assert_called_once_with(
            error_rate=0.0, trace_count=5
        )

    def test_error_rate_calculation_some_errors(self, monkeypatch):
        mock_adaptive_sampler = mock.Mock(spec=adaptive_sampler)
        monkeypatch.setattr(
            "pypss.core.error_rate_monitor.adaptive_sampler", mock_adaptive_sampler
        )

        monitor = ErrorRateMonitor(
            collector=global_collector, interval=0.01, window_size=5
        )  # Pass global_collector

        # Add traces to global_collector to trigger _on_new_trace callback
        # Use the actual global_collector, which will notify the monitor
        global_collector.clear()  # Ensure clean state before adding
        for _ in range(3):
            global_collector.add_trace({"error": False})
        for _ in range(2):
            global_collector.add_trace({"error": True})

        monitor._calculate_and_update_error_rate()

        mock_adaptive_sampler.update_metrics.assert_called_once_with(
            error_rate=0.4, trace_count=5
        )  # 2 errors out of 5 traces

    def test_error_rate_calculation_all_errors(self, monkeypatch):
        mock_adaptive_sampler = mock.Mock(spec=adaptive_sampler)
        monkeypatch.setattr(
            "pypss.core.error_rate_monitor.adaptive_sampler", mock_adaptive_sampler
        )

        monitor = ErrorRateMonitor(
            collector=global_collector, interval=0.01, window_size=5
        )  # Pass global_collector

        # Add traces to global_collector to trigger _on_new_trace callback
        global_collector.clear()  # Ensure clean state before adding
        for _ in range(5):  # Add 5 errors to fill the window
            global_collector.add_trace({"error": True})

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

        monitor = ErrorRateMonitor(
            collector=global_collector, interval=0.05, window_size=10
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
