from pypss.cli.html_report import render_report_html


class TestHTMLReport:
    def test_render_report_html(self):
        report = {
            "pss": 85,
            "breakdown": {
                "timing_stability": 0.8,
                "memory_stability": 0.9,
                "error_volatility": 0.7,
                "branching_entropy": 1.0,
                "concurrency_chaos": 0.85,
            },
        }
        advisor_text = "Advisor says all good."

        html = render_report_html(report, advisor_text)

        assert "<!DOCTYPE html>" in html
        assert "85" in html
        assert "Advisor says all good" in html
        assert "Timing Stability" in html
        # Check for JS injection of values
        assert "0.8" in html
