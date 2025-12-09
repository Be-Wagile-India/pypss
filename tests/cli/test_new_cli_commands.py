import click
import json
import os
import sys
from unittest.mock import patch, MagicMock
from click.testing import CliRunner
from datetime import datetime, timedelta

# Ensure project root is in sys.path for module discovery
sys.path.insert(0, os.path.abspath("."))

from pypss.cli.cli import ml_detect, history, analyze  # Import analyze command
from pypss.storage.sqlite import SQLiteStorage

# Define a test group for CLI commands
cli_test_group = click.Group()

# ...

cli_test_group.add_command(ml_detect)
cli_test_group.add_command(history)
cli_test_group.add_command(analyze)  # Add analyze command


class TestNewCLICoammnds:
    def setup_method(self, method):
        self.runner = CliRunner()
        # Use a temporary file for the database, specific to each test method
        self.temp_db_path = f"{method.__name__}.db"

    def teardown_method(self):
        # Clean up the temporary database file
        if os.path.exists(self.temp_db_path):
            os.remove(self.temp_db_path)
        pass

    # --- ml_detect command tests ---
    def test_ml_detect_invalid_file_path(self, tmp_path):
        non_existent_file = tmp_path / "non_existent.json"
        result = self.runner.invoke(
            ml_detect,  # Use ml_detect directly
            [
                "--baseline-file",
                str(non_existent_file),
                "--target-file",
                str(non_existent_file),
            ],
        )
        assert result.exit_code == 2  # Click's error for non-existent path
        assert "Error: Invalid value for '--baseline-file'" in result.output

    def test_ml_detect_no_baseline_traces(self, tmp_path):
        baseline_file = tmp_path / "baseline.json"
        target_file = tmp_path / "target.json"
        with open(baseline_file, "w") as f:
            f.write("{invalid json")  # Malformed JSON
        with open(target_file, "w") as f:
            json.dump([{"duration": 1.0}], f)

        result = self.runner.invoke(
            ml_detect,
            [
                "--baseline-file",
                str(baseline_file),
                "--target-file",
                str(target_file),
            ],
        )
        assert result.exit_code == 1
        assert (
            "Error reading trace file: lexical error: invalid char in json text."
            in result.output
        )

    def test_ml_detect_no_target_traces(self, tmp_path):
        baseline_file = tmp_path / "baseline.json"
        target_file = tmp_path / "target.json"
        with open(baseline_file, "w") as f:
            json.dump([{"duration": 1.0}], f)
        with open(target_file, "w") as f:
            json.dump([], f)  # Empty target

        with patch("pypss.cli.cli.PatternDetector") as mock_detector:
            mock_instance = MagicMock()
            mock_detector.return_value = mock_instance
            result = self.runner.invoke(
                ml_detect,  # Use ml_detect directly
                [
                    "--baseline-file",
                    str(baseline_file),
                    "--target-file",
                    str(target_file),
                ],
            )
            assert result.exit_code == 0
            assert (
                "No traces found in target file. Nothing to analyze." in result.output
            )
            mock_detector.assert_called_once()
            mock_instance.fit.assert_called_once()

    @patch(
        "pypss.ml.detector.IsolationForest",
        side_effect=ImportError("No module named 'sklearn.ensemble._isolation_forest'"),
    )
    def test_ml_detect_scikit_learn_missing(self, mock_isolation_forest, tmp_path):
        baseline_file = tmp_path / "baseline.json"
        target_file = tmp_path / "target.json"
        with open(baseline_file, "w") as f:
            json.dump([{"duration": 1.0}], f)
        with open(target_file, "w") as f:
            json.dump([{"duration": 1.0}], f)

        result = self.runner.invoke(
            ml_detect,  # Use ml_detect directly
            [
                "--baseline-file",
                str(baseline_file),
                "--target-file",
                str(target_file),
            ],
        )
        assert result.exit_code == 1
        assert "Please install scikit-learn to use ML features" in result.output

    @patch(
        "pypss.cli.cli.PatternDetector", side_effect=Exception("Model training failed!")
    )
    def test_ml_detect_model_fit_error(self, mock_pattern_detector, tmp_path):
        baseline_file = tmp_path / "baseline.json"
        target_file = tmp_path / "target.json"
        with open(baseline_file, "w") as f:
            json.dump([{"duration": 1.0}], f)
        with open(target_file, "w") as f:
            json.dump([{"duration": 1.0}], f)

        result = self.runner.invoke(
            ml_detect,  # Use ml_detect directly
            [
                "--baseline-file",
                str(baseline_file),
                "--target-file",
                str(target_file),
            ],
        )
        assert result.exit_code == 1
        assert "Error fitting ML model: Model training failed!" in result.output

    @patch("pypss.cli.cli.PatternDetector")
    def test_ml_detect_anomalies_found(self, MockPatternDetector, tmp_path):
        baseline_file = tmp_path / "baseline.json"
        target_file = tmp_path / "target.json"
        with open(baseline_file, "w") as f:
            json.dump([{"duration": 1.0, "name": "normal_trace"}], f)
        with open(target_file, "w") as f:
            json.dump(
                [
                    {"duration": 1.0, "name": "normal_trace"},
                    {"duration": 5.0, "name": "anomaly_trace"},
                ],
                f,
            )

        # Configure the mock instance that PatternDetector() will return
        mock_instance = MagicMock()
        mock_instance.fit.return_value = None  # fit just needs to run
        mock_instance.predict_anomalies.return_value = [False, True]
        mock_instance.anomaly_score.return_value = [
            -0.1,
            0.5,
        ]  # -0.1 normal, 0.5 anomaly

        MockPatternDetector.return_value = (
            mock_instance  # Ensure PatternDetector() returns our configured mock
        )

        result = self.runner.invoke(
            ml_detect,  # Use ml_detect directly
            [
                "--baseline-file",
                str(baseline_file),
                "--target-file",
                str(target_file),
            ],
        )
        assert result.exit_code == 0
        assert "Anomaly detected in 'anomaly_trace' (Score: 0.50)" in result.output
        assert "\nSummary: Anomalies were detected." in result.output
        MockPatternDetector.assert_called_once()
        mock_instance.fit.assert_called_once()
        mock_instance.predict_anomalies.assert_called_once()
        mock_instance.anomaly_score.assert_called_once()

    def test_ml_detect_no_anomalies_found(self, tmp_path):
        baseline_file = tmp_path / "baseline.json"
        target_file = tmp_path / "target.json"
        with open(baseline_file, "w") as f:
            json.dump([{"duration": 1.0}], f)
        with open(target_file, "w") as f:
            json.dump([{"duration": 1.0}], f)

        with patch("pypss.cli.cli.PatternDetector") as mock_detector:
            mock_instance = MagicMock()
            mock_detector.return_value = mock_instance
            mock_instance.predict_anomalies.return_value = [False]  # No anomalies
            mock_instance.anomaly_score.return_value = [-0.1]  # Scores for anomalies
            result = self.runner.invoke(
                ml_detect,  # Use ml_detect directly
                [
                    "--baseline-file",
                    str(baseline_file),
                    "--target-file",
                    str(target_file),
                ],
            )
            assert result.exit_code == 0
            assert (
                "No significant anomalies detected in target traces." in result.output
            )
            mock_detector.assert_called_once()
            mock_instance.fit.assert_called_once()
            mock_instance.predict_anomalies.assert_called_once()
            mock_instance.anomaly_score.assert_called_once()

    # --- history command tests ---
    def test_history_no_data(self):
        with (
            patch(
                "pypss.utils.config.GLOBAL_CONFIG.storage_uri", new=self.temp_db_path
            ),
            patch("pypss.utils.config.GLOBAL_CONFIG.storage_backend", new="sqlite"),
        ):
            # Ensure the storage is initialized for this path
            _ = SQLiteStorage(db_path=self.temp_db_path)

            result = self.runner.invoke(
                cli_test_group, ["history", "--db-path", self.temp_db_path]
            )  # Pass db_path explicitly
            assert result.exit_code == 0
            assert "No history found." in result.output

    def test_history_display(self):
        with (
            patch(
                "pypss.utils.config.GLOBAL_CONFIG.storage_uri", new=self.temp_db_path
            ),
            patch("pypss.utils.config.GLOBAL_CONFIG.storage_backend", new="sqlite"),
        ):
            storage = SQLiteStorage(
                db_path=self.temp_db_path
            )  # Re-initialize storage here
            # Add some mock data
            now = datetime.now()
            with patch("time.time", return_value=(now - timedelta(days=1)).timestamp()):
                storage.save(
                    {
                        "pss": 90,
                        "breakdown": {
                            "timing_stability": 10.0,
                            "memory_stability": 10.0,
                            "error_volatility": 10.0,
                            "branching_entropy": 10.0,
                            "concurrency_chaos": 10.0,
                        },
                    },
                    meta={"script": "script1.py"},
                )
            with patch("time.time", return_value=now.timestamp()):
                storage.save(
                    {
                        "pss": 85,
                        "breakdown": {
                            "timing_stability": 9.0,
                            "memory_stability": 9.0,
                            "error_volatility": 9.0,
                            "branching_entropy": 9.0,
                            "concurrency_chaos": 9.0,
                        },
                    },
                    meta={"script": "script2.py"},
                )

            result = self.runner.invoke(
                cli_test_group, ["history", "--db-path", self.temp_db_path]
            )  # Use cli_test_group here
            assert result.exit_code == 0
            assert "Historical PSS Trends" in result.output
            assert "90" in result.output
            assert "85" in result.output
            assert "10.00" in result.output
            assert "9.00" in result.output
            assert (
                "script1.py" not in result.output
            )  # meta is not displayed in text report

    def test_history_export_json(self):
        with (
            patch(
                "pypss.utils.config.GLOBAL_CONFIG.storage_uri", new=self.temp_db_path
            ),
            patch("pypss.utils.config.GLOBAL_CONFIG.storage_backend", new="sqlite"),
        ):
            storage = SQLiteStorage(
                db_path=self.temp_db_path
            )  # Re-initialize storage here
            now = datetime.now()
            with patch("time.time", return_value=(now - timedelta(days=1)).timestamp()):
                storage.save(
                    {
                        "pss": 90,
                        "breakdown": {
                            "timing_stability": 10.0,
                            "memory_stability": 10.0,
                            "error_volatility": 10.0,
                            "branching_entropy": 10.0,
                            "concurrency_chaos": 10.0,
                        },
                    },
                    meta={"script": "script1.py"},
                )

            result = self.runner.invoke(
                cli_test_group,
                ["history", "--export", "json", "--db-path", self.temp_db_path],
            )  # Use cli_test_group here
            assert result.exit_code == 0
            output_json = json.loads(result.output)
            assert len(output_json) == 1
            assert output_json[0]["pss"] == 90
            assert output_json[0]["meta"]["script"] == "script1.py"

    def test_history_export_csv(self):
        with (
            patch(
                "pypss.utils.config.GLOBAL_CONFIG.storage_uri", new=self.temp_db_path
            ),
            patch("pypss.utils.config.GLOBAL_CONFIG.storage_backend", new="sqlite"),
        ):
            storage = SQLiteStorage(
                db_path=self.temp_db_path
            )  # Re-initialize storage here
            now = datetime.now()
            with patch("time.time", return_value=(now - timedelta(days=1)).timestamp()):
                storage.save(
                    {
                        "pss": 90,
                        "breakdown": {
                            "timing_stability": 10.0,
                            "memory_stability": 10.0,
                            "error_volatility": 10.0,
                            "branching_entropy": 10.0,
                            "concurrency_chaos": 10.0,
                        },
                    },
                    meta={"script": "script1.py"},
                )
            with patch("time.time", return_value=now.timestamp()):
                storage.save(
                    {
                        "pss": 80,
                        "breakdown": {
                            "timing_stability": 8.0,
                            "memory_stability": 8.0,
                            "error_volatility": 8.0,
                            "branching_entropy": 8.0,
                            "concurrency_chaos": 8.0,
                        },
                    },
                    meta={"script": "script2.py"},
                )

            result = self.runner.invoke(
                cli_test_group,
                ["history", "--export", "csv", "--db-path", self.temp_db_path],
            )  # Use cli_test_group here
            assert result.exit_code == 0
            lines = result.output.strip().split("\n")
            assert len(lines) == 3  # Header + 2 data rows
            assert "pss,ts,ms,ev,be,cc,meta" in lines[0]
            # The most recent record is script2.py (PSS 80)
            assert '80.0,8.0,8.0,8.0,8.0,8.0,"{""script"": ""script2.py""}"' in lines[1]
            # The older record is script1.py (PSS 90)
            assert (
                '90.0,10.0,10.0,10.0,10.0,10.0,"{""script"": ""script1.py""}"'
                in lines[2]
            )

    def test_history_with_limit(self):
        with (
            patch(
                "pypss.utils.config.GLOBAL_CONFIG.storage_uri", new=self.temp_db_path
            ),
            patch("pypss.utils.config.GLOBAL_CONFIG.storage_backend", new="sqlite"),
        ):
            storage = SQLiteStorage(
                db_path=self.temp_db_path
            )  # Re-initialize storage here
            now = datetime.now()
            for i in range(5):
                with patch(
                    "time.time", return_value=(now - timedelta(minutes=i)).timestamp()
                ):
                    storage.save(
                        {
                            "pss": 100 - i,
                            "breakdown": {
                                "timing_stability": 10.0,
                                "memory_stability": 10.0,
                                "error_volatility": 10.0,
                                "branching_entropy": 10.0,
                                "concurrency_chaos": 10.0,
                            },
                        },
                        meta={},
                    )
            result = self.runner.invoke(
                cli_test_group,
                ["history", "--limit", "2", "--db-path", self.temp_db_path],
            )  # Use cli_test_group here
            assert result.exit_code == 0
            lines = result.output.strip().split("\n")
            # Header + separator + 2 data rows + separator = 5 lines of content
            assert len([line for line in lines if " | " in line]) == 3
            # Check the newest 2 entries are present
            assert "100" in result.output  # newest PSS should be there
            assert "99" in result.output  # next newest PSS should be there
            assert "98" not in result.output  # older PSS should not be there
            assert "97" not in result.output  # older PSS should not be there

    def test_history_with_days_filter(self):
        with (
            patch(
                "pypss.utils.config.GLOBAL_CONFIG.storage_uri", new=self.temp_db_path
            ),
            patch("pypss.utils.config.GLOBAL_CONFIG.storage_backend", new="sqlite"),
        ):
            storage = SQLiteStorage(
                db_path=self.temp_db_path
            )  # Re-initialize storage here
            now = datetime.now()
            # Data from today and yesterday
            with patch("time.time", return_value=now.timestamp()):
                storage.save(
                    {
                        "pss": 95,
                        "breakdown": {
                            "timing_stability": 10.0,
                            "memory_stability": 10.0,
                            "error_volatility": 10.0,
                            "branching_entropy": 10.0,
                            "concurrency_chaos": 10.0,
                        },
                    },
                    meta={},
                )
            with patch("time.time", return_value=(now - timedelta(days=1)).timestamp()):
                storage.save(
                    {
                        "pss": 85,
                        "breakdown": {
                            "timing_stability": 9.0,
                            "memory_stability": 9.0,
                            "error_volatility": 9.0,
                            "branching_entropy": 9.0,
                            "concurrency_chaos": 9.0,
                        },
                    },
                    meta={},
                )
            # Data from 3 days ago (should be filtered out by --days 2)
            with patch("time.time", return_value=(now - timedelta(days=3)).timestamp()):
                storage.save(
                    {
                        "pss": 75,
                        "breakdown": {
                            "timing_stability": 8.0,
                            "memory_stability": 8.0,
                            "error_volatility": 8.0,
                            "branching_entropy": 8.0,
                            "concurrency_chaos": 8.0,
                        },
                    },
                    meta={},
                )

            result = self.runner.invoke(
                cli_test_group,
                ["history", "--days", "2", "--db-path", self.temp_db_path],
            )  # Use cli_test_group here
            assert result.exit_code == 0
            assert "95" in result.output
            assert "85" in result.output
            assert "75" not in result.output
