from unittest.mock import MagicMock, patch
from pypss.integrations.pytest_plugin import (
    pytest_addoption,
    pytest_runtest_call,
    pytest_sessionfinish,
)
from pypss.instrumentation import global_collector


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
        traces = global_collector.get_traces()
        assert len(traces) > 0
        assert "test_foo" in traces[-1]["name"]

    def test_runtest_call_pss_disabled(self):
        item = MagicMock()
        item.config.getoption.return_value = False  # Disable PSS

        global_collector.clear()  # Ensure no residual traces

        # Mock the yield (generator)
        gen = pytest_runtest_call(item)
        next(gen)  # Start

        # Simulate execution
        outcome = MagicMock()

        try:
            gen.send(outcome)
        except StopIteration:
            pass

        # Verify no trace added
        traces = global_collector.get_traces()
        assert len(traces) == 0

    def test_runtest_call_test_fails(self):
        item = MagicMock()
        item.config.getoption.return_value = True  # Enable PSS
        item.nodeid = "test_failing_foo"

        global_collector.clear()  # Ensure no residual traces

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
        traces = global_collector.get_traces()
        assert len(traces) > 0
        assert traces[-1]["name"] == "test::test_failing_foo"
        assert traces[-1]["error"] is True

    def test_sessionfinish_no_traces(self, capsys):
        session = MagicMock()
        session.config.getoption.return_value = True  # PSS enabled
        session.exitstatus = 0  # Initialize exitstatus

        global_collector.clear()  # Ensure no traces

        pytest_sessionfinish(session, 0)

        captured = capsys.readouterr()
        assert "PyPSS Stability Report" not in captured.out  # No report if no traces
        assert session.exitstatus == 0  # Should not change exit status

    @patch("pypss.integrations.pytest_plugin.compute_pss_from_traces")
    def test_sessionfinish_fail_below_threshold(self, mock_compute_pss, capsys):
        session = MagicMock()
        session.config.getoption.side_effect = lambda x: {
            "--pss": True,
            "--pss-fail-below": 90,
        }.get(x, False)  # Enable PSS, set threshold

        # Mock PSS report to be below threshold
        mock_compute_pss.return_value = {"pss": 85}

        global_collector.add_trace({"duration": 0.1})  # Need at least one trace

        pytest_sessionfinish(session, 0)

        captured = capsys.readouterr()
        assert "FAILURE: PSS 85 is below threshold 90" in captured.out
        assert session.exitstatus == 1
