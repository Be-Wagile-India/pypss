import math
import statistics
from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class BaselineProfile:
    """Statistical profile of a baseline trace dataset."""

    latency_mean: float = 0.0
    latency_median: float = 0.0
    latency_p95: float = 0.0
    latency_p99: float = 0.0
    latency_stddev: float = 0.0

    memory_mean: float = 0.0
    memory_peak: float = 0.0
    memory_variance: float = 0.0

    error_rate: float = 0.0

    total_traces: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Returns the profile as a dictionary."""
        return {
            "latency": {
                "mean": self.latency_mean,
                "median": self.latency_median,
                "p95": self.latency_p95,
                "p99": self.latency_p99,
                "stddev": self.latency_stddev,
            },
            "memory": {
                "mean": self.memory_mean,
                "peak": self.memory_peak,
                "variance": self.memory_variance,
            },
            "errors": {
                "rate": self.error_rate,
            },
            "total_traces": self.total_traces,
        }


class Profiler:
    """Analyzes a collection of traces to produce a statistical baseline."""

    def __init__(self, traces: List[Dict[str, Any]]):
        """
        Initialize the Profiler.

        Args:
            traces: List of trace dictionaries (deserialized JSON or TraceMessage dicts).
        """
        self.traces = traces

    def profile(self) -> BaselineProfile:
        """
        Calculate statistical properties of the trace dataset.

        Returns:
            BaselineProfile object containing the stats.
        """
        if not self.traces:
            return BaselineProfile()

        durations = [float(t.get("duration", 0.0)) for t in self.traces]
        memories = [float(t.get("memory", 0)) for t in self.traces]
        errors = [1 if t.get("error", False) else 0 for t in self.traces]

        latency_mean = statistics.mean(durations)
        latency_median = statistics.median(durations)
        try:
            latency_stddev = statistics.stdev(durations)
        except statistics.StatisticsError:
            latency_stddev = 0.0

        sorted_durations = sorted(durations)
        n = len(sorted_durations)

        def get_percentile(p: float) -> float:
            if n == 0:
                return 0.0
            k = (n - 1) * p
            f = math.floor(k)
            c = math.ceil(k)
            if f == c:
                return sorted_durations[int(k)]
            d0 = sorted_durations[int(f)]
            d1 = sorted_durations[int(c)]
            return d0 + (d1 - d0) * (k - f)

        latency_p95 = get_percentile(0.95)
        latency_p99 = get_percentile(0.99)

        memory_mean = statistics.mean(memories) if memories else 0.0
        memory_peak = max(memories) if memories else 0.0
        try:
            memory_variance = statistics.variance(memories) if len(memories) > 1 else 0.0
        except statistics.StatisticsError:
            memory_variance = 0.0

        error_rate = sum(errors) / len(errors) if errors else 0.0

        return BaselineProfile(
            latency_mean=latency_mean,
            latency_median=latency_median,
            latency_p95=latency_p95,
            latency_p99=latency_p99,
            latency_stddev=latency_stddev,
            memory_mean=memory_mean,
            memory_peak=memory_peak,
            memory_variance=memory_variance,
            error_rate=error_rate,
            total_traces=len(self.traces),
        )
