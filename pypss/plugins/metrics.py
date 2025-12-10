import logging
import re
import statistics
from typing import Dict, Iterable

from ..utils import (
    GLOBAL_CONFIG,
    calculate_cv,
    exponential_decay_score,
    normalize_score,
)
from .base import BaseMetric

logger = logging.getLogger(__name__)


class IOStabilityMetric(BaseMetric):
    """
    Measures the consistency of I/O operations.

    It calculates the ratio of 'wait_time' (I/O) to total 'duration' for each trace.
    The score is based on the Coefficient of Variation (CV) of these I/O ratios.

    High Stability (Score ~1.0): I/O overhead is consistent across requests.
    Low Stability (Score <1.0): I/O overhead fluctuates wildly (jittery network/disk).
    """

    code = "IO"
    name = "I/O Stability"
    default_weight = 0.15

    def compute(self, traces: Iterable[Dict]) -> float:
        io_ratios = []
        traces_list = list(traces)

        for t in traces_list:
            duration = t.get("duration", 0.0)
            wait_time = t.get("wait_time", 0.0)

            if duration > 0.0001:
                ratio = max(0.0, min(1.0, wait_time / duration))
                io_ratios.append(ratio)

        if len(io_ratios) < 2:
            return 1.0

        cv = calculate_cv(io_ratios)

        sensitivity = GLOBAL_CONFIG.alpha

        return exponential_decay_score(cv, sensitivity)


class DBStabilityMetric(BaseMetric):
    """
    Measures the consistency of database interaction durations.

    It identifies traces related to database operations using keywords in their name or module.
    The score is based on the Coefficient of Variation (CV) of the durations of these DB traces.

    High Stability (Score ~1.0): Database query times are consistent.
    Low Stability (Score <1.0): Database query times are erratic.
    """

    code = "DB"
    name = "Database Stability"
    default_weight = 0.2

    DB_KEYWORDS = [
        "db",
        "sql",
        "mongo",
        "redis",
        "query",
        "database",
        "orm",
        "execute",
        "fetch",
        "commit",
        "rollback",
        "write",
    ]
    DB_PATTERN = re.compile(r"|".join(DB_KEYWORDS), re.IGNORECASE)

    def compute(self, traces: Iterable[Dict]) -> float:
        db_durations = []
        traces_list = list(traces)

        for t in traces_list:
            name = t.get("name", "")
            module = t.get("module", "")
            branch_tag = t.get("branch_tag", "")

            if self.DB_PATTERN.search(name) or self.DB_PATTERN.search(module) or self.DB_PATTERN.search(branch_tag):
                duration = t.get("duration", 0.0)
                if duration > 0:
                    db_durations.append(duration)

        if len(db_durations) < 2:
            return 1.0

        cv = calculate_cv(db_durations)

        sensitivity = GLOBAL_CONFIG.alpha

        return exponential_decay_score(cv, sensitivity)


class GCStabilityMetric(BaseMetric):
    """
    Measures the consistency of Garbage Collection (GC) pauses or memory management.

    If direct GC pause durations are not available, it attempts to infer GC-related instability
    from the variance of negative `memory_diff` values (i.e., memory deallocation events).

    High Stability (Score ~1.0): Consistent GC impact.
    Low Stability (Score <1.0): Erratic GC pauses or memory deallocation patterns.
    """

    code = "GC"
    name = "GC Stability"
    default_weight = 0.1

    def compute(self, traces: Iterable[Dict]) -> float:
        gc_pause_durations = []
        negative_memory_diffs = []

        traces_list = list(traces)

        for t in traces_list:
            if t.get("system_metric"):
                meta = t.get("metadata", {})
                if "gc_pause_duration" in meta and meta["gc_pause_duration"] > 0:
                    gc_pause_durations.append(meta["gc_pause_duration"])

            mem_diff = t.get("memory_diff")
            if mem_diff is not None and mem_diff <= -100:
                negative_memory_diffs.append(abs(mem_diff))

        cv = 0.0
        if len(gc_pause_durations) >= 2:
            cv = calculate_cv(gc_pause_durations)
        elif len(negative_memory_diffs) >= 2:
            cv = calculate_cv(negative_memory_diffs)
        else:
            return 1.0

        sensitivity = GLOBAL_CONFIG.gamma

        score = exponential_decay_score(cv, sensitivity)
        return score


class CacheStabilityMetric(BaseMetric):
    """
    Measures the stability of cache hit ratios.

    It identifies traces with 'branch_tag' as 'cache_hit' or 'cache_miss'
    and calculates the overall hit ratio. A lower hit ratio leads to a lower score.

    High Stability (Score ~1.0): High and consistent cache hit rate.
    Low Stability (Score <1.0): Low or erratic cache hit rate.
    """

    code = "CACHE"
    name = "Cache Stability"
    default_weight = 0.15

    def compute(self, traces: Iterable[Dict]) -> float:
        hits = 0
        misses = 0
        traces_list = list(traces)

        for t in traces_list:
            branch_tag = t.get("branch_tag", "").lower()
            if "cache_hit" in branch_tag:
                hits += 1
            elif "cache_miss" in branch_tag:
                misses += 1

        total_cache_ops = hits + misses
        if total_cache_ops == 0:
            return 1.0

        hit_ratio = hits / total_cache_ops

        return normalize_score(hit_ratio)


class ThreadStarvationMetric(BaseMetric):
    """
    Measures the impact of thread/task starvation in concurrent applications.

    It analyzes `lag` data from system metrics. High mean `lag` indicates
    significant delays in task execution due to starvation or scheduling issues.

    High Stability (Score ~1.0): Low and consistent lag.
    Low Stability (Score <1.0): High or erratic lag.
    """

    code = "STARVE"
    name = "Thread Starvation"
    default_weight = 0.1

    def compute(self, traces: Iterable[Dict]) -> float:
        lags = []
        traces_list = list(traces)

        for t in traces_list:
            if t.get("system_metric"):
                meta = t.get("metadata", {})
                if "lag" in meta and meta["lag"] > 0:
                    lags.append(meta["lag"])

        if len(lags) < 2:
            return 1.0

        mean_lag = statistics.mean(lags)

        sensitivity_factor = getattr(GLOBAL_CONFIG, "thread_starvation_sensitivity", 50.0)

        return exponential_decay_score(mean_lag, sensitivity_factor)


class NetworkStabilityMetric(BaseMetric):
    """
    Measures the consistency of network request durations.

    It identifies traces related to network calls using keywords in their name, module, or branch_tag.
    The score is based on the Coefficient of Variation (CV) of the durations of these network traces.

    High Stability (Score ~1.0): Network request latencies are consistent.
    Low Stability (Score <1.0): Network request latencies are erratic (jittery).
    """

    code = "NET"
    name = "Network Jitter Stability"
    default_weight = 0.15

    NET_KEYWORDS = [
        "http",
        "https",
        "request",
        "fetch",
        "api",
        "get",
        "post",
        "put",
        "delete",
        "patch",
        "connect",
        "send",
        "recv",
        "socket",
        "url",
        "endpoint",
        "remote",
    ]
    NET_PATTERN = re.compile(r"|".join(NET_KEYWORDS), re.IGNORECASE)

    def compute(self, traces: Iterable[Dict]) -> float:
        net_durations = []
        traces_list = list(traces)

        for t in traces_list:
            name = t.get("name", "")
            module = t.get("module", "")
            branch_tag = t.get("branch_tag", "")

            if self.NET_PATTERN.search(name) or self.NET_PATTERN.search(module) or self.NET_PATTERN.search(branch_tag):
                duration = t.get("duration", 0.0)
                if duration > 0:
                    net_durations.append(duration)

        if len(net_durations) < 2:
            return 1.0

        cv = calculate_cv(net_durations)

        sensitivity = getattr(GLOBAL_CONFIG, "alpha", 2.0)

        return exponential_decay_score(cv, sensitivity)


class KafkaLagStabilityMetric(BaseMetric):
    """
    Measures the stability of Kafka consumer lag.

    It analyzes 'kafka_lag' data from system metrics reported via `report_kafka_lag`.
    High mean lag or high variance in lag indicates instability in consumer processing.

    High Stability (Score ~1.0): Lag is consistently low.
    Low Stability (Score <1.0): Lag is high or fluctuating wildly (bursty consumption).
    """

    code = "KAFKA"
    name = "Kafka Lag Stability"
    default_weight = 0.15

    def compute(self, traces: Iterable[Dict]) -> float:
        lags = []
        traces_list = list(traces)

        for t in traces_list:
            if t.get("system_metric"):
                meta = t.get("metadata", {})
                if "kafka_lag" in meta:
                    lags.append(meta["kafka_lag"])

        if len(lags) < 2:
            return 1.0

        mean_lag = statistics.mean(lags)

        normalized_lag = mean_lag / 100.0

        sensitivity = getattr(GLOBAL_CONFIG, "kafka_lag_sensitivity", 1.0)

        return exponential_decay_score(normalized_lag, sensitivity)
