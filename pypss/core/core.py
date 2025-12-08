# Core score computation and algorithms
import math
import statistics
import array
from collections import Counter
from typing import Iterable, Dict, Union, Optional
from ..utils import (
    calculate_cv,
    calculate_entropy,
    exponential_decay_score,
    normalize_score,
)
from ..utils import GLOBAL_CONFIG


def _calculate_timing_stability_score(
    latencies: Union[list, array.array], conf
) -> float:
    ts_score = 1.0
    if not latencies:
        return ts_score

    # calculate_cv expects a sequence, array works
    cv = calculate_cv(latencies)

    tail_ratio = 1.0
    if len(latencies) > 1:
        # Create a sorted copy to avoid modifying the original list if it's used elsewhere
        quantiles = statistics.quantiles(latencies, n=100)
        p50 = quantiles[49]  # 50th percentile
        p95 = quantiles[conf.score_latency_tail_percentile]  # Configurable percentile
        if p50 > 0:
            tail_ratio = p95 / p50

    ts_part1 = exponential_decay_score(cv, conf.alpha)
    ts_part2 = 1.0 / (1.0 + conf.beta * max(0, tail_ratio - 1.0))
    ts_score = ts_part1 * ts_part2
    return ts_score


def _calculate_memory_stability_score(
    memory_samples: Union[list, array.array], conf
) -> float:
    ms_score = 1.0
    if not memory_samples or len(memory_samples) < 2:
        return ms_score

    mem_median = statistics.median(memory_samples)
    mem_peak = max(memory_samples)

    # Add a small epsilon to prevent division by zero or near-zero
    mem_median += conf.score_memory_epsilon

    if mem_median <= conf.score_memory_epsilon:
        # If median is zero, and we have samples, it means constant zero memory or some issue.
        # If peak is also zero, score is 1.0. Otherwise, very unstable.
        return 1.0 if mem_peak == 0 else 0.0

    mem_std = statistics.stdev(memory_samples)

    # Primary metric combines deviation and peak relative to median
    metric = (mem_std / mem_median) + (mem_peak / mem_median - 1.0)
    ms_score = exponential_decay_score(metric, conf.gamma)

    # Add a penalty for significant memory spikes
    if mem_peak / mem_median > conf.mem_spike_threshold_ratio:
        # Proportional penalty based on how much it exceeds the threshold
        spike_penalty = (mem_peak / mem_median) - conf.mem_spike_threshold_ratio
        ms_score *= exponential_decay_score(
            spike_penalty, conf.gamma
        )  # Apply more gamma sensitivity

    return ms_score


def _calculate_error_volatility_score(errors: Union[list, array.array], conf) -> float:
    ev_score = 1.0
    if not errors:
        return ev_score

    # errors is boolean 0/1, so sum is count
    total_errors = sum(errors)
    total_traces = len(errors)

    if total_traces == 0:
        return ev_score

    mean_count = total_errors / total_traces

    vmr = 0.0
    if total_traces > 1 and mean_count > 0:
        try:
            variance = statistics.variance(errors)
            vmr = variance / mean_count
        except (
            statistics.StatisticsError
        ):  # Handle case of all identical values in error_counts (variance is 0)
            vmr = 0.0

    # Base score using mean error rate and VMR
    ev_score = exponential_decay_score(
        mean_count + conf.score_error_vmr_multiplier * vmr, conf.delta
    )

    # Penalty for error spikes (sudden high error rate)
    if mean_count > conf.error_spike_threshold:
        spike_impact = (mean_count - conf.error_spike_threshold) / (
            1.0 - conf.error_spike_threshold
        )  # Normalize impact
        ev_score *= (
            1.0 - spike_impact * conf.score_error_spike_impact_multiplier
        )  # Apply penalty for severe spikes

    # Penalty for consecutive errors
    consecutive_error_count = 0
    max_consecutive_errors = 0
    for is_error in errors:
        if is_error:
            consecutive_error_count += 1
        else:
            consecutive_error_count = 0
        max_consecutive_errors = max(max_consecutive_errors, consecutive_error_count)

    if max_consecutive_errors >= conf.consecutive_error_threshold:
        consecutive_penalty_factor = (
            max_consecutive_errors - conf.consecutive_error_threshold + 1
        )  # +1 to start penalty at threshold
        ev_score *= exponential_decay_score(
            consecutive_penalty_factor,
            conf.delta * conf.score_consecutive_error_decay_multiplier,
        )  # More aggressive decay for consecutive errors

    return ev_score


def _calculate_branching_entropy_score(branch_data: Union[list, Counter]) -> float:
    be_score = 1.0
    if not branch_data:
        return be_score

    # Handle both list of tags and pre-computed Counter
    if isinstance(branch_data, Counter):
        # We need calculate_entropy to handle dict/counter or we do it here
        # calculate_entropy typically takes a list. Let's assume we need to adapt.
        # Check pypss.utils.calculate_entropy implementation.
        # If it takes a list, we can recreate a distribution or calculate entropy from counts.
        # Entropy = - sum(p * log2(p)). p = count/total.
        total_count = branch_data.total()
        entropy = 0.0
        if total_count > 0:
            for count in branch_data.values():
                if count > 0:
                    p = count / total_count
                    entropy -= p * math.log2(p)

        unique_branches = len(branch_data)
    else:
        # Legacy list support
        entropy = calculate_entropy(branch_data)
        unique_branches = len(set(branch_data))

    if unique_branches > 1:
        max_entropy = math.log2(unique_branches)
        if max_entropy > 0:
            be_score = 1.0 - (entropy / max_entropy)
        else:
            be_score = (
                1.0  # Should not happen if unique_branches > 1, but as a safeguard
            )
    elif unique_branches == 1:
        be_score = 1.0
    # If unique_branches is 0 (covered by not branch_tags), be_score is 1.0
    return be_score


def _calculate_concurrency_chaos_score(
    wait_times: Union[list, array.array],
    conf,
    system_metrics: Optional[Dict[str, list]] = None,
) -> float:
    cc_score = 1.0

    # Base Score: Wait Time Variance (Standard)
    if not wait_times or len(wait_times) < 2:
        pass  # Keep 1.0 if no data
    else:
        mean_wait = sum(wait_times) / len(wait_times)
        if mean_wait > conf.concurrency_wait_threshold:
            cc_cv = calculate_cv(wait_times)
            cc_score = exponential_decay_score(cc_cv, conf.alpha)

    # Advanced Score: System Metrics (Event Loop Health)
    if system_metrics:
        # 1. Loop Lag Penalty
        lags = system_metrics.get("lag", [])
        if lags:
            mean_lag = sum(lags) / len(lags)
            # If mean lag > 10ms, penalize
            # Example: 100ms lag => heavy penalty
            if mean_lag > 0.01:
                lag_penalty = min(1.0, mean_lag * 5.0)  # 0.2s lag => 0 score modifier
                cc_score *= 1.0 - lag_penalty

        # 2. Task Churn Penalty (Stability of parallelism)
        # High churn rate (spikes) might indicate instability
        # Not implementing strict penalty yet without baseline

        # 3. Active Task Saturation
        active_tasks = system_metrics.get("active_tasks", [])
        if active_tasks:
            pass
            # If we have massive task spikes, minor penalty?
            # Let's keep it simple for now: Lag is the best proxy for chaos.

    return max(0.0, cc_score)


def compute_pss_from_traces(traces: Iterable[Dict]) -> dict:
    if traces is None:
        return {
            "pss": 0,
            "breakdown": {
                "timing_stability": 0,
                "memory_stability": 0,
                "error_volatility": 0,
                "branching_entropy": 0,
                "concurrency_chaos": 0,
            },
        }

    # 1. Extract Data Streamingly into efficient arrays
    latencies = array.array("d")
    memory_samples = array.array("d")
    wait_times = array.array("d")
    errors = array.array("b")  # signed char is sufficient for 0/1
    branch_tags_counter: Counter[str] = Counter()

    # System Metrics (for advanced scoring)
    system_metrics: Dict[str, list] = {"lag": [], "active_tasks": [], "churn_rate": []}

    count = 0
    for t in traces:
        # Check for system/meta traces first
        if t.get("system_metric"):
            meta = t.get("metadata", {})
            if "lag" in meta:
                system_metrics["lag"].append(meta["lag"])
            if "active_tasks" in meta:
                system_metrics["active_tasks"].append(meta["active_tasks"])
            if "churn_rate" in meta:
                system_metrics["churn_rate"].append(meta["churn_rate"])
            # System traces don't contribute to regular latencies/errors count
            continue

        count += 1
        # Use float() to handle potential Decimal from ijson
        latencies.append(float(t.get("duration", 0)))
        memory_samples.append(float(t.get("memory", 0)))
        wait_times.append(float(t.get("wait_time", 0)))
        errors.append(1 if t.get("error", False) else 0)

        tag = t.get("branch_tag")
        if tag is not None and isinstance(tag, str):
            branch_tags_counter[tag] += 1

    if count == 0 and not system_metrics["lag"]:
        return {
            "pss": 0,
            "breakdown": {
                "timing_stability": 0,
                "memory_stability": 0,
                "error_volatility": 0,
                "branching_entropy": 0,
                "concurrency_chaos": 0,
            },
        }

    conf = GLOBAL_CONFIG

    # Calculate individual scores
    ts_score = _calculate_timing_stability_score(latencies, conf)
    ms_score = _calculate_memory_stability_score(memory_samples, conf)
    ev_score = _calculate_error_volatility_score(errors, conf)
    be_score = _calculate_branching_entropy_score(branch_tags_counter)

    # CC Score now accepts system metrics
    cc_score = _calculate_concurrency_chaos_score(wait_times, conf, system_metrics)

    # Final PSS
    pss_raw = (
        conf.w_ts * ts_score
        + conf.w_ms * ms_score
        + conf.w_ev * ev_score
        + conf.w_be * be_score
        + conf.w_cc * cc_score
    )

    # Normalize if weights don't sum to 1
    total_weight = conf.w_ts + conf.w_ms + conf.w_ev + conf.w_be + conf.w_cc
    if total_weight > 0:
        pss_raw /= total_weight

    pss_final = round(normalize_score(pss_raw) * 100)

    return {
        "pss": pss_final,
        "breakdown": {
            "timing_stability": round(ts_score, 2),
            "memory_stability": round(ms_score, 2),
            "error_volatility": round(ev_score, 2),
            "branching_entropy": round(be_score, 2),
            "concurrency_chaos": round(cc_score, 2),
        },
    }
