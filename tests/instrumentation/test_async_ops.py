import asyncio
import sys
import pytest
from unittest import mock
import time
import psutil
import logging
from pypss.instrumentation import global_collector, monitor_async
from pypss.instrumentation.async_ops import (
    start_async_monitoring,
    stop_async_monitoring,
    EventLoopHealthMonitor,
    _health_monitor_instance,
)
from pypss.utils.config import GLOBAL_CONFIG


@pytest.mark.asyncio
async def test_async_monitor_context_manager():
    global_collector.clear()

    async with monitor_async("test_block", branch_tag="tag1"):
        await asyncio.sleep(0.05)

    traces = global_collector.get_traces()
    assert len(traces) == 1
    t = traces[0]

    assert t["name"] == "test_block"
    assert t["branch_tag"] == "tag1"
    # Allow for minor floating point inaccuracies and async scheduling
    # Duration should be approximately 0.05, but at least very close to it.
    expected_min_duration = 0.05
    tolerance = 0.005  # 5 milliseconds tolerance
    assert t["duration"] >= expected_min_duration - tolerance
    assert (
        t["duration"] < expected_min_duration + 0.1
    )  # Should not be excessively long either
    assert t.get("async_op") is True


@pytest.mark.asyncio
async def test_yield_counting():
    if sys.version_info < (3, 12):
        pytest.skip("sys.monitoring requires Python 3.12+")

    global_collector.clear()
    start_async_monitoring(enable_sys_monitoring=True)

    async with monitor_async("yieldy_task"):
        await asyncio.sleep(0.001)
        await asyncio.sleep(0.001)
        await asyncio.sleep(0.001)

    traces = global_collector.get_traces()
    task_traces = [t for t in traces if t["name"] == "yieldy_task"]

    assert len(task_traces) == 1
    t = task_traces[0]

    assert t.get("yield_count", 0) > 0
    print(f"Yield Count: {t.get('yield_count')}")


@pytest.mark.asyncio
async def test_loop_health_monitor():
    global_collector.clear()

    monitor = EventLoopHealthMonitor(interval=0.05, threshold=0.0)
    monitor.start()

    await asyncio.sleep(0.2)

    monitor.stop()

    traces = global_collector.get_traces()
    health_traces = [t for t in traces if t["name"] == "__event_loop_health__"]

    assert len(health_traces) > 0
    first = health_traces[0]
    assert first["module"] == "pypss.system"
    assert "metadata" in first
    assert "lag" in first["metadata"]
    assert "active_tasks" in first["metadata"]
    assert "churn_rate" in first["metadata"]

    stop_async_monitoring()


@pytest.mark.asyncio
async def test_async_monitor_sampling_skip(monkeypatch):
    global_collector.clear()

    monkeypatch.setattr(GLOBAL_CONFIG, "sample_rate", 0.5)

    mock_time = mock.Mock()
    mock_time.return_value = 100.75
    monkeypatch.setattr(time, "time", mock_time)

    async with monitor_async("test_sampled_block"):
        await asyncio.sleep(0.01)

    traces = global_collector.get_traces()
    assert len(traces) == 0


@pytest.mark.asyncio
async def test_async_monitor_memory_tracking(monkeypatch):
    global_collector.clear()

    monkeypatch.setattr(GLOBAL_CONFIG, "w_ms", 1.0)

    mock_process = mock.Mock()
    mock_process.memory_info.return_value.rss = 1000
    monkeypatch.setattr(psutil, "Process", mock.Mock(return_value=mock_process))

    async with monitor_async("test_memory_block"):
        mock_process.memory_info.return_value.rss = 1500
        await asyncio.sleep(0.01)

    traces = global_collector.get_traces()
    assert len(traces) == 1
    t = traces[0]

    assert t["name"] == "test_memory_block"
    assert t["memory_diff"] == 500
    assert t["memory"] == 1500


@pytest.mark.asyncio
async def test_event_loop_health_monitor_start_already_running(monkeypatch, caplog):
    global_collector.clear()
    monitor = EventLoopHealthMonitor()
    monitor._monitor_loop = mock.AsyncMock()  # Mock the coroutine method directly

    mock_loop = mock.AsyncMock()
    mock_task_instance = mock.AsyncMock()
    mock_task_instance.cancel = mock.Mock()  # Ensure cancel is synchronous
    mock_loop.create_task = mock.Mock(return_value=mock_task_instance)
    monkeypatch.setattr(asyncio, "get_running_loop", mock.Mock(return_value=mock_loop))

    with caplog.at_level(logging.INFO):
        monitor.start()
        assert "Event Loop Health Monitor started" in caplog.text
        caplog.clear()

        monitor.start()
        assert "Event Loop Health Monitor started" not in caplog.text

    mock_loop.create_task.assert_called_once()

    monitor.stop()


@pytest.mark.asyncio
async def test_event_loop_health_monitor_start_runtime_error(monkeypatch, caplog):
    monitor = EventLoopHealthMonitor()

    monkeypatch.setattr(
        asyncio,
        "get_running_loop",
        mock.Mock(side_effect=RuntimeError("No running loop")),
    )

    with caplog.at_level(logging.WARNING):
        monitor.start()
        assert len(caplog.text) == 0

    assert monitor._task is None
    assert monitor._running is False


@pytest.mark.asyncio
async def test_event_loop_health_monitor_stop_no_task():
    monitor = EventLoopHealthMonitor()
    monitor.stop()
    assert monitor._running is False
    assert monitor._task is None


@pytest.mark.asyncio
async def test_event_loop_health_monitor_monitor_loop_cancelled_error(monkeypatch):
    monitor = EventLoopHealthMonitor()

    monitor.start()

    # Give the task a moment to start and run
    await asyncio.sleep(0.01)

    # Now, explicitly cancel the monitor's task
    monitor._task.cancel()

    # Wait for the task to complete its cancellation
    try:
        await monitor._task
    except asyncio.CancelledError:
        pass  # Expected, as we just cancelled it.

    assert monitor._task.done() is True
    # monitor object's _running state is not changed by task cancellation itself.
    # It is only changed by calling monitor.stop().
    assert monitor._running is True

    monitor.stop()  # Explicitly stop the monitor (sets _running=False)
    assert monitor._running is False  # Verify monitor.stop() effect.


@pytest.mark.asyncio
async def test_event_loop_health_monitor_monitor_loop_exception(monkeypatch, caplog):
    caplog.set_level(logging.ERROR, logger="pypss.instrumentation.async_ops")
    monitor = EventLoopHealthMonitor()
    original_asyncio_sleep = asyncio.sleep

    monkeypatch.setattr(
        asyncio,
        "all_tasks",
        mock.Mock(side_effect=Exception("Simulated task error")),
    )

    sleep_calls = []

    class YieldingAsyncSleepMock:
        async def __call__(self, delay):
            sleep_calls.append(delay)
            if delay == 1.0:
                raise asyncio.CancelledError()
            await original_asyncio_sleep(0)
            return None

    mock_async_sleep = YieldingAsyncSleepMock()
    monkeypatch.setattr(asyncio, "sleep", mock_async_sleep)

    monitor._running = True
    _monitor_loop_task = asyncio.create_task(monitor._monitor_loop())

    with caplog.at_level(logging.ERROR):
        await original_asyncio_sleep(monitor.interval + 0.1)

        timeout = 5.0
        start_time = time.time()
        called_with_1_0 = False
        while time.time() - start_time < timeout:
            if 1.0 in sleep_calls:
                called_with_1_0 = True
                break
            await original_asyncio_sleep(0.01)

        assert called_with_1_0, (
            f"asyncio.sleep was not called with 1.0 within timeout. Calls: {sleep_calls}"
        )

    _monitor_loop_task.cancel()
    try:
        await _monitor_loop_task
    except asyncio.CancelledError:
        pass


@pytest.mark.asyncio
async def test_start_async_monitoring_runtime_error(monkeypatch, caplog):
    global _health_monitor_instance
    _health_monitor_instance = None
    caplog.set_level(logging.WARNING, logger="pypss.instrumentation.async_ops")

    monkeypatch.setattr(
        asyncio,
        "get_running_loop",
        mock.Mock(side_effect=RuntimeError("No running loop")),
    )

    with caplog.at_level(logging.WARNING):
        start_async_monitoring()
        assert (
            "PyPSS: start_async_monitoring called outside of event loop." in caplog.text
        )

    assert _health_monitor_instance is None


@pytest.mark.asyncio
async def test_stop_async_monitoring_no_instance():
    # Ensure _health_monitor_instance is None before calling stop_async_monitoring
    # It is reset by the autouse fixture in test_async_ops.py or test_sys_monitoring.py
    # or explicitly set to None in test_start_async_monitoring_runtime_error
    stop_async_monitoring()  # Should not raise an error
    # No assertion needed beyond not raising an error, but ensure _health_monitor_instance remains None
    assert _health_monitor_instance is None
