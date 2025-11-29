import json
from pypss.cli.reporting import render_report_text, render_report_json


class TestReporting:
    def test_render_report_json(self):
        report = {"pss": 80, "breakdown": {"timing_stability": 0.8}}
        json_output = render_report_json(report)
        data = json.loads(json_output)
        assert data["pss"] == 80
        assert data["breakdown"]["timing_stability"] == 0.8

    def test_render_report_text(self):
        report = {
            "pss": 50,
            "breakdown": {
                "timing_stability": 0.5,
                "memory_stability": 0.6,
                "error_volatility": 0.7,
                "branching_entropy": 0.8,
                "concurrency_chaos": 0.9,
            },
        }
        text_output = render_report_text(report)

        assert "PSS: 50/100" in text_output
        assert "Timing Stability: 0.50" in text_output
        assert "Memory Stability: 0.60" in text_output
        # Check that advisor output is included (it adds "AI Stability Diagnosis")
        assert "AI Stability Diagnosis" in text_output
