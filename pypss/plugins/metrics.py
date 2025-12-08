from typing import Iterable, Dict
import statistics
import re
from .base import BaseMetric
from ..utils import (
    calculate_cv,
    exponential_decay_score,
    normalize_score,
    GLOBAL_CONFIG,
)
import logging

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
        # Ensure traces are materialized if they might be an iterator
        traces_list = list(traces)

        for t in traces_list:
            duration = t.get("duration", 0.0)
            wait_time = t.get("wait_time", 0.0)

            # Filter out negligible durations to avoid division instability
            if duration > 0.0001:
                # Clamp ratio between 0 and 1
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

    # Keywords to identify DB-related traces
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
        traces_list = list(traces)  # Materialize

        for t in traces_list:
            name = t.get("name", "")
            module = t.get("module", "")
            branch_tag = t.get("branch_tag", "")

            # Check if the trace is DB-related
            if (
                self.DB_PATTERN.search(name)
                or self.DB_PATTERN.search(module)
                or self.DB_PATTERN.search(branch_tag)
            ):
                duration = t.get("duration", 0.0)
                if duration > 0:
                    db_durations.append(duration)

        if len(db_durations) < 2:
            return 1.0  # No sufficient data or perfectly stable

        cv = calculate_cv(db_durations)

        sensitivity = GLOBAL_CONFIG.alpha  # Using global alpha for now

        return exponential_decay_score(cv, sensitivity)


class GCStabilityMetric(BaseMetric):
    """
    Measures the consistency of Garbage Collection (GC) pauses or memory management.

    This metric assumes that traces may contain `gc_pause_duration` in their metadata
    (e.g., from system-level monitoring). It calculates the Coefficient of Variation (CV)
    of these GC pause durations.

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

        traces_list = list(traces)  # Materialize traces

        for t in traces_list:  # Iterate over the materialized list
            # Look for explicit GC pause durations in system metrics
            if t.get("system_metric"):
                meta = t.get("metadata", {})
                if "gc_pause_duration" in meta and meta["gc_pause_duration"] > 0:
                    gc_pause_durations.append(meta["gc_pause_duration"])

            # Fallback: analyze significant negative memory diffs in regular traces
            mem_diff = t.get("memory_diff")
            if (
                mem_diff is not None and mem_diff <= -100
            ):  # Threshold for significant deallocation
                negative_memory_diffs.append(abs(mem_diff))

        cv = 0.0  # Initialize cv
        if len(gc_pause_durations) >= 2:
            cv = calculate_cv(gc_pause_durations)
        elif len(negative_memory_diffs) >= 2:
            # Fallback to CV of absolute negative memory diffs
            cv = calculate_cv(negative_memory_diffs)
        else:
            return 1.0  # Not enough data, assume stable

        sensitivity = GLOBAL_CONFIG.gamma  # Use directly

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
        traces_list = list(traces)  # Materialize

        for t in traces_list:
            branch_tag = t.get("branch_tag", "").lower()
            if "cache_hit" in branch_tag:
                hits += 1
            elif "cache_miss" in branch_tag:
                misses += 1

        total_cache_ops = hits + misses
        if total_cache_ops == 0:
            return 1.0  # No cache operations, assume stable

        hit_ratio = hits / total_cache_ops

        # Normalize the hit_ratio to a score between 0 and 1.
        # A simple linear normalization: if hit_ratio is 0.5, score is 0.5.
        # Can be made more sophisticated with thresholds if needed.
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
        traces_list = list(traces)  # Materialize

        for t in traces_list:
            if t.get("system_metric"):
                meta = t.get("metadata", {})
                if "lag" in meta and meta["lag"] > 0:
                    lags.append(meta["lag"])

        if len(lags) < 2:
            return 1.0  # Not enough data, assume stable

        mean_lag = statistics.mean(lags)

        # Penalize high mean lag using exponential decay.
        # Higher lag value (more starvation) should result in lower score.
        # A small `mean_lag` (e.g., 0.001s) should give a high score (~0.95).
        # A larger `mean_lag` (e.g., 0.05s) should give a very low score (~0.05).

        # Determine sensitivity factor for mean_lag.
        # For mean_lag=0.001, we want score ~0.95. e^(-factor * 0.001) = 0.95 => factor ~= 51
        # For mean_lag=0.05, we want score ~0.05. e^(-factor * 0.05) = 0.05 => factor ~= 60
        # Let's use a default sensitivity factor that balances this.
        # A factor around 50.0 to 60.0 seems reasonable.

        sensitivity_factor = getattr(
            GLOBAL_CONFIG, "thread_starvation_sensitivity", 50.0
        )

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

    # Keywords to identify Network-related traces
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

            if (
                self.NET_PATTERN.search(name)
                or self.NET_PATTERN.search(module)
                or self.NET_PATTERN.search(branch_tag)
            ):
                duration = t.get("duration", 0.0)
                if duration > 0:
                    net_durations.append(duration)

        if len(net_durations) < 2:
            return 1.0

        cv = calculate_cv(net_durations)

        # Sensitivity can be tuned. Using GLOBAL_CONFIG.alpha for now.
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
            return 1.0  # Insufficient data

        mean_lag = statistics.mean(lags)
        # Normalize mean lag. A lag of 0 is perfect. A lag of 1000 might be bad.
        # Let's say lag > 100 starts penalizing.
        # We also care about consistency (CV).
        # But primarily high lag is the issue. Let's stick to mean lag penalization like thread starvation.
        # Lag is integer (messages).

        # Simple exponential decay on normalized lag.
        # Assume tolerance is 100 messages.
        normalized_lag = mean_lag / 100.0

        sensitivity = getattr(GLOBAL_CONFIG, "kafka_lag_sensitivity", 1.0)

        return exponential_decay_score(normalized_lag, sensitivity)
