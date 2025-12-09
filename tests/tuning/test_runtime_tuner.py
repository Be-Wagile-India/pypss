import pytest
import time
import os

import pypss  # Add this import
from pypss import (
    init,
    GLOBAL_CONFIG,
    monitor_function,
)
from pypss.tuning.runtime import RuntimeBaselineState, RuntimeTuner
from pypss.utils.config import PSSConfig  # For fresh config in fixture


@pytest.fixture(autouse=True)
def cleanup_runtime_state_and_reset_config():
    """Ensure a clean runtime state and GLOBAL_CONFIG for each test."""
    state_file = RuntimeBaselineState()._file_path
    if os.path.exists(state_file):
        os.remove(state_file)

    # Backup original GLOBAL_CONFIG state
    original_config_state = GLOBAL_CONFIG.__dict__.copy()

    # Create a fresh PSSConfig instance for each test
    # This ensures no carry-over of changes to GLOBAL_CONFIG
    GLOBAL_CONFIG.__dict__.clear()
    GLOBAL_CONFIG.__dict__.update(
        PSSConfig().__dict__
    )  # Reinitialize GLOBAL_CONFIG with defaults

    yield  # Run the test

    # Restore original GLOBAL_CONFIG state after the test
    GLOBAL_CONFIG.__dict__.clear()
    GLOBAL_CONFIG.__dict__.update(original_config_state)

    if os.path.exists(state_file):
        os.remove(state_file)

    # Stop the tuner if it was started
    # Use pypss.get_runtime_tuner()
    try:
        tuner = pypss.get_runtime_tuner()
        if tuner and tuner._thread and tuner._thread.is_alive():
            tuner.stop()
    except RuntimeError:  # Tuner might not have been initialized in some test paths
        pass


def test_runtime_tuner_initialization():
    """Test that the RuntimeTuner initializes correctly."""
    # Ensure global_collector is initialized before RuntimeTuner
    init()
    tuner = pypss.get_runtime_tuner()
    assert tuner is not None
    assert isinstance(tuner, RuntimeTuner)
    assert (
        tuner.state.concurrency_wait_threshold == PSSConfig().concurrency_wait_threshold
    )


def test_runtime_tuner_updates_threshold(monkeypatch):  # Add monkeypatch
    """Test that RuntimeTuner adjusts the concurrency_wait_threshold."""
    init()
    tuner = pypss.get_runtime_tuner()
    assert tuner is not None

    # Reduce tuning interval and min samples for faster test execution
    monkeypatch.setattr(tuner, "_tuning_interval", 0.1)  # Set to 0.1 seconds
    monkeypatch.setattr(tuner, "_min_samples_for_tuning", 5)  # Set to a small number

    initial_threshold = GLOBAL_CONFIG.concurrency_wait_threshold

    # Simulate enough traces with consistent wait_times to trigger tuning
    sample_wait_time = 0.1  # A higher wait time
    for i in range(tuner._min_samples_for_tuning + 10):
        # Add a trace directly to the global_collector
        # The _on_new_trace observer will pick it up
        pypss.get_global_collector().add_trace(
            {
                "trace_id": f"test-{i}",
                "name": "test_op",
                "duration": 0.01,
                "wait_time": sample_wait_time,
                "error": False,
                "timestamp": time.time(),
            }
        )
        time.sleep(0.001)  # Simulate some time passing

    # Explicitly trigger tuning instead of waiting for background thread
    tuner._tune_parameters()  # Call directly

    # Assert that the threshold has been updated
    assert GLOBAL_CONFIG.concurrency_wait_threshold != initial_threshold
    assert (
        GLOBAL_CONFIG.concurrency_wait_threshold > initial_threshold
    )  # Should increase

    # Also check that the state was saved
    loaded_state = RuntimeBaselineState.load()
    assert (
        loaded_state.concurrency_wait_threshold
        == GLOBAL_CONFIG.concurrency_wait_threshold
    )

    tuner.stop()  # Manually stop the tuner for clean shutdown


# Test with an actual monitored function
def test_runtime_tuner_with_monitor_function(
    monkeypatch,
):  # Add monkeypatch as argument
    init()
    tuner = pypss.get_runtime_tuner()
    assert tuner is not None

    # Reduce tuning interval for faster test execution
    monkeypatch.setattr(tuner, "_tuning_interval", 0.1)  # Set to 0.1 seconds
    monkeypatch.setattr(tuner, "_min_samples_for_tuning", 5)  # Set to a small number

    initial_threshold = GLOBAL_CONFIG.concurrency_wait_threshold

    # Use a monitored function to generate traces
    @monitor_function("monitored_op")
    def monitored_operation(sleep_duration):
        time.sleep(sleep_duration)  # Simulate some work and create wait_time

    sample_wait_time = 0.08
    sleep_duration_for_test = sample_wait_time * 2  # To ensure a high wait time

    for _ in range(tuner._min_samples_for_tuning + 10):
        monitored_operation(sleep_duration_for_test)
        # No sleep needed here, traces are collected by the end of monitored_operation

    # Explicitly trigger tuning instead of waiting for background thread
    tuner._tune_parameters()

    # ... (rest of the test)

    # Assert that the threshold has been updated
    assert GLOBAL_CONFIG.concurrency_wait_threshold != initial_threshold
    assert GLOBAL_CONFIG.concurrency_wait_threshold > initial_threshold

    # Assert that the collected traces actually have the expected wait_time
    # This ensures the decorator is working as expected
    traces = pypss.get_global_collector().get_traces()
    assert len(traces) > 0
    # The wait_time is approximated by the decorator, so we check a range
    first_trace_wait_time = traces[0]["wait_time"]
    assert first_trace_wait_time >= sleep_duration_for_test * 0.9
    assert first_trace_wait_time <= sleep_duration_for_test * 1.75

    tuner.stop()
