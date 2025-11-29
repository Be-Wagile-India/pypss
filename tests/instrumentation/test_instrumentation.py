import pytest
import time
from pypss.instrumentation import monitor_function, monitor_block, global_collector


# Reset collector before each test (simple way for now)
@pytest.fixture(autouse=True)
def clean_collector():
    global_collector.clear()
    yield
    global_collector.clear()


class TestInstrumentation:
    def test_monitor_function_decorator(self):
        @monitor_function("test_func", branch_tag="A")
        def sample_func(x):
            return x * 2

        # Run function
        res = sample_func(10)
        assert res == 20

        # Check traces
        traces = global_collector.get_traces()
        assert len(traces) == 1
        t = traces[0]
        assert t["name"] == "test_func"
        assert t["branch_tag"] == "A"
        assert "duration" in t
        assert "memory" in t
        assert t["error"] is False

    def test_monitor_function_exception(self):
        @monitor_function("error_func")
        def fail_func():
            raise ValueError("Boom")

        with pytest.raises(ValueError):
            fail_func()

        traces = global_collector.get_traces()
        assert len(traces) == 1
        assert traces[0]["error"] is True

    def test_monitor_block_context_manager(self):
        with monitor_block("block_A", branch_tag="B"):
            time.sleep(0.001)

        traces = global_collector.get_traces()
        assert len(traces) == 1
        assert traces[0]["name"] == "block_A"
        assert traces[0]["branch_tag"] == "B"
        assert traces[0]["error"] is False

    def test_sampling_decorator(self):
        from pypss.utils import GLOBAL_CONFIG

        # 1. Disable sampling (0%)
        orig_rate = GLOBAL_CONFIG.sample_rate
        GLOBAL_CONFIG.sample_rate = 0.0

        @monitor_function("sampled_func")
        def func():
            pass

        for _ in range(10):
            func()

        traces = global_collector.get_traces()
        assert len(traces) == 0

        # 2. Enable sampling (100%)
        GLOBAL_CONFIG.sample_rate = 1.0
        func()
        assert len(global_collector.get_traces()) == 1

        GLOBAL_CONFIG.sample_rate = orig_rate
