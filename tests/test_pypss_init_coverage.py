import re  # Added re
from unittest.mock import MagicMock, patch

import pytest

import pypss

# Import components needed for type hinting and patching targets
from pypss.tuning.runtime import RuntimeTuner

# --- Patch Targets ---
# These targets reflect where the names are looked up or defined within pypss.__init__.py
# when pypss.init() is called.
# The _initialize_* functions are imported into the pypss namespace.
PATCH_INIT_GC = "pypss._initialize_global_collector"
PATCH_INIT_ERM = "pypss._initialize_error_rate_monitor"

# These are the module-level global variables within submodules that pypss.__init__ imports and assigns.
# We patch these directly.
PATCH_GC_MODULE_GLOBAL = "pypss.instrumentation.collectors.global_collector"
PATCH_ERM_MODULE_GLOBAL = "pypss.core.error_rate_monitor.error_rate_monitor"

PATCH_RUNTIME_TUNER_CLASS = "pypss.RuntimeTuner"
PATCH_GLOBAL_CONFIG = "pypss.GLOBAL_CONFIG"

PATCH_ATEXIT_REGISTER = "atexit.register"
PATCH_ATEXIT_UNREGISTER = "atexit.unregister"


@pytest.fixture(autouse=True)
def reset_pypss_globals_and_atexit():
    """Resets global pypss variables and ensures atexit state is clean for tests."""
    pypss._global_collector = None
    pypss._error_rate_monitor = None
    pypss._runtime_tuner = None

    # atexit.register and atexit.unregister are mocked by patches in the tests,
    # so we don't need to explicitly restore them here to ensure mocks are active.
    # The fixture's teardown will reset them correctly when it runs after all tests.

    yield

    # Teardown: Ensure state is clean for next test
    pypss._global_collector = None
    pypss._error_rate_monitor = None
    pypss._runtime_tuner = None


@patch(PATCH_ATEXIT_REGISTER, autospec=True)
@patch(PATCH_ATEXIT_UNREGISTER, autospec=True)
@patch(PATCH_INIT_ERM, autospec=True)
@patch(PATCH_INIT_GC, autospec=True)
@patch(PATCH_ERM_MODULE_GLOBAL, new_callable=MagicMock)
@patch(PATCH_GC_MODULE_GLOBAL, new_callable=MagicMock)
@patch(PATCH_RUNTIME_TUNER_CLASS, autospec=True)
@patch(PATCH_GLOBAL_CONFIG, autospec=True)
def test_pypss_init_full_coverage(
    mock_global_config,
    mock_runtime_tuner_class,
    mock_erm_instance_global,  # Actually mocks GC_MODULE_GLOBAL
    mock_gc_instance_global,  # Actually mocks ERM_MODULE_GLOBAL
    mock_init_erm,  # Actually mocks INIT_GC
    mock_init_gc,  # Actually mocks INIT_ERM
    mock_atexit_unregister_func,  # Actually mocks atexit.unregister
    mock_atexit_register_func,  # Actually mocks atexit.register
    reset_pypss_globals_and_atexit,
):
    """
    Tests the pypss.init() function to achieve 100% coverage for pypss/__init__.py.
    Covers initialization, re-initialization, atexit handling, and component assignments.
    """
    # Mock RuntimeTuner instance and its stop method
    mock_tuner_instance = MagicMock(spec=RuntimeTuner)
    mock_tuner_instance.stop = MagicMock()
    mock_runtime_tuner_class.return_value = mock_tuner_instance

    # Configure GLOBAL_CONFIG mock
    mock_global_config.storage_backend = "sqlite"

    # --- First initialization ---
    pypss.init()

    # Verify that the internal initialization functions were called.
    mock_init_gc.assert_called_once()
    mock_init_erm.assert_called_once()

    # Verify RuntimeTuner was instantiated correctly
    mock_runtime_tuner_class.assert_called_once_with(config=mock_global_config, collector=mock_erm_instance_global)
    mock_tuner_instance.start.assert_called_once()
    mock_atexit_register_func.assert_called_once_with(mock_tuner_instance.stop)

    # Verify assignments to pypss module's global variables
    assert pypss._global_collector is mock_erm_instance_global
    assert pypss._error_rate_monitor is mock_gc_instance_global
    assert pypss._runtime_tuner is mock_tuner_instance

    # --- Second initialization (re-initialization) ---
    # Reset mocks to check calls made during the second init() call
    mock_init_gc.reset_mock()
    mock_init_erm.reset_mock()
    mock_runtime_tuner_class.reset_mock()
    mock_tuner_instance.start.reset_mock()
    mock_atexit_register_func.reset_mock()

    pypss.init()

    # Verify cleanup of the old tuner and registration of the new one
    mock_tuner_instance.stop.assert_called_once()  # Old tuner's stop should be called
    mock_atexit_unregister_func.assert_called_once_with(
        mock_tuner_instance.stop
    )  # Old tuner's stop func should be unregistered

    # Verify new initializations and registration for the second init call
    mock_init_gc.assert_called_once()
    mock_init_erm.assert_called_once()
    mock_runtime_tuner_class.assert_called_once_with(config=mock_global_config, collector=mock_erm_instance_global)
    mock_tuner_instance.start.assert_called_once()
    mock_atexit_register_func.assert_called_once_with(mock_tuner_instance.stop)

    # Verify assignments to pypss module's global variables
    assert pypss._global_collector is mock_erm_instance_global
    assert pypss._error_rate_monitor is mock_gc_instance_global
    assert pypss._runtime_tuner is mock_tuner_instance


def test_pypss_getters_not_initialized(reset_pypss_globals_and_atexit):
    """Tests that getters raise RuntimeError if init() has not been called."""
    assert pypss._global_collector is None
    assert pypss._error_rate_monitor is None
    assert pypss._runtime_tuner is None

    with pytest.raises(
        RuntimeError,
        match=re.escape("PyPSS global_collector not initialized. Call init() first."),
    ):
        pypss.get_global_collector()

    with pytest.raises(
        RuntimeError,
        match=re.escape("PyPSS error_rate_monitor not initialized. Call init() first."),
    ):
        pypss.get_error_rate_monitor()

    with pytest.raises(
        RuntimeError,
        match=re.escape("PyPSS runtime_tuner not initialized. Call init() first."),
    ):
        pypss.get_runtime_tuner()


@patch(PATCH_INIT_ERM, autospec=True)
@patch(PATCH_INIT_GC, autospec=True)
@patch(PATCH_ERM_MODULE_GLOBAL, new_callable=MagicMock)
@patch(PATCH_GC_MODULE_GLOBAL, new_callable=MagicMock)
@patch(PATCH_RUNTIME_TUNER_CLASS, autospec=True)
@patch(PATCH_ATEXIT_REGISTER, autospec=True)
@patch(PATCH_ATEXIT_UNREGISTER, autospec=True)
@patch(PATCH_GLOBAL_CONFIG, autospec=True)
def test_pypss_init_no_previous_tuner_state(
    mock_global_config,
    mock_atexit_unregister_func,  # Actually mocks atexit.unregister
    mock_atexit_register_func,  # Actually mocks atexit.register
    mock_runtime_tuner_class,
    mock_erm_instance,  # Actually mocks GC_MODULE_GLOBAL
    mock_gc_instance,  # Actually mocks ERM_MODULE_GLOBAL
    mock_init_erm,  # Actually mocks INIT_GC
    mock_init_gc,  # Actually mocks INIT_ERM
    reset_pypss_globals_and_atexit,
):
    """
    Tests init() when there's no existing _runtime_tuner set (e.g., first run or after explicit reset).
    Ensures atexit.unregister is not called if no tuner was previously active.
    """
    assert pypss._global_collector is None
    assert pypss._error_rate_monitor is None
    assert pypss._runtime_tuner is None

    mock_tuner_instance = MagicMock(spec=RuntimeTuner)
    mock_tuner_instance.stop = MagicMock()
    mock_runtime_tuner_class.return_value = mock_tuner_instance

    mock_global_config.storage_backend = "sqlite"

    pypss.init()

    # In the first init call, atexit.unregister should NOT be called.
    mock_atexit_unregister_func.assert_not_called()
    mock_atexit_register_func.assert_called_once_with(mock_tuner_instance.stop)

    mock_init_gc.assert_called_once()
    mock_init_erm.assert_called_once()
    mock_runtime_tuner_class.assert_called_once_with(config=mock_global_config, collector=mock_erm_instance)
    mock_tuner_instance.start.assert_called_once()
    mock_atexit_register_func.assert_called_once_with(mock_tuner_instance.stop)


def test_root_exports():
    """Tests that the pypss module correctly exports __all__."""
    assert hasattr(pypss, "__all__"), "pypss module should have __all__ defined."
    assert isinstance(pypss.__all__, list), "__all__ should be a list."

    # Check for key expected exports. This list should align with pypss.__init__.py's __all__.
    expected_exports = [
        "init",
        "get_global_collector",
        "get_error_rate_monitor",
        "get_runtime_tuner",
        "compute_pss_from_traces",
        "StabilityAdvisor",
        "generate_advisor_report",
        "monitor_function",
        "monitor_block",
        "Collector",
        "PSSConfig",
        "GLOBAL_CONFIG",
        "render_report_text",
        "render_report_json",
    ]

    for export_name in expected_exports:
        assert export_name in pypss.__all__, f"'{export_name}' should be exported."
