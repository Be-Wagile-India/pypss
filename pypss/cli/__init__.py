from .cli import main
from .discovery import CodebaseDiscoverer, get_module_score_breakdown
from .reporting import render_report_json, render_report_text
from .runner import AutoInstrumentor, run_with_instrumentation

__all__ = [
    "main",
    "render_report_text",
    "render_report_json",
    "run_with_instrumentation",
    "AutoInstrumentor",
    "CodebaseDiscoverer",
    "get_module_score_breakdown",
]
