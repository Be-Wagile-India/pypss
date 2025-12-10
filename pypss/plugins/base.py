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
        Returns:
            float: Stability score between 0.0 (unstable) and 1.0 (stable).
        """
        pass
