import asyncio
import pytest
import pypss
from pypss.instrumentation import monitor_function


# Define an async function to monitor
@monitor_function("async_task")
async def async_task(duration):
    await asyncio.sleep(duration)
    return "done"


@monitor_function("async_worker")
async def async_worker(delay):
    # Simulate work that yields
    await asyncio.sleep(delay)
    # Simulate some CPU work (should not be counted in cpu_time for async to avoid pollution)
    sum(range(10000))


@pytest.mark.asyncio
async def test_async_monitoring():
    pypss.init()
    collector = pypss.get_global_collector()
    collector.clear()

    expected_duration = 0.1
    # Run the async task
    result = await async_task(expected_duration)
    assert result == "done"

    traces = collector.get_traces()
    assert len(traces) == 1
    trace = traces[0]

    print(f"Trace duration: {trace['duration']}")

    # Verify duration capture
    assert trace["duration"] >= expected_duration * 0.5

    # Verify AsyncIO specific metric fix:
    # cpu_time should be 0.0
    # wait_time should be == duration
    assert trace["cpu_time"] == 0.0
    assert trace["wait_time"] == trace["duration"]


@pytest.mark.asyncio
async def test_async_wait_time_metric():
    pypss.init()
    collector = pypss.get_global_collector()
    collector.clear()

    # Run two concurrent tasks
    # Task 1 sleeps 0.2s
    # Task 2 sleeps 0.2s
    # Total wall time ~0.2s (concurrent)

    await asyncio.gather(async_worker(0.2), async_worker(0.2))

    traces = collector.get_traces()
    assert len(traces) == 2

    for trace in traces:
        # Check that metrics are sane for async
        assert trace["duration"] >= 0.2
        assert trace["cpu_time"] == 0.0
        assert trace["wait_time"] == trace["duration"]
