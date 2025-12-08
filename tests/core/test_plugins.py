import pytest
from typing import Iterable, Dict
from pypss.plugins import BaseMetric, MetricRegistry
from pypss.core.core import compute_pss_from_traces
from pypss.utils.config import GLOBAL_CONFIG
from pypss.plugins.metrics import (
    IOStabilityMetric,
    DBStabilityMetric,
    CacheStabilityMetric,
    ThreadStarvationMetric,
    NetworkStabilityMetric,
)
import pypss.core.core  # Import the module to access its MetricRegistry

import logging

# Configure logging to capture DEBUG messages during tests
# logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class SimpleCountMetric(BaseMetric):
    code = "CNT"
    default_weight = 0.5

    def compute(self, traces: Iterable[Dict]) -> float:
        # A simple metric: score is 1.0 if count > 5, else 0.5
        count = len(list(traces))
        return 1.0 if count > 5 else 0.5


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

        # 6 traces -> CNT score should be 1.0
        traces = [{"duration": 0.1}] * 6

        # Mock MetricRegistry.get_all for compute_pss_from_traces
        monkeypatch.setattr(
            pypss.core.core.MetricRegistry,
            "get_all",
            lambda: {"CNT": SimpleCountMetric()},
        )

        report = compute_pss_from_traces(traces)

        assert "CNT" in report["breakdown"]
        assert report["breakdown"]["CNT"] == 1.0

        # Check PSS calculation influence
        # Standard metrics are all perfect (1.0) with these traces?
        # Duration 0.1 constant -> CV=0 -> TS=1.0
        # No Memory -> MS=1.0 (median=0) actually MS might be 0 if median is 0?
        # Let's provide valid data for other metrics to be stable 1.0
        traces_perfect = [
            {"duration": 0.1, "memory": 100, "wait_time": 0.0, "error": False}
            for _ in range(6)
        ]

        # Mock MetricRegistry.get_all again for the second call if needed, or pass registry state
        monkeypatch.setattr(
            pypss.core.core.MetricRegistry,
            "get_all",
            lambda: {"CNT": SimpleCountMetric()},
        )

        report = compute_pss_from_traces(traces_perfect)
        # Standard metrics should be ~1.0. CNT is 1.0. Total PSS should be 100.
        assert report["pss"] >= 99

    def test_plugin_weight_override(self, clean_registry, monkeypatch):
        MetricRegistry.register(SimpleCountMetric)

        # 1 trace -> CNT score is 0.5
        traces = [{"duration": 0.1, "memory": 100}]

        # Override weight in config
        monkeypatch.setattr(GLOBAL_CONFIG, "custom_metric_weights", {"CNT": 2.0})

        # Mock MetricRegistry.get_all
        monkeypatch.setattr(
            pypss.core.core.MetricRegistry,
            "get_all",
            lambda: {"CNT": SimpleCountMetric()},
        )

        report = compute_pss_from_traces(traces)
        assert report["breakdown"]["CNT"] == 0.5
        # Score calculation is complex to assert exact number without calc,
        # but we verified the flow in core.py

    def test_failing_plugin_does_not_crash_core(self, clean_registry, monkeypatch):
        MetricRegistry.register(AlwaysFailMetric)
        traces = [{"duration": 0.1}]

        # Mock MetricRegistry.get_all
        monkeypatch.setattr(
            pypss.core.core.MetricRegistry,
            "get_all",
            lambda: {"FAIL": AlwaysFailMetric()},
        )

        report = compute_pss_from_traces(traces)

        # Should succeed
        assert "FAIL" in report["breakdown"]
        assert report["breakdown"]["FAIL"] == 0.0  # Default on error

    def test_io_stability_metric(self):
        metric = IOStabilityMetric()

        # Case 1: Perfect stability (constant I/O ratio)
        # Wait time is always 20% of duration
        traces_stable = [
            {"duration": 1.0, "wait_time": 0.2},
            {"duration": 0.5, "wait_time": 0.1},
            {"duration": 2.0, "wait_time": 0.4},
        ]
        score = metric.compute(traces_stable)
        assert score == pytest.approx(1.0)

        # Case 2: Unstable I/O
        # Ratios: 0.1, 0.9, 0.1 (Huge variance)
        traces_unstable = [
            {"duration": 1.0, "wait_time": 0.1},
            {"duration": 1.0, "wait_time": 0.9},
            {"duration": 1.0, "wait_time": 0.1},
        ]
        score = metric.compute(traces_unstable)
        assert score < 0.8  # Should be penalized significantly

    def test_db_stability_metric(self, clean_registry, monkeypatch):
        metric = DBStabilityMetric()

        # Case 1: Perfect stability (constant DB durations)
        traces_stable_db = [
            {"name": "query_users", "module": "app.db", "duration": 0.1},
            {"name": "insert_log", "module": "app.db", "duration": 0.1},
            {"name": "get_products", "module": "app.db", "duration": 0.1},
        ]
        score_stable = metric.compute(traces_stable_db)
        assert score_stable == pytest.approx(1.0)

        # Case 2: Unstable DB durations
        traces_unstable_db = [
            {"name": "query_users", "module": "app.db", "duration": 0.05},
            {"name": "insert_log", "module": "app.db", "duration": 0.5},
            {"name": "get_products", "module": "app.db", "duration": 0.05},
        ]
        score_unstable = metric.compute(traces_unstable_db)
        assert score_unstable < 0.8  # Should be penalized

        # Case 3: No DB traces
        traces_no_db = [
            {"name": "compute_cpu", "module": "app.logic", "duration": 0.1},
            {"name": "parse_data", "module": "app.parser", "duration": 0.2},
        ]
        score_no_db = metric.compute(traces_no_db)
        assert score_no_db == pytest.approx(1.0)

        # Test registration and integration
        MetricRegistry.register(DBStabilityMetric)
        monkeypatch.setattr(
            pypss.core.core.MetricRegistry,
            "get_all",
            lambda: {"DB": DBStabilityMetric()},
        )
        report = compute_pss_from_traces(traces_stable_db)
        assert "DB" in report["breakdown"]
        assert report["breakdown"]["DB"] == pytest.approx(1.0)

    # def test_gc_stability_metric(self, clean_registry, monkeypatch):
    #     logger.debug("TestPluginSystem.test_gc_stability_metric START")
    #     metric = GCStabilityMetric()

    #     # Case 1: Stable GC pauses (via system_metric traces)
    #     traces_stable_gc = [
    #         {"system_metric": True, "metadata": {"gc_pause_duration": 0.001}},
    #         {"system_metric": True, "metadata": {"gc_pause_duration": 0.001}},
    #         {"system_metric": True, "metadata": {"gc_pause_duration": 0.001}},
    #     ]
    #     score_stable = metric.compute(traces_stable_gc)
    #     assert score_stable == pytest.approx(1.0)

    #     # Case 2: Unstable GC pauses
    #     traces_unstable_gc = [
    #         {"system_metric": True, "metadata": {"gc_pause_duration": 0.0001}},
    #         {"system_metric": True, "metadata": {"gc_pause_duration": 0.01}}, # Spike
    #         {"system_metric": True, "metadata": {"gc_pause_duration": 0.0001}},
    #     ]
    #     score_unstable = metric.compute(traces_unstable_gc)
    #     assert score_unstable < 0.8 # Should be penalized

    #     # Case 3: No GC traces, fallback to memory_diff
    #     traces_mem_diff = [
    #         {"duration": 1.0, "memory_diff": -2000},
    #         {"duration": 1.0, "memory_diff": -2050},
    #         {"duration": 1.0, "memory_diff": -1950},
    #     ]
    #     score_mem_diff_stable = metric.compute(traces_mem_diff)
    #     assert score_mem_diff_stable > 0.9 # Should be high, but not 1.0 due to some variance

    #     traces_mem_diff_unstable = [
    #         {"duration": 1.0, "memory_diff": -100},
    #         {"duration": 1.0, "memory_diff": -5000}, # Spike
    #         {"duration": 1.0, "memory_diff": -100},
    #     ]
    #     score_mem_diff_unstable = metric.compute(traces_mem_diff_unstable)
    #     assert score_mem_diff_unstable < 0.8

    #     # Case 4: No relevant traces
    #     traces_no_gc = [
    #         {"name": "cpu_bound", "duration": 0.1},
    #         {"name": "io_bound", "duration": 0.2, "wait_time": 0.1},
    #     ]
    #     score_no_gc = metric.compute(traces_no_gc)
    #     assert score_no_gc == pytest.approx(1.0)

    #     # Test registration and integration
    #     # MetricRegistry.register(GCStabilityMetric)
    #     # logger.debug(f"Test: Registry keys after register: {list(MetricRegistry.get_all().keys())}")
    #     # monkeypatch.setattr(pypss.core.core.MetricRegistry, "get_all", lambda: {"GC": GCStabilityMetric()})
    #     # report = compute_pss_from_traces(traces_stable_gc)
    #     # logger.debug(f"Test: Report breakdown after compute: {report['breakdown'].keys()}")
    #     # assert "GC" in report["breakdown"]
    #     # assert report["breakdown"]["GC"] == pytest.approx(1.0)

    def test_cache_stability_metric(self, clean_registry, monkeypatch):
        metric = CacheStabilityMetric()

        # Case 1: High and stable hit ratio (all hits)
        traces_all_hits = [
            {"name": "get_data", "branch_tag": "cache_hit"},
            {"name": "get_data", "branch_tag": "cache_hit"},
            {"name": "get_data", "branch_tag": "cache_hit"},
        ]
        score_all_hits = metric.compute(traces_all_hits)
        assert score_all_hits == pytest.approx(1.0)  # 100% hit ratio

        # Case 2: Low hit ratio (mostly misses)
        traces_mostly_misses = [
            {"name": "get_data", "branch_tag": "cache_hit"},
            {"name": "get_data", "branch_tag": "cache_miss"},
            {"name": "get_data", "branch_tag": "cache_miss"},
            {"name": "get_data", "branch_tag": "cache_miss"},
        ]
        score_mostly_misses = metric.compute(traces_mostly_misses)
        assert score_mostly_misses == pytest.approx(0.25)  # 25% hit ratio

        # Case 3: Mixed hits and misses, e.g., 50% hit ratio
        traces_mixed = [
            {"name": "get_data", "branch_tag": "cache_hit"},
            {"name": "get_data", "branch_tag": "cache_miss"},
        ]
        score_mixed = metric.compute(traces_mixed)
        assert score_mixed == pytest.approx(0.5)

        # Case 4: No cache operations
        traces_no_cache = [
            {"name": "compute_cpu", "duration": 0.1},
            {"name": "io_bound", "duration": 0.2, "wait_time": 0.1},
        ]
        score_no_cache = metric.compute(traces_no_cache)
        assert score_no_cache == pytest.approx(1.0)  # Assumed stable if no data

        # Test registration and integration
        MetricRegistry.register(CacheStabilityMetric)
        monkeypatch.setattr(
            pypss.core.core.MetricRegistry,
            "get_all",
            lambda: {"CACHE": CacheStabilityMetric()},
        )
        report = compute_pss_from_traces(traces_all_hits)
        assert "CACHE" in report["breakdown"]
        assert report["breakdown"]["CACHE"] == pytest.approx(1.0)

    def test_thread_starvation_metric(self, clean_registry, monkeypatch):
        metric = ThreadStarvationMetric()

        # Case 1: Stable (low) lag
        traces_stable_lag = [
            {"system_metric": True, "metadata": {"lag": 0.001}},
            {"system_metric": True, "metadata": {"lag": 0.001}},
            {"system_metric": True, "metadata": {"lag": 0.001}},
        ]
        score_stable = metric.compute(traces_stable_lag)
        assert score_stable > 0.9  # Should be high

        # Case 2: Unstable (high) lag
        traces_unstable_lag = [
            {"system_metric": True, "metadata": {"lag": 0.001}},
            {"system_metric": True, "metadata": {"lag": 0.05}},  # Spike
            {"system_metric": True, "metadata": {"lag": 0.001}},
        ]
        score_unstable = metric.compute(traces_unstable_lag)
        assert score_unstable < 0.2  # Should be very low due to aggressive penalization

        # Case 3: No lag data
        traces_no_lag = [
            {"name": "cpu_bound", "duration": 0.1},
            {"system_metric": True, "metadata": {"other_metric": 1.0}},
        ]
        score_no_lag = metric.compute(traces_no_lag)
        assert score_no_lag == pytest.approx(1.0)

        # Test registration and integration
        MetricRegistry.register(ThreadStarvationMetric)
        monkeypatch.setattr(
            pypss.core.core.MetricRegistry,
            "get_all",
            lambda: {"STARVE": ThreadStarvationMetric()},
        )
        report = compute_pss_from_traces(traces_stable_lag)
        assert "STARVE" in report["breakdown"]
        assert report["breakdown"]["STARVE"] == pytest.approx(round(score_stable, 2))

    def test_network_stability_metric(self, clean_registry, monkeypatch):
        metric = NetworkStabilityMetric()

        # Case 1: Stable Network (low CV)
        traces_stable_net = [
            {"name": "http_get", "duration": 0.1},
            {"name": "api_request", "duration": 0.1},
            {"name": "fetch_url", "duration": 0.1},
        ]
        score_stable = metric.compute(traces_stable_net)
        assert score_stable == pytest.approx(1.0)

        # Case 2: Unstable Network (high CV)
        traces_unstable_net = [
            {"name": "http_get", "duration": 0.05},
            {"name": "api_request", "duration": 0.5},  # Spike
            {"name": "fetch_url", "duration": 0.05},
        ]
        score_unstable = metric.compute(traces_unstable_net)
        assert score_unstable < 0.8  # Should be penalized

        # Case 3: No Network Traces
        traces_no_net = [
            {"name": "compute_cpu", "duration": 0.1},
            {"name": "local_func", "duration": 0.2},
        ]
        score_no_net = metric.compute(traces_no_net)
        assert score_no_net == pytest.approx(1.0)

        # Test registration and integration
        MetricRegistry.register(NetworkStabilityMetric)
        monkeypatch.setattr(
            pypss.core.core.MetricRegistry,
            "get_all",
            lambda: {"NET": NetworkStabilityMetric()},
        )
        report = compute_pss_from_traces(traces_stable_net)
        assert "NET" in report["breakdown"]
        assert report["breakdown"]["NET"] == pytest.approx(1.0)
