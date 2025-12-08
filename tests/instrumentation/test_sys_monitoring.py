import pytest
from unittest import mock
import logging
import time

import pypss.instrumentation.async_ops as async_ops  # Import the module directly

from pypss.instrumentation.async_ops import (
    _setup_sys_monitoring,
    AsyncTraceContext,
    _current_trace_context,
)


# Ensure _MONITORING_ACTIVE and _METRICS_COROUTINE_STARTS are reset for each test
@pytest.fixture(autouse=True)
def reset_monitoring_state():
    async_ops._MONITORING_ACTIVE = False
    async_ops._METRICS_COROUTINE_STARTS = 0
    yield
    async_ops._MONITORING_ACTIVE = False
    async_ops._METRICS_COROUTINE_STARTS = 0


class TestSetupSysMonitoring:
    def test_setup_sys_monitoring_python_version_lt_3_12(self, monkeypatch):
        # Test the branch where Python version is less than 3.12
        monkeypatch.setattr(async_ops.sys, "version_info", (3, 11))
        _setup_sys_monitoring()
        assert not async_ops._MONITORING_ACTIVE

    def test_setup_sys_monitoring_already_active(self):
        # Test the branch where _MONITORING_ACTIVE is already True
        async_ops._MONITORING_ACTIVE = True
        _setup_sys_monitoring()
        assert async_ops._MONITORING_ACTIVE

    @pytest.mark.skipif(
        async_ops.sys.version_info < (3, 12),
        reason="sys.monitoring requires Python 3.12+",
    )
    def test_setup_sys_monitoring_no_sys_monitoring(self, monkeypatch, caplog):
        # Test the branch where sys.monitoring is not found
        monkeypatch.setattr(async_ops.sys, "monitoring", None)
        with caplog.at_level(logging.WARNING):
            _setup_sys_monitoring()
        assert "sys.monitoring not found" in caplog.text
        assert not async_ops._MONITORING_ACTIVE

    @pytest.mark.skipif(
        async_ops.sys.version_info < (3, 12),
        reason="sys.monitoring requires Python 3.12+",
    )
    def test_setup_sys_monitoring_profiler_id_in_use_falls_back_to_debugger(
        self, monkeypatch, caplog
    ):
        # Mock sys.monitoring to simulate PROFILER_ID being in use
        mock_monitoring = mock.Mock()
        mock_monitoring.PROFILER_ID = 1
        mock_monitoring.DEBUGGER_ID = 2
        mock_monitoring.events.PY_YIELD = 1 << 0
        mock_monitoring.events.PY_START = 1 << 1

        mock_monitoring.use_tool_id.side_effect = [
            ValueError("PROFILER_ID in use"),
            None,  # Success for DEBUGGER_ID
        ]

        monkeypatch.setattr(async_ops.sys, "monitoring", mock_monitoring)
        monkeypatch.setattr(
            async_ops.sys, "version_info", (3, 12, 0, "final", 0)
        )  # Ensure Python 3.12+

        with caplog.at_level(logging.WARNING):
            _setup_sys_monitoring()

        assert "PROFILER_ID in use. Trying DEBUGGER_ID" in caplog.text
        assert mock_monitoring.use_tool_id.call_count == 2
        mock_monitoring.use_tool_id.assert_any_call(
            mock_monitoring.PROFILER_ID, "pypss_monitor"
        )
        mock_monitoring.use_tool_id.assert_any_call(
            mock_monitoring.DEBUGGER_ID, "pypss_monitor"
        )
        mock_monitoring.set_events.assert_called_once_with(
            mock_monitoring.DEBUGGER_ID,
            mock_monitoring.events.PY_YIELD | mock_monitoring.events.PY_START,
        )
        assert async_ops._MONITORING_ACTIVE

    @pytest.mark.skipif(
        async_ops.sys.version_info < (3, 12),
        reason="sys.monitoring requires Python 3.12+",
    )
    def test_setup_sys_monitoring_exception_during_setup(self, monkeypatch, caplog):
        # Test handling of unexpected exceptions during sys.monitoring setup
        mock_monitoring = mock.Mock()
        mock_monitoring.PROFILER_ID = 1
        mock_monitoring.events.PY_YIELD = 1 << 0
        mock_monitoring.events.PY_START = 1 << 1
        mock_monitoring.use_tool_id.side_effect = Exception("Mock monitoring error")

        monkeypatch.setattr(async_ops.sys, "monitoring", mock_monitoring)
        monkeypatch.setattr(async_ops.sys, "version_info", (3, 12, 0, "final", 0))

        with caplog.at_level(logging.WARNING):
            _setup_sys_monitoring()

        assert "Failed to initialize sys.monitoring" in caplog.text
        assert not async_ops._MONITORING_ACTIVE

    @pytest.mark.skipif(
        async_ops.sys.version_info < (3, 12),
        reason="sys.monitoring requires Python 3.12+",
    )
    @pytest.mark.asyncio
    async def test_setup_sys_monitoring_callbacks_registered_and_called(
        self, monkeypatch
    ):
        # Test that callbacks are registered and yield_callback updates context
        mock_monitoring = mock.Mock()
        mock_monitoring.PROFILER_ID = 1
        mock_monitoring.events.PY_YIELD = 1 << 0
        mock_monitoring.events.PY_START = 1 << 1

        # Ensure sys.monitoring is seen as active
        monkeypatch.setattr(async_ops.sys, "monitoring", mock_monitoring)
        monkeypatch.setattr(async_ops.sys, "version_info", (3, 12, 0, "final", 0))

        _setup_sys_monitoring()

        # Assert callbacks were registered
        mock_monitoring.register_callback.assert_any_call(
            mock_monitoring.PROFILER_ID, mock_monitoring.events.PY_YIELD, mock.ANY
        )
        mock_monitoring.register_callback.assert_any_call(
            mock_monitoring.PROFILER_ID, mock_monitoring.events.PY_START, mock.ANY
        )

        # Get the registered yield_callback (it's the second positional arg for PY_YIELD)
        yield_callback = mock_monitoring.register_callback.call_args_list[0].args[
            2
        ]  # Adjust index based on which callback is called first

        # Simulate a context being active
        ctx = AsyncTraceContext(
            name="test", module="mod", branch_tag=None, start_wall=time.time()
        )
        token = _current_trace_context.set(ctx)

        # Call the yield callback directly to simulate a yield event
        yield_callback(
            mock.Mock(), 0, mock.Mock(), mock.Mock()
        )  # code, instruction_offset, obj, *args (obj and args might vary)

        assert ctx.yield_count == 1

        # Simulate a coroutine start
        initial_starts = async_ops._METRICS_COROUTINE_STARTS
        start_callback = mock_monitoring.register_callback.call_args_list[1].args[2]

        mock_code = mock.Mock()
        mock_code.co_flags = 0x0080  # CO_COROUTINE
        start_callback(mock_code, 0, mock.Mock())  # code, instruction_offset, arg

        assert async_ops._METRICS_COROUTINE_STARTS == initial_starts + 1

        _current_trace_context.reset(token)

    @pytest.mark.skipif(
        async_ops.sys.version_info < (3, 12),
        reason="sys.monitoring requires Python 3.12+",
    )
    def test_setup_sys_monitoring_yield_callback_no_context(self, monkeypatch):
        # Test yield_callback when no AsyncTraceContext is active
        mock_monitoring = mock.Mock()
        mock_monitoring.PROFILER_ID = 1
        mock_monitoring.events.PY_YIELD = 1 << 0
        monkeypatch.setattr(async_ops.sys, "monitoring", mock_monitoring)
        monkeypatch.setattr(async_ops.sys, "version_info", (3, 12, 0, "final", 0))

        # Temporarily ensure _current_trace_context is None
        current_context_token = _current_trace_context.set(None)

        _setup_sys_monitoring()  # This will register the callbacks

        yield_callback_func = mock_monitoring.register_callback.call_args_list[0].args[
            2
        ]

        # Call yield_callback without an active context
        yield_callback_func(mock.Mock(), 0, mock.Mock(), mock.Mock())

        # No assertion needed, just ensure it doesn't crash and returns None
        # The key is that ctx.yield_count += 1 branch is not taken

        _current_trace_context.reset(current_context_token)

    @pytest.mark.skipif(
        async_ops.sys.version_info < (3, 12),
        reason="sys.monitoring requires Python 3.12+",
    )
    def test_setup_sys_monitoring_start_callback_not_coroutine(self, monkeypatch):
        # Test start_callback when code.co_flags does not indicate a coroutine
        mock_monitoring = mock.Mock()
        mock_monitoring.PROFILER_ID = 1
        mock_monitoring.events.PY_START = 1 << 1
        monkeypatch.setattr(async_ops.sys, "monitoring", mock_monitoring)
        monkeypatch.setattr(async_ops.sys, "version_info", (3, 12, 0, "final", 0))

        _setup_sys_monitoring()

        start_callback_func = mock_monitoring.register_callback.call_args_list[1].args[
            2
        ]  # Assuming PY_START is registered second

        initial_starts = async_ops._METRICS_COROUTINE_STARTS

        mock_code = mock.Mock()
        mock_code.co_flags = 0x0001  # Not a coroutine flag
        start_callback_func(mock_code, 0, mock.Mock())

        assert (
            async_ops._METRICS_COROUTINE_STARTS == initial_starts
        )  # Should not increment
