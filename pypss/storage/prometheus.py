from typing import Dict, List, Any, Optional
from .base import StorageBackend

try:
    from prometheus_client import (
        Gauge,
        CollectorRegistry,
        push_to_gateway,
        start_http_server,
    )

    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False


class PrometheusStorage(StorageBackend):
    def __init__(
        self,
        push_gateway: Optional[str] = None,
        http_port: Optional[int] = None,
        job_name: str = "pypss",
    ):
        if not PROMETHEUS_AVAILABLE:
            raise ImportError(
                "prometheus-client is not installed. Run 'pip install pypss[monitoring]'"
            )

        self.push_gateway = push_gateway
        self.http_port = http_port
        self.job_name = job_name
        self.registry = CollectorRegistry()

        # Define Metrics
        self.g_pss = Gauge(
            "pypss_score", "Python Program Stability Score", registry=self.registry
        )
        self.g_ts = Gauge("pypss_ts", "Timing Stability Score", registry=self.registry)
        self.g_ms = Gauge("pypss_ms", "Memory Stability Score", registry=self.registry)
        self.g_ev = Gauge("pypss_ev", "Error Volatility Score", registry=self.registry)
        self.g_be = Gauge("pypss_be", "Branching Entropy Score", registry=self.registry)
        self.g_cc = Gauge("pypss_cc", "Concurrency Chaos Score", registry=self.registry)

        if self.http_port:
            try:
                start_http_server(self.http_port, registry=self.registry)
            except Exception as e:
                print(
                    f"⚠️ Failed to start Prometheus server on port {self.http_port}: {e}"
                )

    def save(
        self, report: Dict[str, Any], meta: Optional[Dict[str, Any]] = None
    ) -> None:
        breakdown = report.get("breakdown", {})

        self.g_pss.set(report.get("pss", 0.0))
        self.g_ts.set(breakdown.get("timing_stability", 0.0))
        self.g_ms.set(breakdown.get("memory_stability", 0.0))
        self.g_ev.set(breakdown.get("error_volatility", 0.0))
        self.g_be.set(breakdown.get("branching_entropy", 0.0))
        self.g_cc.set(breakdown.get("concurrency_chaos", 0.0))

        if self.push_gateway:
            try:
                push_to_gateway(
                    self.push_gateway, job=self.job_name, registry=self.registry
                )
            except Exception as e:
                print(f"⚠️ Failed to push metrics to {self.push_gateway}: {e}")

    def get_history(
        self, limit: int = 10, days: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        # Prometheus is write-only from the client perspective
        return []
