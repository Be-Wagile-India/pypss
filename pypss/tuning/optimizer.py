import random
from typing import List, Dict, Any, Tuple
from dataclasses import replace
from collections import Counter

# Import for Bayesian Optimization
from skopt import gp_minimize
from skopt.space import Real

from ..utils.config import PSSConfig

# Importing internal scoring functions.
# NOTE: This relies on internal implementation details of pypss.core.core.
from ..core.core import (
    _calculate_timing_stability_score,
    _calculate_memory_stability_score,
    _calculate_error_volatility_score,
    _calculate_branching_entropy_score,
    _calculate_concurrency_chaos_score,
)


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

    def _compute_score(
        self, traces: List[Dict[str, Any]], config: PSSConfig
    ) -> Tuple[float, Dict[str, float]]:
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

        # Extract vectors (simplified extraction compared to core.py which handles streaming)
        latencies = [float(t.get("duration", 0.0)) for t in traces]
        memory_samples = [float(t.get("memory", 0.0)) for t in traces]
        wait_times = [float(t.get("wait_time", 0.0)) for t in traces]
        errors = [1 if t.get("error", False) else 0 for t in traces]

        branch_tags = [t.get("branch_tag") for t in traces if t.get("branch_tag")]
        branch_tags_counter = Counter(branch_tags)

        # System metrics extraction (simplified)
        system_metrics: Dict[str, List[float]] = {"lag": []}
        for t in traces:
            if t.get("system_metric") and "lag" in t.get("metadata", {}):
                system_metrics["lag"].append(t["metadata"]["lag"])

        # Calculate individual scores
        ts_score = _calculate_timing_stability_score(latencies, config)
        ms_score = _calculate_memory_stability_score(memory_samples, config)
        ev_score = _calculate_error_volatility_score(errors, config)
        be_score = _calculate_branching_entropy_score(branch_tags_counter)
        cc_score = _calculate_concurrency_chaos_score(
            wait_times, config, system_metrics
        )

        # Weighted Sum
        pss_raw = (
            config.w_ts * ts_score
            + config.w_ms * ms_score
            + config.w_ev * ev_score
            + config.w_be * be_score
            + config.w_cc * cc_score
        )

        total_weight = (
            config.w_ts + config.w_ms + config.w_ev + config.w_be + config.w_cc
        )
        if total_weight > 0:
            pss_raw /= total_weight

        individual_scores = {
            "ts_score": ts_score,
            "ms_score": ms_score,
            "ev_score": ev_score,
            "be_score": be_score,
            "cc_score": cc_score,
        }

        # Return 0-100 score and individual scores
        return pss_raw * 100.0, individual_scores

    def calculate_loss(self, config: PSSConfig) -> float:
        """
        Loss function to minimize.
        Loss = (100 - Baseline_Overall_Score)^2
               + sum((Faulty_Overall_Score - Target_Faulty_Overall_Score)^2)
               + sum(Targeted_Metric_Penalty)
        """
        baseline_overall_score, baseline_individual_scores = self._compute_score(
            self.baseline_traces, config
        )

        # We want baseline overall PSS to be 100
        loss = (100.0 - baseline_overall_score) ** 2

        # We want faulty overall PSS scores to be low (e.g., 40-50)
        target_overall_fault_score = 45.0

        # Define which individual metric is primarily targeted by each fault type
        fault_to_metric_map = {
            "latency_jitter": "ts_score",
            "memory_leak": "ms_score",
            "error_burst": "ev_score",
            "thread_starvation": "cc_score",
        }

        # Penalties for metric weights for general use-cases
        # Penalize if weights are too skewed towards metrics not relevant to the fault

        for fault_type, traces in self.faulty_traces_map.items():
            fault_overall_score, fault_individual_scores = self._compute_score(
                traces, config
            )

            # Penalty for overall faulty PSS not being low enough
            loss += (fault_overall_score - target_overall_fault_score) ** 2

            # Targeted Metric Penalty:
            # If this fault type targets a specific metric, penalize if that metric
            # didn't significantly drop compared to the baseline.
            if fault_type in fault_to_metric_map:
                targeted_metric = fault_to_metric_map[fault_type]

                fault_metric_score = fault_individual_scores.get(targeted_metric, 1.0)

                # We want fault_metric_score to be much less than 1.0 when that fault type is present.
                # Penalize if fault_metric_score is too high (e.g., > 0.8, meaning the metric is still stable)
                # The magnitude of penalty can be adjusted.
                fault_detection_threshold = (
                    0.7  # We want the faulty metric score to drop below this
                )
                if fault_metric_score > fault_detection_threshold:
                    loss += (
                        fault_metric_score - fault_detection_threshold
                    ) ** 2 * 100  # Stronger penalty

                # Additionally, penalize if the drop in the *overall* score is not primarily driven by the targeted metric's weight.
                # This is more complex and might require examining the gradient of the overall score wrt weights,
                # or a comparative penalty (e.g., if w_ts * ts_score is not the largest contributor to score drop for latency fault)
                # For now, let's keep it simpler and focus on making the individual metric score drop.

        return loss

    def optimize(self, iterations: int = 50) -> Tuple[PSSConfig, float]:
        """
        Runs a Bayesian Optimization (Gaussian Process) loop to find the best configuration.

        Args:
            iterations: Number of optimization iterations (n_calls for gp_minimize).

        Returns:
            Tuple of (Best Config, Best Loss)
        """
        # Define the search space for parameters
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

        # Best initial config from defaults (or previous best)
        initial_config = PSSConfig()

        # initial_point was removed (F841 fix)

        def objective_function(params):
            # Extract parameters from the list in the order defined in dimensions
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

            # Normalize weights so they sum to 1.0
            sum_weights = w_ts + w_ms + w_ev + w_be + w_cc
            if sum_weights > 0:
                w_ts /= sum_weights
                w_ms /= sum_weights
                w_ev /= sum_weights
                w_be /= sum_weights
                w_cc /= sum_weights
            else:  # Distribute evenly if sum is 0
                w_ts = w_ms = w_ev = w_be = w_cc = 1.0 / 5.0

            # Create a candidate PSSConfig
            candidate_config = replace(
                initial_config,  # Start from a clean slate or the default
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

            # Calculate and return the loss
            return self.calculate_loss(candidate_config)

        # Run Bayesian Optimization
        res = gp_minimize(
            objective_function,
            dimensions,
            n_calls=iterations,
            random_state=random.randint(0, 10000),  # For reproducibility if needed
            initial_point_generator="random",  # Use random points for initial exploration
            # x0=[initial_point], # You can also specify an initial point if desired
        )

        # Extract the best parameters found
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

        # Normalize weights from the best_params again, just to be safe
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
            initial_config,  # Start from a clean slate or the default
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
