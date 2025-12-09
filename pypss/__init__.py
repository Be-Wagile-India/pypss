import atexit
from typing import Optional, TYPE_CHECKING  # Import TYPE_CHECKING

# Forward references for type hinting to avoid circular imports during module load
if TYPE_CHECKING:
    from .instrumentation.collectors import BaseCollector
    from .core.error_rate_monitor import ErrorRateMonitor
    from .tuning.runtime import RuntimeTuner

from .instrumentation.collectors import _initialize_global_collector
from .core.error_rate_monitor import _initialize_error_rate_monitor
from .utils.config import PSSConfig, GLOBAL_CONFIG

from .core import compute_pss_from_traces, StabilityAdvisor, generate_advisor_report
from .instrumentation import (
    monitor_function,
    monitor_block,
    Collector,
)
from .cli.reporting import render_report_text, render_report_json
from .tuning.runtime import RuntimeTuner  # Import RuntimeTuner


__all__ = [
    "init",
    "get_global_collector",
    "get_error_rate_monitor",
    "get_runtime_tuner",
    "PSSConfig",
    "GLOBAL_CONFIG",
    "compute_pss_from_traces",
    "StabilityAdvisor",
    "generate_advisor_report",
    "monitor_function",
    "monitor_block",
    "Collector",
    "render_report_text",
    "render_report_json",
    "RuntimeTuner",
]

# Internal global variables, accessed via getters after pypss.init()
_global_collector: Optional["BaseCollector"] = None
_error_rate_monitor: Optional["ErrorRateMonitor"] = None
_runtime_tuner: Optional["RuntimeTuner"] = None


def get_global_collector() -> "BaseCollector":
    """Returns the initialized global collector, raising an error if not initialized."""
    if _global_collector is None:
        raise RuntimeError(
            "PyPSS global_collector not initialized. Call pypss.init() first."
        )
    return _global_collector


def get_error_rate_monitor() -> "ErrorRateMonitor":
    """Returns the initialized global error rate monitor, raising an error if not initialized."""
    if _error_rate_monitor is None:
        raise RuntimeError(
            "PyPSS error_rate_monitor not initialized. Call pypss.init() first."
        )
    return _error_rate_monitor


def get_runtime_tuner() -> "RuntimeTuner":
    """Returns the initialized runtime tuner, raising an error if not initialized."""
    if _runtime_tuner is None:
        raise RuntimeError(
            "PyPSS runtime_tuner not initialized. Call pypss.init() first."
        )
    return _runtime_tuner


def init():
    """
    Initializes PyPSS components. This function should be called once at the
    start of your application to ensure all global components are properly set up.
    It is idempotent for external calls, but re-initializes components if called again.
    """
    global _global_collector, _error_rate_monitor, _runtime_tuner

    # If already initialized, stop existing components before re-initializing
    if _runtime_tuner:
        _runtime_tuner.stop()
        # Explicitly unregister atexit for the old tuner to prevent multiple stops on exit
        try:
            atexit.unregister(_runtime_tuner.stop)
        except AttributeError:
            # unregister is only available in Python 3.9+ and might fail if not registered
            pass
    if _error_rate_monitor:
        _error_rate_monitor.stop()

    # 1. Initialize global collector in its module
    _initialize_global_collector()
    # 2. Set the _global_collector in this pypss module from the one just initialized
    from .instrumentation.collectors import global_collector as _g_c_mod

    _global_collector = _g_c_mod

    # 3. Now initialize error rate monitor, which can now safely call pypss.get_global_collector()
    _initialize_error_rate_monitor()
    # 4. Set the _error_rate_monitor in this pypss module
    from .core.error_rate_monitor import error_rate_monitor as _erm_mod

    _error_rate_monitor = _erm_mod

    # 5. Initialize and start RuntimeTuner
    # It can now safely call pypss.get_global_collector()
    _runtime_tuner = RuntimeTuner(
        config=GLOBAL_CONFIG, collector=get_global_collector()
    )
    _runtime_tuner.start()
    atexit.register(_runtime_tuner.stop)  # Ensure tuner is stopped on exit


# TODO: Add tests in a dedicated test file (e.g., tests/test_pypss_init_coverage.py) to cover the following:
# - Re-initialization of pypss.init() to test atexit.unregister (line 33).
# - Assignment of _global_collector (line 42), _error_rate_monitor (line 51), and RuntimeTuner instantiation (lines 71-73) under various initialization conditions.
# - Edge cases for get_global_collector, get_error_rate_monitor, and get_runtime_tuner when not initialized.
