import threading
import json
import os
import math
from collections import deque
from dataclasses import dataclass, asdict
from typing import Optional, Deque, Dict

from ..utils.config import PSSConfig, GLOBAL_CONFIG
from ..instrumentation.collectors import BaseCollector


@dataclass
class RuntimeBaselineState:
    """
    Stores runtime-adjusted baseline parameters for dynamic tuning.
    """

    concurrency_wait_threshold: float = GLOBAL_CONFIG.concurrency_wait_threshold
    # Add other dynamically adjusted parameters here if needed in the future

    _file_path: str = ".pypss_runtime_baseline.json"

    def save(self):
        """Saves the current state to a JSON file."""
        data = asdict(self)
        # Remove internal field before saving
        data.pop("_file_path", None)
        try:
            with open(self._file_path, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            # Log error, but don't fail the application
            print(f"Error saving runtime baseline state to {self._file_path}: {e}")

    @classmethod
    def load(cls) -> "RuntimeBaselineState":
        """Loads the state from a JSON file, or returns a default if not found."""
        instance = cls()  # Default values
        if os.path.exists(instance._file_path):
            try:
                with open(instance._file_path, "r") as f:
                    data = json.load(f)
                    for key, value in data.items():
                        if hasattr(instance, key):
                            setattr(instance, key, value)
            except Exception as e:
                print(
                    f"Error loading runtime baseline state from {instance._file_path}: {e}"
                )
        return instance


class RuntimeTuner:
    """
    Dynamically adjusts PyPSS configuration parameters at runtime based on observed metrics.
    Currently focuses on `concurrency_wait_threshold`.
    """

    def __init__(self, config: PSSConfig, collector: BaseCollector):
        self.config = config
        self.collector = collector
        self.state = RuntimeBaselineState.load()

        self._wait_times_history: Deque[float] = deque(
            maxlen=1000
        )  # Keep history of recent wait times
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._tuning_interval: float = (
            60.0  # How often to re-evaluate (e.g., every minute)
        )
        self._min_samples_for_tuning: int = 100  # Minimum samples before tuning

        # Register as an observer to get new traces
        self.collector.register_observer(self._on_new_trace)

    def _on_new_trace(self, trace: Dict):
        """Callback method invoked by the global_collector when a new trace is added."""
        if "wait_time" in trace:
            self._wait_times_history.append(float(trace["wait_time"]))

    def start(self):
        """Starts the background tuning thread."""
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="PyPSS-RuntimeTuner"
        )
        self._thread.start()
        print("PyPSS: Runtime Tuner started.")

    def stop(self):
        """Stops the background tuning thread."""
        self.collector.unregister_observer(self._on_new_trace)
        if self._thread and self._thread.is_alive():
            self._stop_event.set()
            self._thread.join(timeout=self._tuning_interval + 1)
            self._thread = None

    def _run(self):
        while not self._stop_event.is_set():
            try:
                self._tune_parameters()
            except Exception as e:
                print(f"PyPSS: Runtime Tuner failed during tuning: {e}")
            self._stop_event.wait(self._tuning_interval)

    def _tune_parameters(self):
        """
        Analyzes collected metrics and adjusts relevant config parameters.
        """
        if len(self._wait_times_history) < self._min_samples_for_tuning:
            return

        # Simple approach: set threshold to P95 of recent wait times
        sorted_wait_times = sorted(list(self._wait_times_history))
        n = len(sorted_wait_times)

        # Calculate P95
        k_p95 = (n - 1) * 0.95
        f_p95 = int(math.floor(k_p95))
        c_p95 = int(math.ceil(k_p95))

        if f_p95 == c_p95:
            p95_wait_time = sorted_wait_times[f_p95]
        else:
            d0 = sorted_wait_times[f_p95]
            d1 = sorted_wait_times[c_p95]
            p95_wait_time = d0 + (d1 - d0) * (k_p95 - f_p95)

        # Apply a small buffer to the P95 to make it a threshold
        new_concurrency_wait_threshold = p95_wait_time * 1.2  # 20% buffer

        if (
            abs(self.config.concurrency_wait_threshold - new_concurrency_wait_threshold)
            > 0.0001
        ):  # Check for significant change
            print(
                f"PyPSS: Adjusting concurrency_wait_threshold from {self.config.concurrency_wait_threshold:.4f} to {new_concurrency_wait_threshold:.4f}"
            )
            self.config.concurrency_wait_threshold = new_concurrency_wait_threshold
            self.state.concurrency_wait_threshold = new_concurrency_wait_threshold
            self.state.save()
            # It's important to update GLOBAL_CONFIG directly here
            # as other components will read from it.
            GLOBAL_CONFIG.concurrency_wait_threshold = new_concurrency_wait_threshold
            # Note: Components like ErrorRateMonitor still read GLOBAL_CONFIG on their init.
            # If they need to react to this specific change, they would need to re-read or be notified.
            # For this Phase 3, we modify GLOBAL_CONFIG in place for components that read it dynamically.
            # `_calculate_concurrency_chaos_score` in core.py reads `conf.concurrency_wait_threshold`
            # and `conf` is `GLOBAL_CONFIG` so it will pick up the change.
