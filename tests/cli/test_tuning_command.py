import json
import os
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from pypss.cli.tuning import tune
from pypss.utils.config import PSSConfig


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def mock_traces_file(tmp_path):
    """Creates a dummy trace file for testing."""
    traces = [
        {"timestamp": 1, "module": "mod1", "metric": {"latency": 0.1, "memory": 100}},
        {"timestamp": 2, "module": "mod1", "metric": {"latency": 0.2, "memory": 150}},
    ]
    file_path = tmp_path / "baseline_traces.json"
    with open(file_path, "w") as f:
        json.dump(traces, f)
    return file_path


@pytest.fixture
def mock_empty_traces_file(tmp_path):
    """Creates an empty trace file for testing."""
    file_path = tmp_path / "empty_traces.json"
    with open(file_path, "w") as f:
        json.dump([], f)
    return file_path


@pytest.fixture
def mock_profiler():
    """Mocks the Profiler class."""
    with patch("pypss.cli.tuning.Profiler") as MockProfiler:
        instance = MockProfiler.return_value
        instance.profile.return_value = MagicMock(
            latency_p95=0.15,
            latency_p99=0.18,
            memory_mean=125,
            error_rate=0.0,
        )
        yield MockProfiler


@pytest.fixture
def mock_injector():
    """Mocks the FaultInjector class."""
    with patch("pypss.cli.tuning.FaultInjector") as MockInjector:
        instance = MockInjector.return_value
        # Return dummy traces for each injection method
        instance.inject_latency_jitter.return_value = ["trace_lat_1"]
        instance.inject_memory_leak.return_value = ["trace_mem_1"]
        instance.inject_error_burst.return_value = ["trace_err_1"]
        instance.inject_thread_starvation.return_value = ["trace_thr_1"]
        yield MockInjector


@pytest.fixture
def mock_optimizer():
    """Mocks the ConfigOptimizer class."""
    with patch("pypss.cli.tuning.ConfigOptimizer") as MockOptimizer:
        instance = MockOptimizer.return_value
        mock_config = PSSConfig(
            alpha=0.5,
            beta=0.5,
            gamma=0.5,
            mem_spike_threshold_ratio=1.5,
            concurrency_wait_threshold=0.01,
        )
        instance.optimize.return_value = (mock_config, 0.1)  # (best_config, best_loss)
        yield MockOptimizer


class TestTuneCommand:
    def test_tune_success(
        self,
        runner,
        mock_traces_file,
        mock_profiler,
        mock_injector,
        mock_optimizer,
        tmp_path,
    ):
        output_file = tmp_path / "test_tuned.toml"
        result = runner.invoke(
            tune,
            [
                "--baseline",
                str(mock_traces_file),
                "--output",
                str(output_file),
                "--iterations",
                "10",
            ],
        )

        assert result.exit_code == 0
        assert "Optimization Complete!" in result.output
        assert "Saving configuration to" in result.output
        assert os.path.exists(output_file)

        mock_profiler.assert_called_once_with(
            [
                {
                    "timestamp": 1,
                    "module": "mod1",
                    "metric": {"latency": 0.1, "memory": 100},
                },
                {
                    "timestamp": 2,
                    "module": "mod1",
                    "metric": {"latency": 0.2, "memory": 150},
                },
            ]
        )
        mock_profiler.return_value.profile.assert_called_once()
        mock_injector.assert_called_once_with(
            [
                {
                    "timestamp": 1,
                    "module": "mod1",
                    "metric": {"latency": 0.1, "memory": 100},
                },
                {
                    "timestamp": 2,
                    "module": "mod1",
                    "metric": {"latency": 0.2, "memory": 150},
                },
            ]
        )
        mock_injector.return_value.inject_latency_jitter.assert_called_once()
        mock_injector.return_value.inject_memory_leak.assert_called_once()
        mock_injector.return_value.inject_error_burst.assert_called_once()
        mock_injector.return_value.inject_thread_starvation.assert_called_once()

        faulty_map = {
            "latency_jitter": ["trace_lat_1"],
            "memory_leak": ["trace_mem_1"],
            "error_burst": ["trace_err_1"],
            "thread_starvation": ["trace_thr_1"],
        }
        mock_optimizer.assert_called_once_with(
            [
                {
                    "timestamp": 1,
                    "module": "mod1",
                    "metric": {"latency": 0.1, "memory": 100},
                },
                {
                    "timestamp": 2,
                    "module": "mod1",
                    "metric": {"latency": 0.2, "memory": 150},
                },
            ],
            faulty_map,
        )
        mock_optimizer.return_value.optimize.assert_called_once_with(iterations=10)

        # Check content of the output file (simplified check)
        with open(output_file, "r") as f:
            content = f.read()
            assert "alpha = 0.5" in content
            assert "beta = 0.5" in content
            assert "gamma = 0.5" in content
            assert "mem_spike_threshold_ratio = 1.5" in content
            assert "concurrency_wait_threshold = 0.01" in content

    def test_tune_baseline_not_found(self, runner, tmp_path):
        non_existent_file = tmp_path / "non_existent.json"
        result = runner.invoke(tune, ["--baseline", str(non_existent_file)])
        assert result.exit_code == 2  # click's error for missing file
        assert "Error: Invalid value for '--baseline'" in result.output

    def test_tune_empty_baseline_traces(
        self,
        runner,
        mock_empty_traces_file,
        mock_profiler,
        mock_injector,
        mock_optimizer,
    ):
        result = runner.invoke(tune, ["--baseline", str(mock_empty_traces_file)])
        assert result.exit_code == 1
        assert "No traces found in baseline file. Cannot tune." in result.output
        mock_profiler.assert_not_called()
        mock_injector.assert_not_called()
        mock_optimizer.assert_not_called()

    def test_tune_baseline_with_errors_warning(
        self,
        runner,
        mock_traces_file,
        mock_profiler,
        mock_injector,
        mock_optimizer,
        tmp_path,
    ):
        # Configure profiler to return a high error rate
        mock_profiler.return_value.profile.return_value = MagicMock(
            latency_p95=0.15,
            latency_p99=0.18,
            memory_mean=125,
            error_rate=0.06,  # > 0.05
        )
        output_file = tmp_path / "test_tuned_error_warning.toml"
        result = runner.invoke(
            tune,
            [
                "--baseline",
                str(mock_traces_file),
                "--output",
                str(output_file),
                "--iterations",
                "10",
            ],
        )

        assert result.exit_code == 0
        assert "Warning: Baseline has > 5% errors. Tuning might be inaccurate." in result.output
        assert os.path.exists(output_file)

    def test_tune_default_output_file(self, runner, mock_traces_file, mock_profiler, mock_injector, mock_optimizer):
        # Run without specifying --output, should default to pypss_tuned.toml in current dir
        with runner.isolated_filesystem():
            result = runner.invoke(
                tune,
                ["--baseline", str(mock_traces_file), "--iterations", "10"],
            )
            assert result.exit_code == 0
            assert os.path.exists("pypss_tuned.toml")
            assert "Saving configuration to pypss_tuned.toml" in result.output
