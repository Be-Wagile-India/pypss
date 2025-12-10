import json
import math
from typing import Dict, List

import pandas as pd

from ..cli.discovery import get_module_score_breakdown
from ..core import compute_pss_from_traces
from ..utils.config import GLOBAL_CONFIG
from ..utils.utils import calculate_entropy


class TraceProcessor:
    """
    Processes raw traces into time-series data using Pandas for the dashboard.
    """

    def __init__(self, traces: List[Dict]):
        self.traces = traces
        if not traces:
            self.df = pd.DataFrame()
            return

        self.df = pd.DataFrame(traces)

        if "timestamp" in self.df.columns:
            self.df["datetime"] = pd.to_datetime(self.df["timestamp"], unit="s")
            self.df = self.df.set_index("datetime").sort_index()

    def get_metric_timeseries(self, window_size: str = "1min") -> pd.DataFrame:
        """
        Aggregates metrics into time buckets (TS, MS, EV, BE, CC, PSS).
        """
        if self.df.empty:
            return pd.DataFrame()

        resampler = self.df.resample(window_size)

        def calc_ts_score(durations):
            if len(durations) < 2:
                return 1.0
            mean = durations.mean()
            if mean == 0:
                return 1.0
            cv = durations.std() / mean
            return math.exp(-GLOBAL_CONFIG.alpha * cv)

        def calc_ms_score(mem_diffs):
            if len(mem_diffs) == 0:
                return 1.0
            mean_diff_mb = abs(mem_diffs.mean()) / (1024 * 1024)
            return math.exp(-GLOBAL_CONFIG.gamma * mean_diff_mb)

        def calc_ev_score(errors):
            if len(errors) == 0:
                return 1.0
            error_rate = errors.sum() / len(errors)
            return max(0.0, 1.0 - (error_rate * 5.0))

        def calc_be_score(tags):
            if len(tags) == 0:
                return 1.0
            ent = calculate_entropy(tags.dropna().tolist())
            return max(0.0, 1.0 - (ent / GLOBAL_CONFIG.advisor_entropy_threshold))

        def calc_cc_score(wait_times):
            if len(wait_times) == 0:
                return 1.0
            mean_wait = wait_times.mean()
            return math.exp(-mean_wait / (GLOBAL_CONFIG.concurrency_wait_threshold * 10))

        agg_funcs = {
            "duration": calc_ts_score,
            "memory_diff": calc_ms_score,
            "error": calc_ev_score,
            "branch_tag": calc_be_score,
            "wait_time": calc_cc_score,
        }

        valid_funcs = {k: v for k, v in agg_funcs.items() if k in self.df.columns}

        scores_df = resampler.agg(valid_funcs)  # type: ignore[arg-type]

        col_map = {
            "duration": "ts",
            "memory_diff": "ms",
            "error": "ev",
            "branch_tag": "be",
            "wait_time": "cc",
        }
        scores_df = scores_df.rename(columns=col_map)

        scores_df = scores_df.fillna(1.0)

        scores_df["pss"] = (
            (scores_df.get("ts", 1.0) * GLOBAL_CONFIG.w_ts)
            + (scores_df.get("ms", 1.0) * GLOBAL_CONFIG.w_ms)
            + (scores_df.get("ev", 1.0) * GLOBAL_CONFIG.w_ev)
            + (scores_df.get("be", 1.0) * GLOBAL_CONFIG.w_be)
            + (scores_df.get("cc", 1.0) * GLOBAL_CONFIG.w_cc)
        ) * 100

        return scores_df


def load_trace_data(file_path: str):
    """
    Loads traces and returns structured data for the dashboard.
    Returns: (overall_report, module_df, raw_traces, trace_processor)
    """

    try:
        with open(file_path, "r") as f:
            data = json.load(f)

    except Exception:
        return None, None, None, None

    if not data:
        return None, None, None, None

    if isinstance(data, dict) and "traces" in data:
        traces = data["traces"]
    elif isinstance(data, list):
        traces = data
    elif isinstance(data, dict):
        traces = []
    else:
        traces = []

    overall_report = compute_pss_from_traces(traces)

    module_scores = get_module_score_breakdown(traces)

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

    module_df = pd.DataFrame(df_data)
    if not module_df.empty:
        module_df = module_df.sort_values(by="pss", ascending=True).reset_index(drop=True)

    processor = TraceProcessor(traces)

    return overall_report, module_df, traces, processor
