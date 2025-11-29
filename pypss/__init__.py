__version__ = "0.8.0"

from .core import compute_pss_from_traces, StabilityAdvisor, generate_advisor_report
from .instrumentation import (
    monitor_function,
    monitor_block,
    global_collector,
    Collector,
)
from .utils import PSSConfig, GLOBAL_CONFIG
from .cli.reporting import render_report_text, render_report_json

__all__ = [
    "compute_pss_from_traces",
    "StabilityAdvisor",
    "generate_advisor_report",
    "monitor_function",
    "monitor_block",
    "global_collector",
    "Collector",
    "PSSConfig",
    "GLOBAL_CONFIG",
    "render_report_text",
    "render_report_json",
]
