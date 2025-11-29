import json
import pandas as pd
from ..cli.discovery import get_module_score_breakdown
from ..core import compute_pss_from_traces


def load_trace_data(file_path: str):
    """


    Loads traces and returns structured data for the dashboard.


    """

    try:
        with open(file_path, "r") as f:
            data = json.load(f)

    except Exception:
        return None, None, None

    if not data:
        return None, None, None

    # Handle full report format (dict) vs raw traces (list)

    if isinstance(data, dict) and "traces" in data:
        traces = data["traces"]

    elif isinstance(data, list):
        traces = data

    elif isinstance(data, dict):
        # Unknown dict format, or empty report

        return None, None, None

    else:
        traces = []

    # 1. Overall Score

    overall_report = compute_pss_from_traces(traces)

    # 2. Module Breakdown

    module_scores = get_module_score_breakdown(traces)

    # Convert to Pandas DataFrame for easy plotting
    df_data = []
    for mod, score in module_scores.items():
        df_data.append(
            {
                "module": mod,
                "pss": score["pss"],
                "timing": score["breakdown"]["timing_stability"],
                "memory": score["breakdown"]["memory_stability"],
                "errors": score["breakdown"]["error_volatility"],
                "traces": len([t for t in traces if mod in t.get("name", "")]),
            }
        )

    df = pd.DataFrame(df_data)

    # Sort modules by PSS score, worst first
    df = df.sort_values(by="pss", ascending=True).reset_index(drop=True)

    return overall_report, df, traces
