import logging
import time

from pypss.utils.config import GLOBAL_CONFIG

logger = logging.getLogger(__name__)


class AdaptiveSampler:
    """
    Manages dynamic adjustment of the global sampling rate based on observed system metrics.
    """

    def __init__(self):
        self._current_sample_rate = GLOBAL_CONFIG.sample_rate
        self._last_adjustment_time = time.time()
        self._last_trace_count_time = time.time()
        self._last_metrics = {
            "lag": 0.0,
            "churn_rate": 0.0,
            "error_rate": 0.0,
            "qps": 0.0,
        }

    def update_metrics(
        self,
        lag: float | None = None,
        churn_rate: float | None = None,
        error_rate: float | None = None,
        trace_count: int = 0,
        **kwargs,
    ):
        """
        Receives updated system metrics and triggers a sampling rate adjustment if needed.
        """
        current_time = time.time()

        # Calculate QPS if trace_count is provided
        if trace_count > 0:
            duration = current_time - self._last_trace_count_time
            if duration > 0:
                qps = trace_count / duration
                self._last_metrics["qps"] = qps
            self._last_trace_count_time = current_time

        if lag is not None:
            self._last_metrics["lag"] = lag
        if churn_rate is not None:
            self._last_metrics["churn_rate"] = churn_rate
        if error_rate is not None:
            self._last_metrics["error_rate"] = error_rate

        self._last_metrics.update(kwargs)
        self._adjust_sample_rate()

    def _adjust_sample_rate(self):
        """
        Applies adaptive sampling strategy based on configured mode.
        """
        current_time = time.time()
        if (
            current_time - self._last_adjustment_time
            < GLOBAL_CONFIG.adaptive_sampler_min_interval
        ):
            return

        mode = GLOBAL_CONFIG.adaptive_sampler_mode
        new_rate = self._current_sample_rate

        # --- Mode Logic ---

        if mode == "high_load":
            # Priority: Reduce overhead under load
            if (
                self._last_metrics["qps"]
                > GLOBAL_CONFIG.adaptive_sampler_high_qps_threshold
            ):
                # Drop to min rate immediately
                new_rate = GLOBAL_CONFIG.adaptive_sampler_min_rate
            else:
                # Otherwise behave normally (Balanced)
                new_rate = self._calculate_balanced_rate(new_rate)

        elif mode == "error_triggered":
            # Priority: Catch errors
            if (
                self._last_metrics["error_rate"]
                > GLOBAL_CONFIG.adaptive_sampler_error_threshold
            ):
                new_rate = GLOBAL_CONFIG.adaptive_sampler_max_rate
            else:
                new_rate = self._calculate_balanced_rate(new_rate)

        elif mode == "surge":
            # Priority: Catch latency spikes
            if self._last_metrics["lag"] > GLOBAL_CONFIG.adaptive_sampler_lag_threshold:
                new_rate = GLOBAL_CONFIG.adaptive_sampler_max_rate
            else:
                new_rate = self._calculate_balanced_rate(new_rate)

        elif mode == "low_noise":
            # Priority: Quiet down if stable
            is_stable = (
                self._last_metrics["error_rate"]
                < GLOBAL_CONFIG.adaptive_sampler_error_threshold / 2
                and self._last_metrics["lag"]
                < GLOBAL_CONFIG.adaptive_sampler_lag_threshold / 2
                and self._last_metrics["churn_rate"]
                < GLOBAL_CONFIG.adaptive_sampler_churn_threshold / 2
            )
            if is_stable:
                new_rate = max(
                    GLOBAL_CONFIG.adaptive_sampler_min_rate,
                    new_rate - GLOBAL_CONFIG.adaptive_sampler_decrease_step,
                )
            else:
                # If not stable, increase quickly
                new_rate = self._calculate_balanced_rate(new_rate)

        else:
            # Default: Balanced
            new_rate = self._calculate_balanced_rate(new_rate)

        # --- Apply Change ---

        # Clamp
        new_rate = max(
            GLOBAL_CONFIG.adaptive_sampler_min_rate,
            min(GLOBAL_CONFIG.adaptive_sampler_max_rate, new_rate),
        )

        if new_rate != self._current_sample_rate:
            logger.info(
                f"AdaptiveSampler ({mode}): Adjusting sample rate {self._current_sample_rate:.3f} -> {new_rate:.3f} "
                f"(QPS={self._last_metrics['qps']:.1f}, Err={self._last_metrics['error_rate']:.2f}, Lag={self._last_metrics['lag']:.3f})"
            )
            self._current_sample_rate = new_rate
            GLOBAL_CONFIG.sample_rate = new_rate
            self._last_adjustment_time = current_time

    def _calculate_balanced_rate(self, current_rate: float) -> float:
        """
        Original logic: Increase on any sign of trouble, decrease if all good.
        """
        increase_score = 0
        if self._last_metrics["lag"] > GLOBAL_CONFIG.adaptive_sampler_lag_threshold:
            increase_score += 1
        if (
            self._last_metrics["churn_rate"]
            > GLOBAL_CONFIG.adaptive_sampler_churn_threshold
        ):
            increase_score += 1
        if (
            self._last_metrics["error_rate"]
            > GLOBAL_CONFIG.adaptive_sampler_error_threshold
        ):
            increase_score += 1

        decrease_score = 0
        if self._last_metrics["lag"] < GLOBAL_CONFIG.adaptive_sampler_lag_threshold / 2:
            decrease_score += 1
        if (
            self._last_metrics["churn_rate"]
            < GLOBAL_CONFIG.adaptive_sampler_churn_threshold / 2
        ):
            decrease_score += 1
        if (
            self._last_metrics["error_rate"]
            < GLOBAL_CONFIG.adaptive_sampler_error_threshold / 2
        ):
            decrease_score += 1

        if increase_score > 0:
            return min(
                GLOBAL_CONFIG.adaptive_sampler_max_rate,
                current_rate
                + GLOBAL_CONFIG.adaptive_sampler_increase_step * increase_score,
            )
        elif decrease_score == 3:
            return max(
                GLOBAL_CONFIG.adaptive_sampler_min_rate,
                current_rate - GLOBAL_CONFIG.adaptive_sampler_decrease_step,
            )

        return current_rate


# Global instance of the adaptive sampler
adaptive_sampler = AdaptiveSampler()
