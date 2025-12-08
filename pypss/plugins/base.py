from abc import ABC, abstractmethod
from typing import Dict, Iterable


class BaseMetric(ABC):
    """
    Abstract Base Class for custom PyPSS metrics.
    """

    name: str = "Base Metric"
    code: str = "BM"
    default_weight: float = 0.1

    @abstractmethod
    def compute(self, traces: Iterable[Dict]) -> float:
        """
        Compute the stability score (0.0 to 1.0) based on the provided traces.

        Args:
            traces: An iterable of trace dictionaries.
                    Note: Since this might be an iterator (from ijson),
                    metrics should ideally support single-pass or we might need to materialize.
                    Currently PyPSS core materializes specific arrays.
                    For plugins, if we pass the iterator, it might be consumed.

                    RECOMMENDATION: PyPSS core will pass a LIST of traces or specific extracted data.
                    However, strictly speaking, `compute_pss_from_traces` consumes the iterator once.
                    We will need to redesign `compute_pss_from_traces` to either materialize traces first
                    (memory heavy) or allow plugins to hook into the iteration loop (complex).

                    For V1 of plugins, let's assume `traces` is a materialized list or we pass extracted arrays.
                    Wait, `compute_pss_from_traces` extracts to `array.array`.
                    Passing these arrays to plugins would be efficient but limits what plugins can access (only extracted fields).

                    Let's assume for now that plugins receive the FULL list of traces.
                    WARNING: This means we implicitly enforce materialization if plugins are used.

        Returns:
            float: Stability score between 0.0 (unstable) and 1.0 (stable).
        """
        pass
