# tests/examples/test_complex_app.py
import os
import pytest
from pypss.core import compute_pss_from_traces
from examples.complex_app.complex_web_service import run_service_simulation


@pytest.fixture(scope="module")
def complex_app_traces():
    """Run the complex web service simulation once and return its traces."""
    # Use a temporary file for traces during testing
    test_output_dir = os.path.join(os.path.dirname(__file__), "temp_traces")
    os.makedirs(test_output_dir, exist_ok=True)
    trace_file_path = os.path.join(test_output_dir, "test_complex_app_traces.json")

    # Run a smaller simulation for tests to keep them fast
    traces = run_service_simulation(num_requests=30, trace_file=trace_file_path)

    # Clean up the generated trace file and directory after tests are done
    yield traces
    if os.path.exists(trace_file_path):
        os.remove(trace_file_path)
    if os.path.exists(test_output_dir):
        os.rmdir(test_output_dir)


class TestComplexApp:
    def test_simulation_generates_traces(self, complex_app_traces):
        assert complex_app_traces is not None
        assert len(complex_app_traces) > 0
        assert isinstance(complex_app_traces[0], dict)
        assert "duration" in complex_app_traces[0]

    def test_pss_report_generated(self, complex_app_traces):
        report = compute_pss_from_traces(complex_app_traces)
        assert report is not None
        assert "pss" in report
        assert "breakdown" in report

    def test_pss_score_range(self, complex_app_traces):
        report = compute_pss_from_traces(complex_app_traces)
        # Given the simulated variability, the score should not be perfect 100
        # and should not be 0 (unless all traces failed, which is unlikely for 30 requests)
        assert 0 < report["pss"] < 100

    def test_breakdown_scores_exist(self, complex_app_traces):
        report = compute_pss_from_traces(complex_app_traces)
        breakdown = report["breakdown"]
        assert "timing_stability" in breakdown
        assert "memory_stability" in breakdown
        assert "error_volatility" in breakdown
        assert "branching_entropy" in breakdown
        assert "concurrency_chaos" in breakdown

        # Verify that scores are within expected range [0, 1] (after rounding to 2 decimal places)
        for score_value in breakdown.values():
            assert 0.0 <= score_value <= 1.0

    def test_error_volatility_reflects_errors(self, complex_app_traces):
        # Check if there are any errors in the traces
        has_errors = any(t.get("error", False) for t in complex_app_traces)
        report = compute_pss_from_traces(complex_app_traces)
        ev_score = report["breakdown"]["error_volatility"]

        if has_errors:
            # If errors exist, the error volatility score should be less than 1.0
            assert ev_score < 1.0
        else:
            # If no errors exist (unlikely in simulation), the score should be high (<= 1.0)
            assert ev_score <= 1.0
