import threading
import logging
from collections import deque
from typing import Deque, Optional, Dict  # Corrected import

# from pypss.instrumentation.collectors import global_collector # REMOVE THIS
import pypss  # ADD THIS

from pypss.core.adaptive_sampler import adaptive_sampler

from pypss.instrumentation.collectors import (
    BaseCollector,
)  # Add BaseCollector import

logger = logging.getLogger(__name__)


class ErrorRateMonitor:
    """
    Monitors the error rate from collected traces and updates the AdaptiveSampler.
    """

    def __init__(
        self, collector: BaseCollector, interval: float = 5.0, window_size: int = 100
    ):  # Add collector parameter
        self.collector = collector  # Store the collector instance
        self.interval = interval
        self.window_size = (
            window_size  # Number of recent traces to consider for error rate
        )
        self._error_history: Deque[bool] = deque(maxlen=window_size)
        self._traces_since_last_interval: int = 0
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        # Register as an observer with the provided collector
        self.collector.register_observer(self._on_new_trace)

    def _on_new_trace(self, trace: Dict):
        """Callback method invoked by the global_collector when a new trace is added."""
        self._error_history.append(trace.get("error", False))
        self._traces_since_last_interval += 1

    def start(self):
        if self._thread and self._thread.is_alive():
            logger.info("PyPSS: Error Rate Monitor already running.")
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info(
            f"PyPSS: Error Rate Monitor started (interval={self.interval}s, window_size={self.window_size})"
        )

    def stop(self):
        # Unregister observer from the provided collector
        self.collector.unregister_observer(self._on_new_trace)
        if self._thread and self._thread.is_alive():
            self._stop_event.set()
            self._thread.join(timeout=self.interval + 1)
            self._thread = None
            logger.info("PyPSS: Error Rate Monitor stopped.")

    def _run(self):
        while not self._stop_event.is_set():
            try:
                self._calculate_and_update_error_rate()
            except Exception as e:
                logger.error(f"Error Rate Monitor failed: {e}")
            self._stop_event.wait(self.interval)

    def _calculate_and_update_error_rate(self):
        # Calculate error rate directly from the _error_history deque
        # The deque is automatically managed by _on_new_trace and has a fixed maxlen

        total_traces = len(self._error_history)
        if total_traces == 0:
            error_rate = 0.0
        else:
            error_count = sum(1 for is_error in self._error_history if is_error)
            error_rate = error_count / total_traces

        adaptive_sampler.update_metrics(
            error_rate=error_rate, trace_count=self._traces_since_last_interval
        )
        self._traces_since_last_interval = 0

        logger.debug(f"Calculated error rate: {error_rate:.2f}")


# Placeholder for the global instance. It must be initialized via pypss.init().
error_rate_monitor: Optional[ErrorRateMonitor] = None


def _initialize_error_rate_monitor():
    """Initializes the global error rate monitor based on the global_collector."""
    global error_rate_monitor
    # Ensure global_collector is initialized
    _collector = (
        pypss.get_global_collector()
    )  # This will raise RuntimeError if not initialized

    error_rate_monitor = ErrorRateMonitor(collector=_collector)
    error_rate_monitor.start()
