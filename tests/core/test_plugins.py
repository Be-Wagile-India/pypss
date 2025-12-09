import pytest
from typing import Iterable, Dict
from pypss.plugins import BaseMetric, MetricRegistry
from pypss.core.core import compute_pss_from_traces
from pypss.utils.config import GLOBAL_CONFIG
from pypss.plugins.metrics import (
    IOStabilityMetric,
    DBStabilityMetric,
    GCStabilityMetric,
    CacheStabilityMetric,
    ThreadStarvationMetric,
    NetworkStabilityMetric,
    KafkaLagStabilityMetric,
)
import pypss.core.core
import logging

logger = logging.getLogger(__name__)


class SimpleCountMetric(BaseMetric):
    code = "CNT"
    default_weight = 0.5

    def compute(self, traces: Iterable[Dict]) -> float:
        return 1.0 if len(list(traces)) > 5 else 0.5


class AlwaysFailMetric(BaseMetric):
    code = "FAIL"
    default_weight = 0.1

    def compute(self, traces: Iterable[Dict]) -> float:
        raise ValueError("Boom")


@pytest.fixture
def clean_registry():
    MetricRegistry.clear()
    yield
    MetricRegistry.clear()


class TestPluginSystem:
    def test_registration(self, clean_registry):
        MetricRegistry.register(SimpleCountMetric)
        all_metrics = MetricRegistry.get_all()
        assert "CNT" in all_metrics
        assert isinstance(all_metrics["CNT"], SimpleCountMetric)

    def test_core_integration_with_plugin(self, clean_registry, monkeypatch):
        MetricRegistry.register(SimpleCountMetric)
        traces = [{"duration": 0.1}] * 6
        monkeypatch.setattr(
            pypss.core.core.MetricRegistry,
            "get_all",
            lambda: {"CNT": SimpleCountMetric()},
        )
        report = compute_pss_from_traces(traces)
        assert "CNT" in report["breakdown"]
        assert report["breakdown"]["CNT"] == 1.0
        assert report["pss"] >= 99

    def test_plugin_weight_override(self, clean_registry, monkeypatch):
        MetricRegistry.register(SimpleCountMetric)
        traces = [{"duration": 0.1, "memory": 100}]
        monkeypatch.setattr(GLOBAL_CONFIG, "custom_metric_weights", {"CNT": 2.0})
        monkeypatch.setattr(
            pypss.core.core.MetricRegistry,
            "get_all",
            lambda: {"CNT": SimpleCountMetric()},
        )
        report = compute_pss_from_traces(traces)
        assert report["breakdown"]["CNT"] == 0.5

    def test_failing_plugin_does_not_crash_core(self, clean_registry, monkeypatch):
        MetricRegistry.register(AlwaysFailMetric)
        traces = [{"duration": 0.1}]
        monkeypatch.setattr(
            pypss.core.core.MetricRegistry,
            "get_all",
            lambda: {"FAIL": AlwaysFailMetric()},
        )
        report = compute_pss_from_traces(traces)
        assert "FAIL" in report["breakdown"]
        assert report["breakdown"]["FAIL"] == 0.0

    @pytest.mark.parametrize(
        "metric_class, traces, expected_score_condition, description",
        [
            # IOStabilityMetric
            (
                IOStabilityMetric,
                [
                    {"duration": 1.0, "wait_time": 0.2},
                    {"duration": 0.5, "wait_time": 0.1},
                    {"duration": 2.0, "wait_time": 0.4},
                ],
                lambda s: s == pytest.approx(1.0),
                "IO Stable",
            ),
            (
                IOStabilityMetric,
                [
                    {"duration": 1.0, "wait_time": 0.1},
                    {"duration": 1.0, "wait_time": 0.9},
                    {"duration": 1.0, "wait_time": 0.1},
                ],
                lambda s: s < 0.8,
                "IO Unstable",
            ),
            # DBStabilityMetric
            (
                DBStabilityMetric,
                [
                    {"name": "q1", "module": "app.db", "duration": 0.1},
                    {"name": "q2", "module": "app.db", "duration": 0.1},
                ],
                lambda s: s == pytest.approx(1.0),
                "DB Stable",
            ),
            (
                DBStabilityMetric,
                [
                    {"name": "q1", "module": "app.db", "duration": 0.05},
                    {"name": "q2", "module": "app.db", "duration": 0.5},
                    {"name": "q3", "module": "app.db", "duration": 0.05},
                ],
                lambda s: s < 0.8,
                "DB Unstable",
            ),
            # GCStabilityMetric
            (
                GCStabilityMetric,
                [
                    {"system_metric": True, "metadata": {"gc_pause_duration": 0.001}},
                    {"system_metric": True, "metadata": {"gc_pause_duration": 0.001}},
                ],
                lambda s: s == pytest.approx(1.0),
                "GC Stable",
            ),
            (
                GCStabilityMetric,
                [
                    {"system_metric": True, "metadata": {"gc_pause_duration": 0.0001}},
                    {"system_metric": True, "metadata": {"gc_pause_duration": 0.01}},
                    {"system_metric": True, "metadata": {"gc_pause_duration": 0.0001}},
                ],
                lambda s: s < 0.8,
                "GC Unstable",
            ),
            # CacheStabilityMetric
            (
                CacheStabilityMetric,
                [{"name": "g", "branch_tag": "cache_hit"}] * 3,
                lambda s: s == pytest.approx(1.0),
                "Cache Stable",
            ),
            (
                CacheStabilityMetric,
                [
                    {"name": "g", "branch_tag": "cache_hit"},
                    {"name": "g", "branch_tag": "cache_miss"},
                ],
                lambda s: s == pytest.approx(0.5),
                "Cache Mixed",
            ),
            # ThreadStarvationMetric
            (
                ThreadStarvationMetric,
                [{"system_metric": True, "metadata": {"lag": 0.001}}] * 3,
                lambda s: s > 0.9,
                "Thread Stable",
            ),
            (
                ThreadStarvationMetric,
                [
                    {"system_metric": True, "metadata": {"lag": 0.001}},
                    {"system_metric": True, "metadata": {"lag": 0.05}},
                    {"system_metric": True, "metadata": {"lag": 0.001}},
                ],
                lambda s: s < 0.2,
                "Thread Unstable",
            ),
            # NetworkStabilityMetric
            (
                NetworkStabilityMetric,
                [{"name": "http_request", "duration": 0.1}] * 3,
                lambda s: s == pytest.approx(1.0),
                "Network Stable",
            ),
            (
                NetworkStabilityMetric,
                [
                    {"name": "http_request", "duration": 0.05},
                    {"name": "http_request", "duration": 0.5},
                    {"name": "http_request", "duration": 0.05},
                ],
                lambda s: s < 0.8,
                "Network Unstable",
            ),
            # KafkaLagStabilityMetric
            (
                KafkaLagStabilityMetric,
                [{"system_metric": True, "metadata": {"kafka_lag": 10}}] * 3,
                lambda s: s > 0.85,
                "Kafka Stable",
            ),
            (
                KafkaLagStabilityMetric,
                [
                    {"system_metric": True, "metadata": {"kafka_lag": 10}},
                    {"system_metric": True, "metadata": {"kafka_lag": 1000}},
                    {"system_metric": True, "metadata": {"kafka_lag": 20}},
                ],
                lambda s: s < 0.2,
                "Kafka Unstable",
            ),
        ],
    )
    def test_metrics_compute(
        self, metric_class, traces, expected_score_condition, description
    ):
        metric = metric_class()
        score = metric.compute(traces)
        assert expected_score_condition(score), f"Failed: {description}"

    @pytest.mark.parametrize(
        "metric_class, traces, metric_key",
        [
            (IOStabilityMetric, [{"duration": 1.0, "wait_time": 0.2}], "IO"),
            (
                DBStabilityMetric,
                [{"name": "q", "module": "app.db", "duration": 0.1}],
                "DB",
            ),
            (
                GCStabilityMetric,
                [{"system_metric": True, "metadata": {"gc_pause_duration": 0.001}}],
                "GC",
            ),
            (
                CacheStabilityMetric,
                [{"name": "g", "branch_tag": "cache_hit"}],
                "CACHE",
            ),
            (
                ThreadStarvationMetric,
                [{"system_metric": True, "metadata": {"lag": 0.001}}],
                "STARVE",
            ),
            (
                NetworkStabilityMetric,
                [{"name": "http_request", "duration": 0.1}],
                "NET",
            ),
            (
                KafkaLagStabilityMetric,
                [{"system_metric": True, "metadata": {"kafka_lag": 10}}],
                "KAFKA",
            ),
        ],
    )
    def test_metric_integration(
        self, metric_class, traces, metric_key, clean_registry, monkeypatch
    ):
        MetricRegistry.register(metric_class)
        # Mock MetricRegistry.get_all to ensure we get the registered metric
        monkeypatch.setattr(
            pypss.core.core.MetricRegistry,
            "get_all",
            lambda: {metric_key: metric_class()},
        )
        report = compute_pss_from_traces(traces)
        assert metric_key in report["breakdown"]
        assert report["breakdown"][metric_key] is not None
