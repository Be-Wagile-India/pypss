from unittest.mock import MagicMock, patch

import pypss
from pypss.integrations.pytest_plugin import (
    pytest_addoption,
    pytest_runtest_call,
    pytest_sessionfinish,
    pytest_sessionstart,
)


class TestPytestPlugin:
    def test_addoption(self):
        parser = MagicMock()
        group = MagicMock()
        parser.getgroup.return_value = group

        pytest_addoption(parser)

        assert group.addoption.called

    def test_runtest_call(self):
        item = MagicMock()
        item.config.getoption.return_value = True  # Enable PSS
        item.nodeid = "test_foo"

        pypss.init()
        collector = pypss.get_global_collector()

        # Mock the yield (generator)
        gen = pytest_runtest_call(item)
        next(gen)  # Start

        # Simulate execution
        outcome = MagicMock()

        try:
            gen.send(outcome)
        except StopIteration:
            pass

        # Verify trace added
        traces = collector.get_traces()
        assert len(traces) > 0
        assert "test_foo" in traces[-1]["name"]

    def test_runtest_call_pss_disabled(self):
        item = MagicMock()
        item.config.getoption.return_value = False  # Disable PSS

        pypss.init()
        collector = pypss.get_global_collector()
        collector.clear()  # Ensure no residual traces

        # Mock the yield (generator)
        gen = pytest_runtest_call(item)
        next(gen)  # Start

        # Simulate execution
        outcome = MagicMock()

        try:
            gen.send(outcome)
        except StopIteration:
            pass

        traces = collector.get_traces()
        assert len(traces) == 0

    def test_runtest_call_test_fails(self):
        item = MagicMock()
        item.config.getoption.return_value = True  # Enable PSS
        item.nodeid = "test_failing_foo"

        pypss.init()
        collector = pypss.get_global_collector()
        collector.clear()  # Ensure no residual traces

        # Mock the yield (generator)
        gen = pytest_runtest_call(item)
        next(gen)  # Start

        # Simulate execution with an exception
        outcome = MagicMock()
        outcome.get_result.side_effect = Exception("Test failed!")

        try:
            gen.send(outcome)
        except StopIteration:
            pass

        # Verify trace added and error flag is True
        traces = collector.get_traces()
        assert len(traces) > 0
        assert traces[-1]["name"] == "test::test_failing_foo"
        assert traces[-1]["error"] is True

    def test_sessionfinish_no_traces(self, capsys, tmp_path):
        session = MagicMock()
        session.config.getoption.return_value = True  # PSS enabled
        session.exitstatus = 0  # Initialize exitstatus

        pypss.init()
        collector = pypss.get_global_collector()
        collector.clear()  # Ensure no traces

        with patch("pypss.integrations.pytest_plugin.TEMP_TRACE_DIR", str(tmp_path)):
            pytest_sessionfinish(session, 0)

        captured = capsys.readouterr()
        assert "PyPSS Stability Report" not in captured.out  # No report if no traces
        assert session.exitstatus == 0  # Should not change exit status

    @patch("pypss.integrations.pytest_plugin.compute_pss_from_traces")
    def test_sessionfinish_fail_below_threshold(self, mock_compute_pss, capsys, tmp_path):
        session = MagicMock()
        del session.config.workerinput  # Ensure Master node behavior
        session.config.getoption.side_effect = lambda x: {
            "--pss": True,
            "--pss-fail-below": 90,
        }.get(x, False)  # Enable PSS, set threshold

        # Mock PSS report to be below threshold
        mock_compute_pss.return_value = {"pss": 85}

        # Clear and add traces for the same test ID (need >= 2 runs)
        pypss.init()
        collector = pypss.get_global_collector()
        collector.clear()
        collector.add_trace({"name": "test_failure", "duration": 0.1})
        collector.add_trace({"name": "test_failure", "duration": 0.2})

        with patch("pypss.integrations.pytest_plugin.TEMP_TRACE_DIR", str(tmp_path)):
            pytest_sessionfinish(session, 0)

        captured = capsys.readouterr()
        # Check for per-test failure message
        assert "FAILURE: The following tests fell below the PSS threshold of 90" in captured.out
        assert "test_failure (PSS: 85)" in captured.out
        assert session.exitstatus == 1

    def test_sessionfinish_insufficient_data(self, capsys, tmp_path):
        session = MagicMock()
        del session.config.workerinput  # Ensure Master node behavior
        session.exitstatus = 0  # Initialize exitstatus
        session.config.getoption.side_effect = lambda x: {
            "--pss": True,
            "--pss-fail-below": 90,
        }.get(x, False)

        # clear and add ONE trace
        pypss.init()
        collector = pypss.get_global_collector()
        collector.clear()
        collector.add_trace({"name": "test_single_run", "duration": 0.1})

        with patch("pypss.integrations.pytest_plugin.TEMP_TRACE_DIR", str(tmp_path)):
            pytest_sessionfinish(session, 0)

        captured = capsys.readouterr()
        # Should show warning about need >1 run
        assert "Need >1 run for PSS" in captured.out
        # Should NOT fail
        assert session.exitstatus == 0

    def test_sessionstart(self, tmp_path):
        session = MagicMock()
        session.config.getoption.return_value = True

        # Ensure we are treated as Master
        del session.config.workerinput

        # Initialize PyPSS once here for the test context
        pypss.init()
        collector_initial = pypss.get_global_collector()

        # Add some dirt to collector_initial
        collector_initial.add_trace({"foo": "bar"})
        assert len(collector_initial.get_traces()) > 0

        # Create a fake temp dir to verify cleanup
        (tmp_path / "junk.json").touch()

        with patch("pypss.integrations.pytest_plugin.TEMP_TRACE_DIR", str(tmp_path)):
            # Now call the pytest_sessionstart hook, which should clear the global collector
            pytest_sessionstart(session)

            # Retrieve the global collector *again* to ensure we are looking at the current state
            collector_after_hook = pypss.get_global_collector()

            # Should be clean now
            assert len(collector_after_hook.get_traces()) == 0
            # Temp dir should be recreated/cleaned
            assert not (tmp_path / "junk.json").exists()

    @patch("pypss.integrations.pytest_plugin.compute_pss_from_traces")
    def test_sessionfinish_calc_error(self, mock_compute_pss, capsys, tmp_path):
        session = MagicMock()
        del session.config.workerinput  # Ensure Master node behavior
        session.config.getoption.return_value = True
        session.exitstatus = 0

        # Mock PSS calculation to raise exception
        mock_compute_pss.side_effect = ValueError("Math error")

        pypss.init()
        collector = pypss.get_global_collector()
        collector.clear()
        collector.add_trace({"name": "test_error", "duration": 0.1})
        collector.add_trace({"name": "test_error", "duration": 0.2})

        with patch("pypss.integrations.pytest_plugin.TEMP_TRACE_DIR", str(tmp_path)):
            pytest_sessionfinish(session, 0)

        captured = capsys.readouterr()
        # Should report error but not crash
        assert "Calc Error: Math error" in captured.out
        assert session.exitstatus == 0
