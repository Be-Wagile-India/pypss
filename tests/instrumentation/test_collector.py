import threading

from pypss.instrumentation.collectors import Collector
from pypss.utils import GLOBAL_CONFIG


class TestAdvancedCollector:
    def test_thread_safety(self):
        # Increase max_traces to ensure shard capacity doesn't limit the test
        # even if all threads hash to the same shard.
        original_max = GLOBAL_CONFIG.max_traces
        GLOBAL_CONFIG.max_traces = 50000  # 50000 // 16 = 3125 > 1000 items

        collector = Collector()
        # No sampling in collector anymore, so every add_trace adds to buffer

        def worker():
            for i in range(100):
                collector.add_trace({"id": i})

        threads = []
        for _ in range(10):
            t = threading.Thread(target=worker)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        traces = collector.get_traces()
        GLOBAL_CONFIG.max_traces = original_max  # Reset
        assert len(traces) == 1000  # 10 threads * 100 items

    def test_ring_buffer(self):
        # Configure small buffer via global config for this test
        original_max = GLOBAL_CONFIG.max_traces
        GLOBAL_CONFIG.max_traces = 10

        # Re-init collector to pick up new config
        collector = Collector()

        for i in range(20):
            collector.add_trace({"id": i})

        traces = collector.get_traces()
        assert len(traces) == 10
        # Should contain the last 10 (10-19)
        assert traces[0]["id"] == 10
        assert traces[-1]["id"] == 19

        GLOBAL_CONFIG.max_traces = original_max
