import time
import pypss
from pypss.instrumentation import monitor_function
from pypss.utils.config import GLOBAL_CONFIG


class TestConcurrencyMetrics:
    def test_wait_time_detection(self):
        pypss.init()
        collector = pypss.get_global_collector()
        collector.clear()
        GLOBAL_CONFIG.sample_rate = 1.0

        @monitor_function("sleepy")
        def sleepy_func():
            # Sleep creates wait_time (Wall >> CPU)
            time.sleep(0.1)

        sleepy_func()

        traces = collector.get_traces()
        assert len(traces) == 1
        t = traces[0]

        assert "cpu_time" in t
        assert "wait_time" in t

        # Wall time should be ~0.1s
        assert t["duration"] >= 0.1
        # CPU time should be near 0
        assert t["cpu_time"] < 0.05
        # Wait time should be near 0.1s
        assert t["wait_time"] >= 0.05

    def test_cpu_bound_metrics(self):
        pypss.init()
        collector = pypss.get_global_collector()
        collector.clear()
        GLOBAL_CONFIG.sample_rate = 1.0

        @monitor_function("busy")
        def busy_func():
            # Busy loop (Wall ~= CPU)
            end = time.time() + 0.1
            while time.time() < end:
                pass

        busy_func()

        traces = collector.get_traces()
        assert len(traces) == 1
        t = traces[0]

        # Wall time ~0.1s
        assert t["duration"] >= 0.1
        # CPU time should be significant (close to Wall time)
        # Note: In CI environments, this might be flaky if CPU is throttled,
        # but locally it should hold.
        assert t["cpu_time"] > 0.05
        # Wait time should be small
        assert t["wait_time"] < 0.05
