import logging
from typing import Iterable
import pypss
from ..utils.config import GLOBAL_CONFIG

try:
    from opentelemetry import metrics
    from opentelemetry.metrics import Observation, CallbackOptions

    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False
    metrics = None  # type: ignore

    # Dummy types for type hinting/usage when OTel is missing
    class Observation:  # type: ignore
        def __init__(self, value):
            self.value = value

    class CallbackOptions:  # type: ignore
        pass


from ..core import compute_pss_from_traces

logger = logging.getLogger(__name__)


class OTelReporter:
    """
    Integrates PyPSS with OpenTelemetry Metrics.
    Registers Observable Gauges that calculate stability scores on-demand when scraped.
    """

    def __init__(self, meter_provider=None):
        if not OTEL_AVAILABLE:
            logger.warning("OpenTelemetry is not installed. Install pypss[otel].")
            return

        self.meter = metrics.get_meter(
            GLOBAL_CONFIG.integration_otel_meter_name,
            GLOBAL_CONFIG.integration_otel_meter_version,
            meter_provider=meter_provider,
        )
        self._register_metrics()

    def _register_metrics(self):
        prefix = GLOBAL_CONFIG.integration_otel_metric_prefix
        self.meter.create_observable_gauge(
            name=f"{prefix}score",
            callbacks=[self._observe_pss],
            description="The overall Python Program Stability Score (0-100)",
            unit="1",
        )
        self.meter.create_observable_gauge(
            name=f"{prefix}stability.timing",
            callbacks=[self._observe_breakdown("timing_stability")],
            description="Timing Stability Score (0-1)",
            unit="1",
        )
        self.meter.create_observable_gauge(
            name=f"{prefix}stability.memory",
            callbacks=[self._observe_breakdown("memory_stability")],
            description="Memory Stability Score (0-1)",
            unit="1",
        )
        self.meter.create_observable_gauge(
            name=f"{prefix}stability.errors",
            callbacks=[self._observe_breakdown("error_volatility")],
            description="Error Volatility Score (0-1)",
            unit="1",
        )
        self.meter.create_observable_gauge(
            name=f"{prefix}stability.entropy",
            callbacks=[self._observe_breakdown("branching_entropy")],
            description="Branching Entropy Score (0-1)",
            unit="1",
        )
        self.meter.create_observable_gauge(
            name=f"{prefix}stability.concurrency",
            callbacks=[self._observe_breakdown("concurrency_chaos")],
            description="Concurrency Chaos Score (0-1)",
            unit="1",
        )

    def _compute_snapshot(self):
        # Get all traces currently in the ring buffer
        collector = pypss.get_global_collector()
        if collector:
            traces = collector.get_traces()
            return compute_pss_from_traces(traces)
        return {
            "pss": 0,
            "breakdown": {},
        }  # Return a default empty report if collector is None

    def _observe_pss(self, options: CallbackOptions) -> Iterable[Observation]:
        report = self._compute_snapshot()
        yield Observation(value=report.get("pss", 0))

    def _observe_breakdown(self, key: str):
        def callback(options: CallbackOptions) -> Iterable[Observation]:
            report = self._compute_snapshot()
            val = report.get("breakdown", {}).get(key, 0.0)
            yield Observation(value=val)

        return callback


def enable_otel_integration(meter_provider=None):
    """
    Enables OpenTelemetry export for PyPSS metrics.
    """
    return OTelReporter(meter_provider)
