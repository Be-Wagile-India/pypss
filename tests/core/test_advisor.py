from pypss.core.advisor import StabilityAdvisor, generate_advisor_report


class TestAdvisor:
    def test_advisor_perfect_score(self):
        report = {
            "pss": 100,
            "breakdown": {
                "timing_stability": 1.0,
                "memory_stability": 1.0,
                "error_volatility": 1.0,
                "branching_entropy": 1.0,
                "concurrency_chaos": 1.0,
            },
        }
        advisor = StabilityAdvisor(report)
        result = advisor.analyze()

        assert "exceptional stability" in result["summary"]
        assert not result["diagnosis"]  # Should be empty or mostly empty
        assert not result["advice"]

    def test_advisor_critical_instability(self):
        report = {
            "pss": 40,
            "breakdown": {
                "timing_stability": 0.5,
                "memory_stability": 0.5,
                "error_volatility": 0.5,
                "branching_entropy": 0.5,
                "concurrency_chaos": 0.5,
            },
        }
        advisor = StabilityAdvisor(report)
        result = advisor.analyze()

        assert "critically unstable" in result["summary"]

        # Check specific rules
        diagnosis_text = result["diagnosis"]
        assert "Correlated volatility in Timing and Memory" in diagnosis_text
        assert "Severe latency jitter" in diagnosis_text
        assert "Critical memory instability" in diagnosis_text
        assert "High Error Volatility" in diagnosis_text
        assert "Severe Concurrency Chaos" in diagnosis_text

    def test_advisor_moderate_instability(self):
        report = {
            "pss": 80,
            "breakdown": {
                "timing_stability": 0.8,
                "memory_stability": 0.8,
                "error_volatility": 0.8,
                "branching_entropy": 0.8,
                "concurrency_chaos": 0.8,
            },
        }
        advisor = StabilityAdvisor(report)
        result = advisor.analyze()

        assert "stable, but shows minor signs" in result["summary"]
        assert "Moderate timing inconsistency" in result["diagnosis"]
        assert "Mild locking overhead" in result["diagnosis"]

    def test_generate_advisor_report(self):
        report = {"pss": 95, "breakdown": {}}
        output = generate_advisor_report(report)
        assert "AI Stability Diagnosis" in output
        assert "exceptional stability" in output
