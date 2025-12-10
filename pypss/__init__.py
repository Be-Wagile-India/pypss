import atexit
from typing import TYPE_CHECKING, Optional

__version__ = "1.3.1"

if TYPE_CHECKING:
    from .core.error_rate_monitor import ErrorRateMonitor
    from .instrumentation.collectors import BaseCollector
    from .tuning.runtime import RuntimeTuner

from .cli.reporting import render_report_json, render_report_text
from .core import StabilityAdvisor, compute_pss_from_traces, generate_advisor_report
from .core.context import add_tag
from .core.error_rate_monitor import _initialize_error_rate_monitor
from .instrumentation import (
    Collector,
    monitor_block,
    monitor_function,
)
from .instrumentation.collectors import _initialize_global_collector
from .tuning.runtime import RuntimeTuner
from .utils.config import GLOBAL_CONFIG, PSSConfig

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
    "add_tag",
]

_global_collector: Optional["BaseCollector"] = None
_error_rate_monitor: Optional["ErrorRateMonitor"] = None
_runtime_tuner: Optional["RuntimeTuner"] = None


def get_global_collector() -> "BaseCollector":
    """Returns the initialized global collector, raising an error if not initialized."""
    if _global_collector is None:
        raise RuntimeError("PyPSS global_collector not initialized. Call init() first.")
    return _global_collector


def get_error_rate_monitor() -> "ErrorRateMonitor":
    """
    Returns the initialized global error rate monitor, raising an error if not
    initialized.
    """
    if _error_rate_monitor is None:
        raise RuntimeError("PyPSS error_rate_monitor not initialized. Call init() first.")
    return _error_rate_monitor


def get_runtime_tuner() -> "RuntimeTuner":
    """Returns the initialized runtime tuner, raising an error if not initialized."""
    if _runtime_tuner is None:
        raise RuntimeError("PyPSS runtime_tuner not initialized. Call init() first.")
    return _runtime_tuner


def init():
    """
    Initializes PyPSS components. This function should be called once at the
    start of your application to ensure all global components are properly set up.
    It is idempotent for external calls, but re-initializes components if called again.
    """
    global _global_collector, _error_rate_monitor, _runtime_tuner

    if _runtime_tuner:
        _runtime_tuner.stop()
        # Explicitly unregister atexit for the old tuner to prevent multiple stops
        # on exit.
        try:
            atexit.unregister(_runtime_tuner.stop)
        except AttributeError:
            # unregister is only available in Python 3.9+ and might fail if not
            # registered.
            pass
    if _error_rate_monitor:
        _error_rate_monitor.stop()

    _initialize_global_collector()
    from .instrumentation.collectors import global_collector as _g_c_mod

    _global_collector = _g_c_mod

    _initialize_error_rate_monitor()
    from .core.error_rate_monitor import error_rate_monitor as _erm_mod

    _error_rate_monitor = _erm_mod

    _runtime_tuner = RuntimeTuner(config=GLOBAL_CONFIG, collector=get_global_collector())
    _runtime_tuner.start()
    atexit.register(_runtime_tuner.stop)
