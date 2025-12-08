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
        self._last_metrics = {
            "lag": 0.0,
            "churn_rate": 0.0,
            "error_rate": 0.0,
        }

    def update_metrics(
        self,
        lag: float = 0.0,
        churn_rate: float = 0.0,
        error_rate: float = 0.0,
        **kwargs,  # For future expansion
    ):
        """
        Receives updated system metrics and triggers a sampling rate adjustment if needed.
        """
        self._last_metrics.update(
            {
                "lag": lag,
                "churn_rate": churn_rate,
                "error_rate": error_rate,
                **kwargs,
            }
        )
        self._adjust_sample_rate()

    def _adjust_sample_rate(self):
        """
        Applies a basic adaptive sampling strategy based on current metrics.
        This is a placeholder and will be expanded with more sophisticated logic.
        """
        current_time = time.time()
        if (
            current_time - self._last_adjustment_time
            < GLOBAL_CONFIG.adaptive_sampler_min_interval
        ):
            return

        new_rate = self._current_sample_rate

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
            new_rate = min(
                GLOBAL_CONFIG.adaptive_sampler_max_rate,
                new_rate
                + GLOBAL_CONFIG.adaptive_sampler_increase_step * increase_score,
            )
        elif decrease_score == 3:
            new_rate = max(
                GLOBAL_CONFIG.adaptive_sampler_min_rate,
                new_rate - GLOBAL_CONFIG.adaptive_sampler_decrease_step,
            )
        # Else: no change

        if new_rate != self._current_sample_rate:
            logger.info(
                f"AdaptiveSampler: Adjusting sample rate from {self._current_sample_rate:.2f} to {new_rate:.2f}"
            )
            self._current_sample_rate = new_rate
            GLOBAL_CONFIG.sample_rate = new_rate
            self._last_adjustment_time = current_time


# Global instance of the adaptive sampler
adaptive_sampler = AdaptiveSampler()
