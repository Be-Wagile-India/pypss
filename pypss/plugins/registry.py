import logging
from typing import Dict, Type

from .base import BaseMetric

logger = logging.getLogger(__name__)


class MetricRegistry:
    _registry: Dict[str, BaseMetric] = {}

    @classmethod
    def register(cls, metric_cls: Type[BaseMetric]):
        """
        Register a new metric class.
        """
        instance = metric_cls()
        cls._registry[instance.code] = instance
        logger.debug(f"MetricRegistry: Registered {instance.name} ({instance.code})")

    @classmethod
    def get_all(cls) -> Dict[str, BaseMetric]:
        logger.debug(f"MetricRegistry: get_all called. Current registry: {list(cls._registry.keys())}")
        return cls._registry

    @classmethod
    def clear(cls):
        logger.debug("MetricRegistry: Cleared registry.")
        cls._registry = {}
