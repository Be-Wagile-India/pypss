import random
import copy
from typing import List, Dict, Any


class FaultInjector:
    """
    Generates synthetic unstable traces by injecting faults into baseline data.
    """

    def __init__(self, traces: List[Dict[str, Any]]):
        """
        Initialize the FaultInjector.

        Args:
            traces: List of baseline trace dictionaries.
                    NOTE: This list should be sorted by timestamp for sequential injections.
        """
        self.original_traces = traces

    def _clone_traces(self) -> List[Dict[str, Any]]:
        return copy.deepcopy(self.original_traces)

    def inject_latency_jitter(
        self, magnitude: float = 2.0, probability: float = 0.3
    ) -> List[Dict[str, Any]]:
        """
        Simulates network/CPU jitter by multiplying random trace durations.

        Args:
            magnitude: Multiplier for the duration (e.g., 2.0 means double the latency).
            probability: Probability of a trace being affected (0.0 to 1.0).
        """
        faulty_traces = self._clone_traces()
        for trace in faulty_traces:
            if random.random() < probability:
                # Apply random jitter up to magnitude
                # Jitter factor between 1.0 and magnitude
                factor = 1.0 + (random.random() * (magnitude - 1.0))
                trace["duration"] = float(trace.get("duration", 0.0)) * factor
        return faulty_traces

    def inject_memory_leak(
        self, growth_rate: int = 1024 * 1024
    ) -> List[Dict[str, Any]]:
        """
        Simulates a memory leak by progressively increasing memory usage.

        Args:
            growth_rate: Bytes added per trace step (default 1MB).
        """
        faulty_traces = self._clone_traces()
        accumulated_leak = 0
        for trace in faulty_traces:
            accumulated_leak += growth_rate

            # Update absolute memory
            current_mem = float(trace.get("memory", 0))
            trace["memory"] = current_mem + accumulated_leak

            # Update memory_diff (leak implies positive diff)
            # We assume the original diff was normal, we add the leak rate to it
            current_diff = float(trace.get("memory_diff", 0))
            trace["memory_diff"] = current_diff + growth_rate

        return faulty_traces

    def inject_error_burst(
        self, burst_size: int = 5, burst_count: int = 1
    ) -> List[Dict[str, Any]]:
        """
        Injects concentrated bursts of errors.

        Args:
            burst_size: Number of consecutive errors in a burst.
            burst_count: Number of separate bursts to inject.
        """
        faulty_traces = self._clone_traces()
        n = len(faulty_traces)
        if n == 0:
            return faulty_traces

        for _ in range(burst_count):
            if n <= burst_size:
                start_idx = 0
            else:
                start_idx = random.randint(0, n - burst_size)

            for i in range(start_idx, min(start_idx + burst_size, n)):
                faulty_traces[i]["error"] = True
                faulty_traces[i]["exception_type"] = "SyntheticFaultError"
                faulty_traces[i]["exception_message"] = "Injected by FaultInjector"

        return faulty_traces

    def inject_thread_starvation(
        self, lag_seconds: float = 0.05, probability: float = 0.2
    ) -> List[Dict[str, Any]]:
        """
        Simulates thread starvation/GIL contention by injecting high wait times.

        Args:
            lag_seconds: Minimum wait time to inject.
            probability: Probability of a trace being affected.
        """
        faulty_traces = self._clone_traces()
        for trace in faulty_traces:
            if random.random() < probability:
                # Add lag to existing wait_time
                current_wait = float(trace.get("wait_time", 0.0))
                # Random jitter on the lag itself (0.8x to 1.2x)
                jitter = lag_seconds * (0.8 + 0.4 * random.random())
                trace["wait_time"] = current_wait + jitter
        return faulty_traces
