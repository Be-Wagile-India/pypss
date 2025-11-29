import json
import os
import sys
from unittest.mock import patch, MagicMock
from click.testing import CliRunner

# Ensure project root is in sys.path for module discovery
sys.path.insert(0, os.path.abspath("."))

from pypss.cli import main
from pypss.instrumentation import global_collector


class TestCLI:
    def test_analyze_command(self, tmp_path):
        # Create a trace file
        traces = [{"duration": 0.1, "memory": 100, "error": False}]
        trace_file = tmp_path / "traces.json"
        with open(trace_file, "w") as f:
            json.dump(traces, f)

        runner = CliRunner()
        result = runner.invoke(main, ["analyze", "--trace-file", str(trace_file)])

        assert result.exit_code == 0
        assert "PSS:" in result.output
        assert "AI Stability Diagnosis" in result.output

    def test_analyze_fail_if_below(self, tmp_path):
        # Perfect run -> PSS 100 (approx)
        traces = [{"duration": 0.1, "memory": 100, "error": False}]
        trace_file = tmp_path / "traces.json"
        with open(trace_file, "w") as f:
            json.dump(traces, f)

        runner = CliRunner()
        # Should pass if threshold is low
        result = runner.invoke(
            main, ["analyze", "--trace-file", str(trace_file), "--fail-if-below", "50"]
        )
        assert result.exit_code == 0

        # Should fail if threshold is impossible (101)
        result = runner.invoke(
            main, ["analyze", "--trace-file", str(trace_file), "--fail-if-below", "101"]
        )
        assert result.exit_code == 1
        assert "Failing" in result.output

    def test_run_command_no_traces(self, tmp_path):
        # Mock run_with_instrumentation to return no traces
        with patch("pypss.cli.cli.run_with_instrumentation"):
            with patch("pypss.cli.cli.global_collector.get_traces") as mock_get_traces:
                mock_get_traces.return_value = []
                script = tmp_path / "empty.py"
                script.touch()
                runner = CliRunner()
                result = runner.invoke(main, ["run", str(script)])

                assert result.exit_code == 0
                assert "No traces collected" in result.output

    def test_run_command_html_output(self, tmp_path):
        with patch("pypss.cli.cli.run_with_instrumentation"):
            with patch("pypss.cli.cli.global_collector.get_traces") as mock_get_traces:
                with patch("pypss.cli.cli.render_report_html") as mock_render_html:
                    mock_get_traces.return_value = [{"duration": 0.1, "error": False}]
                    mock_render_html.return_value = "<html>mock html</html>"

                    script = tmp_path / "dummy.py"
                    script.touch()
                    output_file = tmp_path / "report.html"

                    runner = CliRunner()
                    result = runner.invoke(
                        main,
                        ["run", str(script), "--html", "--output", str(output_file)],
                    )

                    assert result.exit_code == 0
                    assert "Report saved" in result.output
                    assert output_file.exists()
                    assert output_file.read_text() == "<html>mock html</html>"

    def test_board_command_dependencies_missing(self, capsys):
        # Mock nicegui, plotly, pandas as not available
        with patch.dict(sys.modules, {"nicegui": None, "plotly": None, "pandas": None}):
            runner = CliRunner()
            result = runner.invoke(main, ["board"])
            assert result.exit_code == 1
            assert "Dashboard dependencies missing" in result.output

    def test_run_command(self, tmp_path):
        # Create a dummy script
        script = tmp_path / "myscript.py"
        script.write_text("print('Hello World')")

        runner = CliRunner()
        result = runner.invoke(main, ["run", str(script)])

        assert result.exit_code == 0
        assert "Launching" in result.output
        # Since script runs instantaneously and has no monitored functions, it might warn about no traces
        assert "No traces collected" in result.output or "PSS:" in result.output

    def test_run_command_with_instrumentation(self, tmp_path):
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
        global_collector.clear()

        runner = CliRunner()
        # Run in the tmp_path so discovery works relatively
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(main, ["run", str(script)])

        assert result.exit_code == 0
        # Should find traces because foo() was called
        if "PSS:" in result.output:
            assert "foo" in result.output or "app" in result.output

    def test_run_command_module_output(self, tmp_path):
        # Mocking to ensure we hit the module printing lines
        with patch("pypss.cli.cli.run_with_instrumentation"):
            with patch("pypss.cli.cli.global_collector.get_traces") as mock_traces:
                with patch(
                    "pypss.cli.cli.get_module_score_breakdown"
                ) as mock_breakdown:
                    # Setup mocks
                    mock_traces.return_value = [{"name": "mod.func", "duration": 0.1}]
                    mock_breakdown.return_value = {
                        "mod_good": {"pss": 95},
                        "mod_ok": {"pss": 75},
                        "mod_bad": {"pss": 40},
                    }

                    script = tmp_path / "dummy.py"
                    script.touch()
                    output_file = tmp_path / "report.json"

                    runner = CliRunner()
                    result = runner.invoke(
                        main, ["run", str(script), "--output", str(output_file)]
                    )

                    assert result.exit_code == 0
                    assert "🟢 mod_good" in result.output
                    assert "🟡 mod_ok" in result.output
                    assert "🔴 mod_bad" in result.output
                    assert "Report saved" in result.output
                    assert output_file.exists()

    @patch("builtins.open", side_effect=OSError("Permission denied"))
    def test_run_command_output_file_write_error(self, mock_open, tmp_path):
        with patch("pypss.cli.cli.run_with_instrumentation"):
            with patch("pypss.cli.cli.global_collector.get_traces") as mock_get_traces:
                mock_get_traces.return_value = [{"duration": 0.1, "error": False}]
                script = tmp_path / "dummy.py"
                script.touch()
                output_file = tmp_path / "report.json"

                runner = CliRunner()
                result = runner.invoke(
                    main,
                    ["run", str(script), "--output", str(output_file)],
                    catch_exceptions=True,
                )

                assert result.exit_code != 0
                assert isinstance(result.exception, OSError)
                assert "Permission denied" in str(result.exception)

    @patch("pypss.cli.cli.ijson.items", side_effect=Exception("Malformed JSON"))
    def test_analyze_command_file_read_error(self, mock_ijson, tmp_path):
        trace_file = tmp_path / "traces.json"
        # Create a file with content so ijson.items gets called
        with open(trace_file, "w") as f:
            f.write("[")

        runner = CliRunner()
        result = runner.invoke(
            main, ["analyze", "--trace-file", str(trace_file)], catch_exceptions=False
        )

        assert result.exit_code != 0

    def test_analyze_command_html_output(self, tmp_path):
        # Create a trace file
        traces = [{"duration": 0.1, "memory": 100, "error": False}]
        trace_file = tmp_path / "traces.json"
        with open(trace_file, "w") as f:
            # The streaming parser needs the correct structure
            json.dump({"traces": traces}, f)

        runner = CliRunner()
        with patch("pypss.cli.cli.render_report_html") as mock_render_html:
            mock_render_html.return_value = "<html>Analyze HTML Report</html>"
            output_file = tmp_path / "analyze_report.html"
            result = runner.invoke(
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
    def test_diagnose_command_file_read_error(self, mock_open, tmp_path):
        trace_file = tmp_path / "traces.json"
        trace_file.touch()

        runner = CliRunner()
        result = runner.invoke(
            main, ["diagnose", "--trace-file", str(trace_file)], catch_exceptions=True
        )

        assert result.exit_code != 0
        assert isinstance(result.exception, SystemExit)

    def test_diagnose_command_unknown_provider(self, tmp_path):
        trace_file = tmp_path / "traces.json"
        trace_file.touch()  # Just need the file to exist

        runner = CliRunner()
        result = runner.invoke(
            main,
            ["diagnose", "--trace-file", str(trace_file), "--provider", "bad_provider"],
        )

        assert result.exit_code == 2  # Click exits with 2 for bad option value
        assert "Invalid value for '--provider'" in result.output

    @patch("pypss.cli.cli.get_llm_diagnosis")
    def test_diagnose_command_openai_success(self, mock_get_llm_diagnosis, tmp_path):
        mock_get_llm_diagnosis.return_value = "AI Diagnosis: OpenAI says good!"
        trace_file = tmp_path / "traces.json"
        with open(trace_file, "w") as f:
            json.dump({"traces": []}, f)

        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "diagnose",
                "--trace-file",
                str(trace_file),
                "--provider",
                "openai",
                "--api-key",
                "dummy_key",
            ],
        )

        assert result.exit_code == 0
        assert "AI Diagnosis: OpenAI says good!" in result.output
        # The json.load will happen, so the arg is a list, not the file content
        mock_get_llm_diagnosis.assert_called_once()
        assert mock_get_llm_diagnosis.call_args[0][0] == []
        assert mock_get_llm_diagnosis.call_args[1] == {
            "provider": "openai",
            "api_key": "dummy_key",
        }

    @patch("pypss.cli.cli.get_llm_diagnosis")
    def test_diagnose_command_ollama_success(self, mock_get_llm_diagnosis, tmp_path):
        mock_get_llm_diagnosis.return_value = "AI Diagnosis: Ollama says fair!"
        trace_file = tmp_path / "traces.json"
        with open(trace_file, "w") as f:
            json.dump({"traces": []}, f)

        runner = CliRunner()
        result = runner.invoke(
            main,
            ["diagnose", "--trace-file", str(trace_file), "--provider", "ollama"],
        )

        assert result.exit_code == 0
        assert "AI Diagnosis: Ollama says fair!" in result.output
        mock_get_llm_diagnosis.assert_called_once()
        assert mock_get_llm_diagnosis.call_args[0][0] == []
        assert mock_get_llm_diagnosis.call_args[1] == {
            "provider": "ollama",
            "api_key": None,
        }

    @patch("subprocess.run")
    def test_board_command_subprocess_success(self, mock_subprocess_run, tmp_path):
        # Mock a successful subprocess run
        mock_subprocess_run.return_value = MagicMock(returncode=0)
        trace_file = tmp_path / "traces.json"
        trace_file.touch()

        runner = CliRunner()
        result = runner.invoke(main, ["board", str(trace_file)])

        assert result.exit_code == 0
        mock_subprocess_run.assert_called_once_with(
            [sys.executable, "-m", "pypss.board.app", str(trace_file)], check=False
        )

    @patch("subprocess.run")
    def test_board_command_subprocess_failure(self, mock_subprocess_run, tmp_path):
        # Mock a failing subprocess run
        mock_subprocess_run.return_value = MagicMock(returncode=123)
        trace_file = tmp_path / "traces.json"
        trace_file.touch()

        runner = CliRunner()
        result = runner.invoke(main, ["board", str(trace_file)])

        assert result.exit_code == 123
        assert "Dashboard crashed with exit code 123" in result.output
        mock_subprocess_run.assert_called_once()

    @patch("subprocess.run")
    def test_board_command_keyboard_interrupt(self, mock_subprocess_run, tmp_path):
        # Mock KeyboardInterrupt during subprocess run
        mock_subprocess_run.side_effect = KeyboardInterrupt
        trace_file = tmp_path / "traces.json"
        trace_file.touch()

        runner = CliRunner()
        result = runner.invoke(main, ["board", str(trace_file)])

        assert result.exit_code == 0  # Handled gracefully
        mock_subprocess_run.assert_called_once()
