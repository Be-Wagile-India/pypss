"""
Metric Auto-Tuning Engine for PyPSS.

This package provides tools to statistically profile application traces,
generate synthetic faults, and optimize PyPSS configuration parameters
for maximum anomaly detection sensitivity.
"""

from .profiler import Profiler, BaselineProfile
from .injector import FaultInjector
from .optimizer import ConfigOptimizer

__all__ = ["Profiler", "BaselineProfile", "FaultInjector", "ConfigOptimizer"]
