import pytest
from click.testing import CliRunner
from unittest.mock import patch, MagicMock
from pypss.cli.cli import main
from pypss.storage.sqlite import SQLiteStorage
from pypss.instrumentation import global_collector


@pytest.fixture
def runner():
    return CliRunner()


def test_history_command_no_data(runner, tmp_path):
    db_path = tmp_path / "empty.db"
    result = runner.invoke(main, ["history", "--db-path", str(db_path)])
    assert result.exit_code == 0
    assert "No history found" in result.output


def test_history_command_with_data(runner, tmp_path):
    db_path = tmp_path / "test.db"
    storage = SQLiteStorage(db_path=str(db_path))
    storage.save({"pss": 88.8, "breakdown": {"timing_stability": 0.5}})

    result = runner.invoke(main, ["history", "--db-path", str(db_path)])
    assert result.exit_code == 0
    assert "88" in result.output
    assert "0.50" in result.output
    assert "Historical PSS Trends" in result.output


def test_run_command_stores_history(runner, tmp_path):
    script = tmp_path / "dummy.py"
    script.write_text("print('hello')")

    # Pre-seed collector so that `run` command proceeds
    global_collector.clear()
    global_collector.add_trace({"name": "dummy", "duration": 0.1})

    # We patch get_storage_backend where it is defined
    with patch("pypss.storage.get_storage_backend") as mock_get_backend:
        mock_storage = MagicMock()
        mock_get_backend.return_value = mock_storage

        result = runner.invoke(main, ["run", str(script), "--store-history"])

        assert result.exit_code == 0
        assert "PSS Score stored in history" in result.output
        mock_storage.save.assert_called_once()


def test_analyze_command_stores_history(runner, tmp_path):
    trace_file = tmp_path / "traces.json"
    trace_file.write_text('{"traces": []}')

    with patch("pypss.storage.get_storage_backend") as mock_get_backend:
        mock_storage = MagicMock()
        mock_get_backend.return_value = mock_storage

        result = runner.invoke(
            main, ["analyze", "--trace-file", str(trace_file), "--store-history"]
        )

        assert result.exit_code == 0
        assert "PSS Score stored in history" in result.output
        mock_storage.save.assert_called_once()


def test_regression_detection(runner, tmp_path):
    db_path = tmp_path / "reg_test.db"
    trace_file = tmp_path / "traces.json"
    trace_file.write_text('{"traces": []}')

    from pypss.storage.sqlite import SQLiteStorage

    storage = SQLiteStorage(str(db_path))

    # Seed high score history
    storage.save({"pss": 95.0, "breakdown": {}})
    storage.save({"pss": 95.0, "breakdown": {}})

    # Patch compute_pss_from_traces to return low score
    with patch("pypss.cli.cli.compute_pss_from_traces") as mock_compute:
        mock_compute.return_value = {"pss": 50.0, "breakdown": {}}

        # Patch get_storage_backend to return OUR storage instance
        with patch("pypss.storage.get_storage_backend") as mock_get_backend:
            mock_get_backend.return_value = storage

            result = runner.invoke(
                main, ["analyze", "--trace-file", str(trace_file), "--store-history"]
            )

            assert result.exit_code == 0
            assert "REGRESSION DETECTED" in result.output
            assert "Current PSS (50.0)" in result.output
