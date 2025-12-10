import random
from collections import Counter
from dataclasses import replace
from typing import Any, Dict, List, Tuple

from skopt import gp_minimize
from skopt.space import Real

from ..core.core import (
    _calculate_branching_entropy_score,
    _calculate_concurrency_chaos_score,
    _calculate_error_volatility_score,
    _calculate_memory_stability_score,
    _calculate_timing_stability_score,
)
from ..utils.config import PSSConfig


class ConfigOptimizer:
    """
    Optimizes PyPSS configuration parameters to maximize separation between
    baseline (healthy) traces and synthetic (faulty) traces.
    """

    def __init__(
        self,
        baseline_traces: List[Dict[str, Any]],
        faulty_traces_map: Dict[str, List[Dict[str, Any]]],
    ):
        """
        Args:
            baseline_traces: List of healthy traces.
            faulty_traces_map: Dictionary mapping fault types (e.g., 'latency', 'memory')
                               to lists of faulty traces.
        """
        self.baseline_traces = baseline_traces
        self.faulty_traces_map = faulty_traces_map

    def _compute_score(self, traces: List[Dict[str, Any]], config: PSSConfig) -> Tuple[float, Dict[str, float]]:
        """
        Replicates the scoring logic from pypss.core.core but uses a specific config instance.
        """
        if not traces:
            return 0.0, {
                "ts_score": 0.0,
                "ms_score": 0.0,
                "ev_score": 0.0,
                "be_score": 0.0,
                "cc_score": 0.0,
            }

        latencies = [float(t.get("duration", 0.0)) for t in traces]
        memory_samples = [float(t.get("memory", 0.0)) for t in traces]
        wait_times = [float(t.get("wait_time", 0.0)) for t in traces]
        errors = [1 if t.get("error", False) else 0 for t in traces]

        branch_tags = [t.get("branch_tag") for t in traces if t.get("branch_tag")]
        branch_tags_counter = Counter(branch_tags)

        system_metrics: Dict[str, List[float]] = {"lag": []}
        for t in traces:
            if t.get("system_metric") and "lag" in t.get("metadata", {}):
                system_metrics["lag"].append(t["metadata"]["lag"])

        ts_score = _calculate_timing_stability_score(latencies, config)
        ms_score = _calculate_memory_stability_score(memory_samples, config)
        ev_score = _calculate_error_volatility_score(errors, config)
        be_score = _calculate_branching_entropy_score(branch_tags_counter)
        cc_score = _calculate_concurrency_chaos_score(wait_times, config, system_metrics)

        pss_raw = (
            config.w_ts * ts_score
            + config.w_ms * ms_score
            + config.w_ev * ev_score
            + config.w_be * be_score
            + config.w_cc * cc_score
        )

        total_weight = config.w_ts + config.w_ms + config.w_ev + config.w_be + config.w_cc
        if total_weight > 0:
            pss_raw /= total_weight

        individual_scores = {
            "ts_score": ts_score,
            "ms_score": ms_score,
            "ev_score": ev_score,
            "be_score": be_score,
            "cc_score": cc_score,
        }

        return pss_raw * 100.0, individual_scores

    def calculate_loss(self, config: PSSConfig) -> float:
        """
        Loss function to minimize.
        """
        baseline_overall_score, baseline_individual_scores = self._compute_score(self.baseline_traces, config)

        loss = (100.0 - baseline_overall_score) ** 2

        target_overall_fault_score = 45.0

        fault_to_metric_map = {
            "latency_jitter": "ts_score",
            "memory_leak": "ms_score",
            "error_burst": "ev_score",
            "thread_starvation": "cc_score",
        }

        for fault_type, traces in self.faulty_traces_map.items():
            fault_overall_score, fault_individual_scores = self._compute_score(traces, config)

            loss += (fault_overall_score - target_overall_fault_score) ** 2

            if fault_type in fault_to_metric_map:
                targeted_metric = fault_to_metric_map[fault_type]

                fault_metric_score = fault_individual_scores.get(targeted_metric, 1.0)

                fault_detection_threshold = 0.7
                if fault_metric_score > fault_detection_threshold:
                    loss += (fault_metric_score - fault_detection_threshold) ** 2 * 100

        return loss

    def optimize(self, iterations: int = 50) -> Tuple[PSSConfig, float]:
        """
        Runs a Bayesian Optimization (Gaussian Process) loop to find the best configuration.

        Args:
            iterations: Number of optimization iterations (n_calls for gp_minimize).

        Returns:
            Tuple of (Best Config, Best Loss)
        """
        dimensions = [
            Real(0.5, 5.0, name="alpha"),
            Real(0.5, 5.0, name="beta"),
            Real(0.5, 5.0, name="gamma"),
            Real(1.1, 3.0, name="mem_spike_threshold_ratio"),
            Real(0.0001, 0.05, name="concurrency_wait_threshold"),
            Real(0.0, 1.0, name="w_ts"),
            Real(0.0, 1.0, name="w_ms"),
            Real(0.0, 1.0, name="w_ev"),
            Real(0.0, 1.0, name="w_be"),
            Real(0.0, 1.0, name="w_cc"),
        ]

        initial_config = PSSConfig()

        def objective_function(params):
            (
                alpha,
                beta,
                gamma,
                mem_spike_threshold_ratio,
                concurrency_wait_threshold,
                w_ts,
                w_ms,
                w_ev,
                w_be,
                w_cc,
            ) = params

            sum_weights = w_ts + w_ms + w_ev + w_be + w_cc
            if sum_weights > 0:
                w_ts /= sum_weights
                w_ms /= sum_weights
                w_ev /= sum_weights
                w_be /= sum_weights
                w_cc /= sum_weights
            else:
                w_ts = w_ms = w_ev = w_be = w_cc = 1.0 / 5.0

            candidate_config = replace(
                initial_config,
                alpha=alpha,
                beta=beta,
                gamma=gamma,
                mem_spike_threshold_ratio=mem_spike_threshold_ratio,
                concurrency_wait_threshold=concurrency_wait_threshold,
                w_ts=w_ts,
                w_ms=w_ms,
                w_ev=w_ev,
                w_be=w_be,
                w_cc=w_cc,
            )

            return self.calculate_loss(candidate_config)

        res = gp_minimize(
            objective_function,
            dimensions,
            n_calls=iterations,
            random_state=random.randint(0, 10000),
            initial_point_generator="random",
        )

        best_params = res.x
        (
            alpha,
            beta,
            gamma,
            mem_spike_threshold_ratio,
            concurrency_wait_threshold,
            w_ts,
            w_ms,
            w_ev,
            w_be,
            w_cc,
        ) = best_params

        sum_weights = w_ts + w_ms + w_ev + w_be + w_cc
        if sum_weights > 0:
            w_ts /= sum_weights
            w_ms /= sum_weights
            w_ev /= sum_weights
            w_be /= sum_weights
            w_cc /= sum_weights
        else:
            w_ts = w_ms = w_ev = w_be = w_cc = 1.0 / 5.0

        best_config = replace(
            initial_config,
            alpha=alpha,
            beta=beta,
            gamma=gamma,
            mem_spike_threshold_ratio=mem_spike_threshold_ratio,
            concurrency_wait_threshold=concurrency_wait_threshold,
            w_ts=w_ts,
            w_ms=w_ms,
            w_ev=w_ev,
            w_be=w_be,
            w_cc=w_cc,
        )

        return best_config, res.fun
