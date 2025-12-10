from unittest.mock import patch

import pandas as pd
import pytest

from pypss.board.data_loader import TraceProcessor, load_trace_data


class TestTraceProcessor:
    @pytest.fixture
    def sample_traces(self):
        base_time = 1600000000.0
        return [
            # Trace 1: Good
            {
                "timestamp": base_time,
                "duration": 0.1,
                "memory_diff": 100,
                "error": False,
                "branch_tag": "A",
                "wait_time": 0.01,
                "name": "func_a",
                "module": "mod_a",
            },
            # Trace 2: Error, Same minute
            {
                "timestamp": base_time + 10,
                "duration": 0.5,  # High duration variation
                "memory_diff": 5000000,  # 5MB spike
                "error": True,
                "branch_tag": "B",
                "wait_time": 1.0,
                "name": "func_b",
                "module": "mod_b",
            },
            # Trace 3: Next minute
            {
                "timestamp": base_time + 61,
                "duration": 0.1,
                "memory_diff": 100,
                "error": False,
                "branch_tag": "A",
                "wait_time": 0.01,
                "name": "func_a",
                "module": "mod_a",
            },
        ]

    def test_init_creates_dataframe(self, sample_traces):
        processor = TraceProcessor(sample_traces)
        assert not processor.df.empty
        assert isinstance(processor.df.index, pd.DatetimeIndex)
        assert len(processor.df) == 3

    def test_init_empty_traces(self):
        processor = TraceProcessor([])
        assert processor.df.empty

    def test_get_metric_timeseries_aggregation(self, sample_traces):
        processor = TraceProcessor(sample_traces)

        # Resample by 1 min. Should have 2 rows (Time 0 and Time 60s)
        df_ts = processor.get_metric_timeseries(window_size="1min")

        assert len(df_ts) == 2

        # Check columns
        expected_cols = ["ts", "ms", "ev", "be", "cc", "pss"]
        for col in expected_cols:
            assert col in df_ts.columns

        # Check Row 1 (Time 0): Contains Trace 1 & 2
        # TS: CV of [0.1, 0.5] -> Mean=0.3, Std~0.28 -> CV~0.93 -> Score < 1
        # MS: Mean of [100, 5000000] ~ 2.5MB -> Score < 1
        # EV: 1 error in 2 -> 50% rate -> Score = 0 (max(0, 1 - 0.5*5))
        row1 = df_ts.iloc[0]
        assert row1["ev"] == 0.0
        assert row1["ts"] < 1.0
        assert row1["ms"] < 1.0

        # Check Row 2 (Time 60): Contains Trace 3
        # Single item -> Perfect scores
        row2 = df_ts.iloc[1]
        assert row2["ts"] == 1.0
        assert row2["ms"] > 0.99  # Tiny memory diff
        assert row2["ev"] == 1.0

    def test_get_metric_timeseries_empty(self):
        processor = TraceProcessor([])
        df = processor.get_metric_timeseries()
        assert df.empty

    def test_missing_columns_handling(self):
        # Traces without some metrics
        traces = [{"timestamp": 1600000000.0, "duration": 0.1}]
        processor = TraceProcessor(traces)
        df_ts = processor.get_metric_timeseries()

        # "duration" exists -> "ts" should exist
        assert "ts" in df_ts.columns
        # "error" missing -> "ev" should NOT be in raw agg, but handled?
        # Our code: valid_funcs = {k:v for k,v in agg_funcs.items() if k in columns}
        # So "ev" won't be in df_ts.
        # But PSS calc uses .get("ev", 1.0). So it works.

        assert "ts" in df_ts.columns
        assert "ev" not in df_ts.columns
        assert "pss" in df_ts.columns

    def test_get_metric_timeseries_duration_zero(self):
        # Traces with zero duration to hit the mean == 0 branch in calc_ts_score
        traces = [
            {
                "timestamp": 1600000000.0,
                "duration": 0.0,
                "memory_diff": 100,
                "error": False,
                "branch_tag": "A",
                "wait_time": 0.0,
            },
            {
                "timestamp": 1600000000.1,
                "duration": 0.0,
                "memory_diff": 100,
                "error": False,
                "branch_tag": "A",
                "wait_time": 0.0,
            },
        ]
        processor = TraceProcessor(traces)
        df_ts = processor.get_metric_timeseries(window_size="1s")
        assert len(df_ts) == 1
        assert df_ts["ts"].iloc[0] == 1.0  # Should be perfect score if mean is 0

    def test_get_metric_timeseries_memory_zero(self):
        # Traces with zero memory to hit mem_median <= conf.score_memory_epsilon branch in calc_ms_score
        traces = [
            {
                "timestamp": 1600000000.0,
                "duration": 0.1,
                "memory_diff": 0,
                "error": False,
                "branch_tag": "A",
                "wait_time": 0.0,
            },
            {
                "timestamp": 1600000000.1,
                "duration": 0.1,
                "memory_diff": 0,
                "error": False,
                "branch_tag": "A",
                "wait_time": 0.0,
            },
        ]
        processor = TraceProcessor(traces)
        df_ts = processor.get_metric_timeseries(window_size="1s")
        assert len(df_ts) == 1
        assert df_ts["ms"].iloc[0] == 1.0  # Should be perfect score if memory_diff is 0


class TestLoadTraceData:
    @patch("builtins.open")
    @patch("json.load")
    @patch("pypss.board.data_loader.compute_pss_from_traces")
    @patch("pypss.board.data_loader.get_module_score_breakdown")
    def test_load_trace_data_success(self, mock_get_mods, mock_compute, mock_json, mock_open):
        mock_json.return_value = {"traces": [{"timestamp": 1, "name": "t1"}]}
        mock_compute.return_value = {"pss": 80}
        mock_get_mods.return_value = {
            "mod1": {
                "pss": 80,
                "breakdown": {
                    "timing_stability": 0.8,
                    "memory_stability": 0.8,
                    "error_volatility": 0.8,
                },
            }
        }

        report, mod_df, traces, processor = load_trace_data("fake.json")

        assert report["pss"] == 80
        assert not mod_df.empty
        assert len(traces) == 1
        assert isinstance(processor, TraceProcessor)
        assert len(processor.traces) == 1

    @patch("builtins.open")
    def test_load_trace_data_file_error(self, mock_open):
        mock_open.side_effect = FileNotFoundError
        res = load_trace_data("missing.json")
        assert res == (None, None, None, None)

    @patch("builtins.open")
    @patch("json.load")
    def test_load_trace_data_json_error(self, mock_json, mock_open):
        mock_json.side_effect = ValueError("Invalid JSON")
        res = load_trace_data("corrupt.json")
        assert res == (None, None, None, None)

    @patch("builtins.open")
    @patch("json.load")
    def test_load_trace_data_empty_or_bad_format(self, mock_json, mock_open):
        # Test empty data
        mock_json.return_value = {}
        res = load_trace_data("empty.json")
        assert res == (None, None, None, None)

        # Test unknown dict format (not "traces" key)
        mock_json.return_value = {"other_key": "value"}
        res = load_trace_data("unknown_dict.json")
        # Should return default empty structure now, not None tuple
        assert res[0]["pss"] == 0
        assert res[1].empty
        assert res[2] == []
        assert res[3] is not None

        # Test empty list (should also return None, None, None, None due to 'if not data' check)
        mock_json.return_value = []
        report, mod_df, traces, processor = load_trace_data("empty_list.json")
        assert report is None
        assert mod_df is None
        assert traces is None
        assert processor is None
