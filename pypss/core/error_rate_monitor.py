import logging
import threading
from collections import deque
from typing import Deque, Dict, Optional

import pypss
from pypss.core.adaptive_sampler import adaptive_sampler
from pypss.instrumentation.collectors import BaseCollector

logger = logging.getLogger(__name__)


class ErrorRateMonitor:
    """
    Monitors the error rate from collected traces and updates the AdaptiveSampler.
    """

    def __init__(self, collector: BaseCollector, interval: float = 5.0, window_size: int = 100):
        self.collector = collector
        self.interval = interval
        self.window_size = window_size
        self._error_history: Deque[bool] = deque(maxlen=window_size)
        self._traces_since_last_interval: int = 0
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
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
        logger.info(f"PyPSS: Error Rate Monitor started (interval={self.interval}s, window_size={self.window_size})")

    def stop(self):
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
        total_traces = len(self._error_history)
        if total_traces == 0:
            error_rate = 0.0
        else:
            error_count = sum(1 for is_error in self._error_history if is_error)
            error_rate = error_count / total_traces

        adaptive_sampler.update_metrics(error_rate=error_rate, trace_count=self._traces_since_last_interval)
        self._traces_since_last_interval = 0

        logger.debug(f"Calculated error rate: {error_rate:.2f}")


error_rate_monitor: Optional[ErrorRateMonitor] = None


def _initialize_error_rate_monitor():
    """Initializes the global error rate monitor based on the global_collector."""
    global error_rate_monitor
    _collector = pypss.get_global_collector()

    error_rate_monitor = ErrorRateMonitor(collector=_collector)
    error_rate_monitor.start()
