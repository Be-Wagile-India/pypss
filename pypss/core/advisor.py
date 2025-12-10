from typing import Dict, List

from ..utils import GLOBAL_CONFIG


class StabilityAdvisor:
    """
    The 'Brain' of pypss. Analyzes stability metrics to provide
    human-readable diagnoses and actionable advice.
    """

    def __init__(self, report: Dict):
        self.report = report
        self.pss = report.get("pss", 0)
        self.breakdown = report.get("breakdown", {})
        self.advice: List[str] = []
        self.diagnosis: List[str] = []

        self.rules = [
            self._analyze_overall,
            self._analyze_timing,
            self._analyze_memory,
            self._analyze_errors,
            self._analyze_entropy,
            self._analyze_concurrency,
        ]

    def analyze(self) -> Dict[str, str]:
        """Performs the analysis and returns a dictionary with 'diagnosis' and 'advice'."""
        for rule in self.rules:
            rule()

        return {
            "summary": self._generate_summary(),
            "diagnosis": "\n".join(f"- {d}" for d in self.diagnosis),
            "advice": "\n".join(f"- {a}" for a in self.advice),
        }

    def _generate_summary(self) -> str:
        if self.pss >= GLOBAL_CONFIG.advisor_threshold_excellent:
            return "🚀 System is performing with exceptional stability. Rock solid."
        elif self.pss >= GLOBAL_CONFIG.advisor_threshold_good:
            return "✅ System is stable, but shows minor signs of variance in specific areas."
        elif self.pss >= GLOBAL_CONFIG.advisor_threshold_warning:
            return "⚠️ System is exhibiting significant flakiness. Reliability is at risk."
        else:
            return "🔥 System is critically unstable. Immediate remediation required."

    def _analyze_overall(self):
        ts = self.breakdown.get("timing_stability", 1.0)
        ms = self.breakdown.get("memory_stability", 1.0)

        threshold = GLOBAL_CONFIG.advisor_metric_score_critical + 0.1
        if ts < threshold and ms < threshold:
            self.diagnosis.append("Correlated volatility in Timing and Memory.")
            self.advice.append(
                "High memory usage might be causing Garbage Collection pauses. Profile memory allocation."
            )

    def _analyze_timing(self):
        score = self.breakdown.get("timing_stability", 1.0)
        if score < GLOBAL_CONFIG.advisor_metric_score_critical:
            self.diagnosis.append("Severe latency jitter detected (High variance or heavy tail).")
            self.advice.append("Check for blocking I/O operations in your hot path.")
            self.advice.append("Consider implementing a timeout budget or circuit breaker.")
        elif score < GLOBAL_CONFIG.advisor_metric_score_warning:
            self.diagnosis.append("Moderate timing inconsistency.")
            self.advice.append("Investigate potential resource contention (CPU/Disk) causing sporadic delays.")

    def _analyze_memory(self):
        score = self.breakdown.get("memory_stability", 1.0)
        if score < GLOBAL_CONFIG.advisor_metric_score_critical:
            self.diagnosis.append("Critical memory instability (spikes or rapid growth).")
            self.advice.append("Potential memory leak or inefficient large object allocation detected.")
        elif score < GLOBAL_CONFIG.advisor_metric_score_warning:
            self.diagnosis.append("Memory usage is fluctuating more than expected.")
            self.advice.append("Review data processing batch sizes; they might be inconsistent.")

    def _analyze_errors(self):
        score = self.breakdown.get("error_volatility", 1.0)
        if score < GLOBAL_CONFIG.advisor_error_critical:
            self.diagnosis.append("High Error Volatility: Failures are bursty and unpredictable.")
            self.advice.append("Suggests external dependency failures or race conditions.")
        elif score < GLOBAL_CONFIG.advisor_error_warning:
            self.diagnosis.append("Occasional errors are impacting stability.")

    def _analyze_entropy(self):
        score = self.breakdown.get("branching_entropy", 1.0)
        if score < GLOBAL_CONFIG.advisor_entropy_threshold:
            self.diagnosis.append("High Branching Entropy: Execution paths are highly unpredictable.")
            self.advice.append("Code flow is data-dependent to an extreme degree. Ensure all edge cases are tested.")

    def _analyze_concurrency(self):
        score = self.breakdown.get("concurrency_chaos", 1.0)
        if score < GLOBAL_CONFIG.advisor_metric_score_critical:
            self.diagnosis.append("Severe Concurrency Chaos: Thread/Process wait times are highly inconsistent.")
            self.advice.append("High contention on locks or shared resources detected. Review critical sections.")
        elif score < GLOBAL_CONFIG.advisor_metric_score_warning:
            self.diagnosis.append("Mild locking overhead detected.")


def generate_advisor_report(report: Dict) -> str:
    advisor = StabilityAdvisor(report)
    result = advisor.analyze()

    return f"""
🧠 AI Stability Diagnosis
=========================
{result["summary"]}

🔍 Observations:
{result["diagnosis"]}

💡 Recommendations:
{result["advice"]}
"""
