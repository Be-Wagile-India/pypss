import json
import os
import sys
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

import pypss

# Ensure project root is in sys.path for module discovery
sys.path.insert(0, os.path.abspath("."))

from pypss.cli import main


@pytest.fixture
def cli_runner():
    return CliRunner()


@pytest.fixture
def mock_trace_file(tmp_path):
    traces = [{"duration": 0.1, "memory": 100, "error": False}]
    trace_file = tmp_path / "traces.json"
    with open(trace_file, "w") as f:
        json.dump(traces, f)
    return trace_file


class TestCLI:
    def test_analyze_command(self, cli_runner, mock_trace_file):
        result = cli_runner.invoke(main, ["analyze", "--trace-file", str(mock_trace_file)])

        assert result.exit_code == 0
        assert "PSS:" in result.output
        assert "AI Stability Diagnosis" in result.output

    def test_analyze_fail_if_below(self, cli_runner, mock_trace_file):
        # Should pass if threshold is low
        result = cli_runner.invoke(
            main,
            ["analyze", "--trace-file", str(mock_trace_file), "--fail-if-below", "50"],
        )
        assert result.exit_code == 0

        # Should fail if threshold is impossible (101)
        result = cli_runner.invoke(
            main,
            ["analyze", "--trace-file", str(mock_trace_file), "--fail-if-below", "101"],
        )
        assert result.exit_code == 1
        assert "Failing" in result.output

    def test_run_command_no_traces(self, cli_runner, tmp_path):
        # Mock run_with_instrumentation to return no traces
        with patch("pypss.cli.cli.run_with_instrumentation"):
            with patch("pypss.get_global_collector") as mock_get_global_collector:
                mock_collector = MagicMock()
                mock_get_global_collector.return_value = mock_collector
                mock_collector.get_traces.return_value = []
                script = tmp_path / "empty.py"
                script.touch()
                result = cli_runner.invoke(main, ["run", str(script)])

                assert result.exit_code == 0
                assert "No traces collected" in result.output

    def test_run_command_html_output(self, cli_runner, tmp_path):
        with patch("pypss.cli.cli.run_with_instrumentation"):
            with patch("pypss.get_global_collector") as mock_get_global_collector:
                with patch("pypss.cli.cli.render_report_html") as mock_render_html:
                    mock_collector = MagicMock()
                    mock_get_global_collector.return_value = mock_collector
                    mock_collector.get_traces.return_value = [{"duration": 0.1, "error": False}]
                    mock_render_html.return_value = "<html>mock html</html>"

                    script = tmp_path / "dummy.py"
                    script.touch()
                    output_file = tmp_path / "report.html"

                    result = cli_runner.invoke(
                        main,
                        ["run", str(script), "--html", "--output", str(output_file)],
                    )

                    assert result.exit_code == 0
                    assert "Report saved" in result.output
                    assert output_file.exists()
                    assert output_file.read_text() == "<html>mock html</html>"

    def test_board_command_dependencies_missing(self, cli_runner, capsys):
        # Mock nicegui, plotly, pandas as not available
        with patch.dict(sys.modules, {"nicegui": None, "plotly": None, "pandas": None}):
            result = cli_runner.invoke(main, ["board"])
            assert result.exit_code == 1
            assert "Dashboard dependencies missing" in result.output

    def test_run_command(self, cli_runner, tmp_path):
        # Create a dummy script
        script = tmp_path / "myscript.py"
        script.write_text("print('Hello World')")

        result = cli_runner.invoke(main, ["run", str(script)])

        assert result.exit_code == 0
        assert "Launching" in result.output
        # Since script runs instantaneously and has no monitored functions, it might warn about no traces
        assert "No traces collected" in result.output or "PSS:" in result.output

    def test_run_command_with_instrumentation(self, cli_runner, tmp_path):
        # Create a dummy script that uses pypss implicitly via runner discovery
        # We need a function to be discovered
        script = tmp_path / "app.py"
        script.write_text("""
import time
def foo():
    time.sleep(0.01)

if __name__ == "__main__":
    foo()
""")

        # We need to run CLI. The runner will discover 'foo' in 'app.py' and instrument it.
        # However, CodebaseDiscoverer looks at file system.

        # Important: global_collector persists across tests in same process unless cleared
        pypss.init()
        collector = pypss.get_global_collector()
        collector.clear()

        # Run in the tmp_path so discovery works relatively
        with cli_runner.isolated_filesystem(temp_dir=tmp_path):
            result = cli_runner.invoke(main, ["run", str(script)])

        assert result.exit_code == 0
        # Should find traces because foo() was called
        if "PSS:" in result.output:
            assert "foo" in result.output or "app" in result.output

    def test_run_command_module_output(self, cli_runner, tmp_path):
        # Mocking to ensure we hit the module printing lines
        with patch("pypss.cli.cli.run_with_instrumentation"):
            with patch("pypss.get_global_collector") as mock_get_global_collector:
                with patch("pypss.cli.cli.get_module_score_breakdown") as mock_breakdown:
                    # Setup mocks
                    mock_collector = MagicMock()
                    mock_get_global_collector.return_value = mock_collector
                    mock_collector.get_traces.return_value = [{"name": "mod.func", "duration": 0.1}]
                    mock_breakdown.return_value = {
                        "mod_good": {"pss": 95},
                        "mod_ok": {"pss": 75},
                        "mod_bad": {"pss": 40},
                    }

                    script = tmp_path / "dummy.py"
                    script.touch()
                    output_file = tmp_path / "report.json"

                    result = cli_runner.invoke(main, ["run", str(script), "--output", str(output_file)])

                    assert result.exit_code == 0
                    assert "🟢 mod_good" in result.output
                    assert "🟡 mod_ok" in result.output
                    assert "🔴 mod_bad" in result.output
                    assert "Report saved" in result.output
                    assert output_file.exists()

    @patch("builtins.open", side_effect=OSError("Permission denied"))
    def test_run_command_output_file_write_error(self, mock_open, cli_runner, tmp_path):
        with patch("pypss.cli.cli.run_with_instrumentation"):
            with patch("pypss.get_global_collector") as mock_get_global_collector:
                mock_collector = MagicMock()
                mock_get_global_collector.return_value = mock_collector
                mock_collector.get_traces.return_value = [{"duration": 0.1, "error": False}]
                script = tmp_path / "dummy.py"
                script.touch()
                output_file = tmp_path / "report.json"

                result = cli_runner.invoke(
                    main,
                    ["run", str(script), "--output", str(output_file)],
                    catch_exceptions=True,
                )

                assert result.exit_code != 0
                assert isinstance(result.exception, OSError)
                assert "Permission denied" in str(result.exception)

    @patch("pypss.cli.cli.ijson.items", side_effect=Exception("Malformed JSON"))
    def test_analyze_command_file_read_error(self, mock_ijson, cli_runner, tmp_path):
        trace_file = tmp_path / "traces.json"
        # Create a file with content so ijson.items gets called
        with open(trace_file, "w") as f:
            f.write("[")

        result = cli_runner.invoke(main, ["analyze", "--trace-file", str(trace_file)], catch_exceptions=False)

        assert result.exit_code != 0

    def test_analyze_command_html_output(self, cli_runner, tmp_path):
        # Create a trace file
        traces = [{"duration": 0.1, "memory": 100, "error": False}]
        trace_file = tmp_path / "traces.json"
        with open(trace_file, "w") as f:
            # The streaming parser needs the correct structure
            json.dump({"traces": traces}, f)

        with patch("pypss.cli.cli.render_report_html") as mock_render_html:
            mock_render_html.return_value = "<html>Analyze HTML Report</html>"
            output_file = tmp_path / "analyze_report.html"
            result = cli_runner.invoke(
                main,
                [
                    "analyze",
                    "--trace-file",
                    str(trace_file),
                    "--html",
                    "--output",
                    str(output_file),
                ],
            )

            assert result.exit_code == 0
            assert "Report saved" in result.output
            assert output_file.exists()
            assert output_file.read_text() == "<html>Analyze HTML Report</html>"

    @patch("builtins.open", side_effect=Exception("Corrupted trace file"))
    def test_diagnose_command_file_read_error(self, mock_open, cli_runner, tmp_path):
        trace_file = tmp_path / "traces.json"
        trace_file.touch()

        result = cli_runner.invoke(main, ["diagnose", "--trace-file", str(trace_file)], catch_exceptions=True)

        assert result.exit_code != 0
        assert isinstance(result.exception, SystemExit)

    def test_diagnose_command_unknown_provider(self, cli_runner, tmp_path):
        trace_file = tmp_path / "traces.json"
        trace_file.touch()  # Just need the file to exist

        result = cli_runner.invoke(
            main,
            ["diagnose", "--trace-file", str(trace_file), "--provider", "bad_provider"],
        )

        assert result.exit_code == 2  # Click exits with 2 for bad option value
        assert "Invalid value for '--provider'" in result.output

    @pytest.mark.parametrize(
        "provider, api_key, expected_output, expected_api_key_call",
        [
            (
                "openai",
                "dummy_key",
                "AI Diagnosis: OpenAI says good!",
                "dummy_key",
            ),
            (
                "ollama",
                None,
                "AI Diagnosis: Ollama says fair!",
                None,
            ),
        ],
    )
    @patch("pypss.cli.cli.get_llm_diagnosis")
    def test_diagnose_command_llm_success(
        self,
        mock_get_llm_diagnosis,
        cli_runner,
        tmp_path,
        provider,
        api_key,
        expected_output,
        expected_api_key_call,
    ):
        mock_get_llm_diagnosis.return_value = expected_output
        trace_file = tmp_path / "traces.json"
        with open(trace_file, "w") as f:
            json.dump({"traces": []}, f)

        command_args = [
            "diagnose",
            "--trace-file",
            str(trace_file),
            "--provider",
            provider,
        ]
        if api_key:
            command_args.extend(["--api-key", api_key])

        result = cli_runner.invoke(main, command_args)

        assert result.exit_code == 0
        assert expected_output in result.output
        mock_get_llm_diagnosis.assert_called_once()
        assert mock_get_llm_diagnosis.call_args[0][0] == []
        assert mock_get_llm_diagnosis.call_args[1] == {
            "provider": provider,
            "api_key": expected_api_key_call,
        }

    @patch("subprocess.run")
    def test_board_command_subprocess_success(self, mock_subprocess_run, cli_runner, tmp_path):
        # Mock dependencies being present so we don't exit early
        with patch.dict(
            sys.modules,
            {"nicegui": MagicMock(), "plotly": MagicMock(), "pandas": MagicMock()},
        ):
            # Mock a successful subprocess run
            mock_subprocess_run.return_value = MagicMock(returncode=0)
            trace_file = tmp_path / "traces.json"
            trace_file.touch()

            result = cli_runner.invoke(main, ["board", str(trace_file)])

            assert result.exit_code == 0
            mock_subprocess_run.assert_called_once_with(
                [sys.executable, "-m", "pypss.board.app", str(trace_file)], check=False
            )

    @patch("subprocess.run")
    def test_board_command_subprocess_failure(self, mock_subprocess_run, cli_runner, tmp_path):
        # Mock dependencies being present
        with patch.dict(
            sys.modules,
            {"nicegui": MagicMock(), "plotly": MagicMock(), "pandas": MagicMock()},
        ):
            # Mock a failing subprocess run
            mock_subprocess_run.return_value = MagicMock(returncode=123)
            trace_file = tmp_path / "traces.json"
            trace_file.touch()

            result = cli_runner.invoke(main, ["board", str(trace_file)])

            assert result.exit_code == 123
            assert "Dashboard crashed with exit code 123" in result.output
            mock_subprocess_run.assert_called_once()

    @patch("subprocess.run")
    def test_board_command_keyboard_interrupt(self, mock_subprocess_run, cli_runner, tmp_path):
        # Mock dependencies being present
        with patch.dict(
            sys.modules,
            {"nicegui": MagicMock(), "plotly": MagicMock(), "pandas": MagicMock()},
        ):
            # Mock KeyboardInterrupt during subprocess run
            mock_subprocess_run.side_effect = KeyboardInterrupt
            trace_file = tmp_path / "traces.json"
            trace_file.touch()

            result = cli_runner.invoke(main, ["board", str(trace_file)])

            assert result.exit_code == 0  # Handled gracefully
            mock_subprocess_run.assert_called_once()
