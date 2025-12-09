import pytest
import time
import inspect
import random
from unittest.mock import MagicMock

import pypss  # Import pypss
from pypss.instrumentation import monitor_function, monitor_block
from pypss.utils.config import GLOBAL_CONFIG


@pytest.fixture(autouse=True)
def setup_teardown_pypss_init():
    """
    Fixture to initialize pypss components before each test and clean up after.
    This ensures global_collector and other components are properly set up.
    """
    pypss.init()
    # Explicitly clear global_collector after init()
    # We retrieve the collector via the getter
    pypss.get_global_collector().clear()

    yield

    # Teardown: Stop runtime tuner and error rate monitor if they were started
    pypss.get_runtime_tuner().stop()
    pypss.get_error_rate_monitor().stop()
    pypss.get_global_collector().clear()  # Clear collector after each test


class TestInstrumentation:
    def test_monitor_function_decorator(
        self, monkeypatch
    ):  # Add monkeypatch as argument
        monkeypatch.setattr(GLOBAL_CONFIG, "sample_rate", 1.0)  # Ensure 100% sampling
        monkeypatch.setattr(
            GLOBAL_CONFIG, "error_sample_rate", 1.0
        )  # Ensure errors are not sampled out

        @monitor_function("test_func", branch_tag="A")
        def sample_func(x):
            return x * 2

        # Run function
        res = sample_func(10)
        assert res == 20

        # Check traces
        traces = pypss.get_global_collector().get_traces()
        assert len(traces) == 1
        t = traces[0]
        assert t["name"] == "test_func"
        assert t["branch_tag"] == "A"
        assert "duration" in t
        assert "memory" in t
        assert t["error"] is False

    def test_monitor_function_exception(self, monkeypatch):
        monkeypatch.setattr(
            GLOBAL_CONFIG, "sample_rate", 1.0
        )  # Explicitly set sample rate
        monkeypatch.setattr(
            GLOBAL_CONFIG, "error_sample_rate", 1.0
        )  # Explicitly set error sample rate

        @monitor_function("error_func")
        def fail_func():
            raise ValueError("Boom")

        with pytest.raises(ValueError):
            fail_func()

        traces = pypss.get_global_collector().get_traces()
        assert len(traces) == 1
        assert traces[0]["error"] is True
        assert traces[0]["exception_type"] == "ValueError"

    def test_monitor_block_context_manager(
        self, monkeypatch
    ):  # Add monkeypatch as argument
        monkeypatch.setattr(GLOBAL_CONFIG, "sample_rate", 1.0)  # Ensure 100% sampling
        monkeypatch.setattr(
            GLOBAL_CONFIG, "error_sample_rate", 1.0
        )  # Ensure errors are not sampled out

        with monitor_block("block_A", branch_tag="B"):
            time.sleep(0.001)

        traces = pypss.get_global_collector().get_traces()
        assert len(traces) == 1
        assert traces[0]["name"] == "block_A"
        assert traces[0]["branch_tag"] == "B"
        assert traces[0]["error"] is False

    def test_sampling_decorator(self):
        # 1. Disable sampling (0%)
        orig_rate = GLOBAL_CONFIG.sample_rate
        GLOBAL_CONFIG.sample_rate = 0.0

        @monitor_function("sampled_func")
        def func():
            pass

        for _ in range(10):
            func()

        traces = pypss.get_global_collector().get_traces()
        assert len(traces) == 0

        # 2. Enable sampling (100%)
        GLOBAL_CONFIG.sample_rate = 1.0
        func()
        assert len(pypss.get_global_collector().get_traces()) == 1

        GLOBAL_CONFIG.sample_rate = orig_rate

    def test_monitor_block_init_no_module_name_success(self, monkeypatch):
        # Mock inspect.stack to return a valid frame
        mock_frame = MagicMock()
        mock_frame.f_globals = {"__name__": "mock_module"}  # Simulate module name
        mock_stack = [
            None,
            (mock_frame, None, None, None, None, None),
        ]  # Only the first element (frame_info) is used.
        monkeypatch.setattr(inspect, "stack", lambda: mock_stack)

        # Mock inspect.getmodule to return a mock module
        mock_mod = MagicMock()
        mock_mod.__name__ = "my_dynamic_module"
        monkeypatch.setattr(inspect, "getmodule", lambda x: mock_mod)

        block = monitor_block("test_name")
        assert block.module_name == "my_dynamic_module"

    def test_monitor_block_init_no_module_name_index_error(self, monkeypatch):
        # Simulate inspect.stack() raising IndexError
        monkeypatch.setattr(inspect, "stack", MagicMock(side_effect=IndexError))

        block = monitor_block("test_name")
        assert block.module_name == "unknown"

    def test_monitor_block_init_no_module_name_attribute_error(self, monkeypatch):
        # Simulate inspect.stack() returning an invalid frame that causes AttributeError
        mock_frame = MagicMock()
        del mock_frame.f_globals  # Remove f_globals to cause AttributeError
        mock_stack = [None, (mock_frame, None, None, None, None, None)]
        monkeypatch.setattr(inspect, "stack", lambda: mock_stack)
        monkeypatch.setattr(
            inspect, "getmodule", MagicMock(return_value=None)
        )  # getmodule might return None

        block = monitor_block("test_name")
        assert block.module_name == "unknown"

    def test_monitor_block_sampling_skipped(self, monkeypatch):
        # Set sample rate to 0.5 and random to return 0.7, so 0.7 > 0.5 -> skip sampling
        monkeypatch.setattr(GLOBAL_CONFIG, "sample_rate", 0.5)
        monkeypatch.setattr(random, "random", lambda: 0.7)

        with monitor_block("skipped_block"):
            time.sleep(0.001)

        traces = pypss.get_global_collector().get_traces()
        assert len(traces) == 0

    def test_monitor_block_error_sampling_override_skip(self, monkeypatch):
        # Simulate an error occurring
        class CustomError(Exception):
            pass

        # Set initial sample rate to 1.0 (to enter the block)
        monkeypatch.setattr(GLOBAL_CONFIG, "sample_rate", 1.0)
        # Set error_sample_rate to 0.0 (to force skipping on error)
        monkeypatch.setattr(GLOBAL_CONFIG, "error_sample_rate", 0.0)
        # Random should return 0.0 so random.random() > error_sample_rate is False.
        # However, because error_sample_rate is 0.0, any random > 0.0 should trigger skip.
        # Let's set random to 0.5 to ensure the "random.random() > current_sample_rate" condition for skipping is met.
        monkeypatch.setattr(random, "random", lambda: 0.5)

        with pytest.raises(CustomError):
            with monitor_block("error_skipped_block"):
                raise CustomError("Error in block")

        traces = pypss.get_global_collector().get_traces()
        # Even though an error occurred, the error sampling rate should cause it to be skipped.
        assert len(traces) == 0

    def test_monitor_function_error_sampling_override_skip_sync(self, monkeypatch):
        class CustomError(Exception):
            pass

        monkeypatch.setattr(GLOBAL_CONFIG, "sample_rate", 1.0)  # Enter the function
        monkeypatch.setattr(
            GLOBAL_CONFIG, "error_sample_rate", 0.0
        )  # Ensure error is sampled out
        monkeypatch.setattr(
            random, "random", lambda: 0.5
        )  # random > error_sample_rate -> skip

        @monitor_function("error_skipped_func")
        def func_with_error():
            raise CustomError("Error in func")

        # Call the function directly, the exception will be suppressed by the decorator's finally block
        # as it's sampled out.
        func_with_error()

        traces = pypss.get_global_collector().get_traces()
        assert len(traces) == 0  # Verify that no trace was collected.
