from pypss.tuning.profiler import Profiler


class TestProfilerCoverage:
    def test_profiler_single_trace(self):
        # Trigger stdev exception (need < 2 data points)
        traces = [{"duration": 1.0, "memory": 100, "error": False}]
        profiler = Profiler(traces)
        profile = profiler.profile()
        assert profile.latency_stddev == 0.0
        assert profile.total_traces == 1

    def test_profiler_to_dict(self):
        traces = [{"duration": 1.0, "memory": 100, "error": False}]
        profiler = Profiler(traces)
        profile = profiler.profile()
        d = profile.to_dict()
        assert "latency" in d
        assert "memory" in d
        assert "errors" in d
        assert d["total_traces"] == 1
