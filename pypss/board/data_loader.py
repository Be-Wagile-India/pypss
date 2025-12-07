import json
import math
import pandas as pd
from typing import Dict, List

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

        # Convert to DataFrame
        self.df = pd.DataFrame(traces)

        # Ensure timestamp is datetime and set as index
        if "timestamp" in self.df.columns:
            self.df["datetime"] = pd.to_datetime(self.df["timestamp"], unit="s")
            self.df = self.df.set_index("datetime").sort_index()

    def get_metric_timeseries(self, window_size: str = "1min") -> pd.DataFrame:
        """
        Aggregates metrics into time buckets (TS, MS, EV, BE, CC, PSS).
        """
        if self.df.empty:
            return pd.DataFrame()

        # Resample
        resampler = self.df.resample(window_size)

        # 1. Timing Stability (CV of duration)
        def calc_ts_score(durations):
            if len(durations) < 2:
                return 1.0  # Not enough data = stable
            mean = durations.mean()
            if mean == 0:
                return 1.0
            cv = durations.std() / mean
            # Score = exp(-alpha * CV)
            return math.exp(-GLOBAL_CONFIG.alpha * cv)

        # 2. Memory Stability (Mean Memory Diff)
        def calc_ms_score(mem_diffs):
            if len(mem_diffs) == 0:
                return 1.0
            # Score = exp(-gamma * |mean_diff_mb|)
            # Convert bytes to MB for scoring consistency
            mean_diff_mb = abs(mem_diffs.mean()) / (1024 * 1024)
            return math.exp(-GLOBAL_CONFIG.gamma * mean_diff_mb)

        # 3. Error Volatility (Error Rate)
        def calc_ev_score(errors):
            if len(errors) == 0:
                return 1.0
            error_rate = errors.sum() / len(errors)
            # Score = max(0, 1 - (rate * multiplier))
            # Assuming a standard penalty. Using config if available or default logic.
            # Using a simplified linear penalty for the trend line.
            return max(0.0, 1.0 - (error_rate * 5.0))  # 20% error rate = 0 score

        # 4. Branching Entropy
        def calc_be_score(tags):
            if len(tags) == 0:
                return 1.0
            ent = calculate_entropy(tags.dropna().tolist())
            # Normalize: 0 entropy = score 1. High entropy = score 0.
            # Using config threshold
            return max(0.0, 1.0 - (ent / GLOBAL_CONFIG.advisor_entropy_threshold))

        # 5. Concurrency Chaos (Mean Wait Time)
        def calc_cc_score(wait_times):
            if len(wait_times) == 0:
                return 1.0
            mean_wait = wait_times.mean()
            # Score = exp(-wait / threshold)
            # We use a derived threshold or just the raw mean wait for visualization?
            # Let's map it to score for consistency.
            # Using a sensitivity factor (e.g., 10x wait threshold)
            return math.exp(
                -mean_wait / (GLOBAL_CONFIG.concurrency_wait_threshold * 10)
            )

        # Apply aggregations
        agg_funcs = {
            "duration": calc_ts_score,
            "memory_diff": calc_ms_score,
            "error": calc_ev_score,
            "branch_tag": calc_be_score,
            "wait_time": calc_cc_score,
        }

        # We must handle missing columns if traces don't have them
        valid_funcs = {k: v for k, v in agg_funcs.items() if k in self.df.columns}

        # Calculate raw scores per bucket
        # mypy has trouble with mixed agg funcs returning different types or taking different types
        scores_df = resampler.agg(valid_funcs)  # type: ignore[arg-type]

        # Rename columns for clarity
        col_map = {
            "duration": "ts",
            "memory_diff": "ms",
            "error": "ev",
            "branch_tag": "be",
            "wait_time": "cc",
        }
        scores_df = scores_df.rename(columns=col_map)

        # Fill NaNs for empty intervals (idle time = perfect stability)
        scores_df = scores_df.fillna(1.0)

        # Calculate Overall PSS
        # PSS = Weighted Sum * 100
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

    # Handle full report format (dict) vs raw traces (list)
    if isinstance(data, dict) and "traces" in data:
        traces = data["traces"]
    elif isinstance(data, list):
        traces = data
    elif isinstance(data, dict):
        # Unknown dict format, or empty report
        return None, None, None, None
    else:
        traces = []

    # 1. Overall Score
    overall_report = compute_pss_from_traces(traces)

    # 2. Module Breakdown
    module_scores = get_module_score_breakdown(traces)

    # Convert to Pandas DataFrame for easy plotting (Module Summary)
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
        # Sort modules by PSS score, worst first
        module_df = module_df.sort_values(by="pss", ascending=True).reset_index(
            drop=True
        )

    # 3. Trace Processor
    processor = TraceProcessor(traces)

    return overall_report, module_df, traces, processor
