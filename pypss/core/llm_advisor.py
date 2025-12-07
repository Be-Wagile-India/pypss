import json
import statistics
from typing import List, Dict, Optional
from abc import ABC, abstractmethod  # Added import
from ..utils.source_code import extract_function_code
from ..utils.config import GLOBAL_CONFIG


class TraceSummarizer:
    @staticmethod
    def summarize(traces: List[Dict], module_name: str = "unknown") -> str:
        if not traces:
            return "No traces collected."

        durations = [t["duration"] for t in traces]
        errors = [t for t in traces if t["error"]]

        stats = {
            "count": len(traces),
            "p50_duration": statistics.median(durations),
            "p95_duration": sorted(durations)[int(len(durations) * 0.95)]
            if len(durations) > 1
            else durations[0],
            "error_rate": len(errors) / len(traces),
            "avg_cpu_time": statistics.mean(t.get("cpu_time", 0) for t in traces),
            "avg_wait_time": statistics.mean(t.get("wait_time", 0) for t in traces),
            "avg_memory_growth_mb": statistics.mean(
                t.get("memory_diff", 0) for t in traces
            )
            / (1024 * 1024),
        }

        # Find anomalies (slowest success vs failure)
        slowest = max(traces, key=lambda x: x["duration"])

        # Extract Source Code
        filename = slowest.get("filename", "unknown")
        lineno = slowest.get("lineno", 0)
        source_code = extract_function_code(filename, lineno)

        return f"""
Analysis Context for Module: {module_name}
----------------------------------------
Statistics:
- Execution Count: {stats["count"]}
- P50 Latency: {stats["p50_duration"]:.4f}s
- P99 Latency: {stats["p95_duration"]:.4f}s
- Error Rate: {stats["error_rate"]:.1%}
- Avg CPU Time: {stats["avg_cpu_time"]:.4f}s
- Avg Wait (I/O) Time: {stats["avg_wait_time"]:.4f}s
- Avg Memory Growth: {stats["avg_memory_growth_mb"]:.2f} MB

Source Code (extracted from {filename}:{lineno}):
```python
{source_code}
```

Sample Trace (Slowest):
{json.dumps(slowest, default=str, indent=2)}
"""


class LLMClient(ABC):
    @abstractmethod
    def generate_diagnosis(self, context: str) -> Optional[str]:
        pass


class OpenAIClient(LLMClient):
    def __init__(self, api_key: Optional[str] = None):
        try:
            from openai import OpenAI

            self.client = OpenAI(api_key=api_key)
        except ImportError:
            raise ImportError("Install 'openai' package to use OpenAI advisor")

    def generate_diagnosis(self, context: str) -> Optional[str]:
        prompt = f"""
You are a Senior Python Performance Engineer. Analyze the following runtime metrics, trace data, and SOURCE CODE.
Identify the root cause of instability (latency spikes, errors, or memory leaks).
Correlate the metrics (CPU vs Wait time, Memory Growth) with specific lines in the provided source code.
Provide concrete code recommendations.

{context}
"""
        response = self.client.chat.completions.create(
            model=GLOBAL_CONFIG.llm_openai_model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=GLOBAL_CONFIG.llm_max_tokens,
        )
        return response.choices[0].message.content


class OllamaClient(LLMClient):
    def __init__(self, model: Optional[str] = None):
        self.model = model or GLOBAL_CONFIG.llm_ollama_model
        import requests  # core dep usually, but verify

        self.requests = requests

    def generate_diagnosis(self, context: str) -> Optional[str]:
        prompt = f"""
You are a Python Performance Expert. Analyze these metrics and the provided source code to diagnose the instability.
Point out specific lines that might be causing the issues.

{context}
"""
        try:
            res = self.requests.post(
                GLOBAL_CONFIG.llm_ollama_url,
                json={"model": self.model, "prompt": prompt, "stream": False},
            )
            if res.status_code == 200:
                return res.json().get("response", "No response from Ollama")
            return f"Ollama Error: {res.text}"
        except Exception as e:
            return f"Ollama Connection Failed: {e}"


def get_llm_diagnosis(
    traces: List[Dict], provider: str = "openai", api_key: Optional[str] = None
) -> Optional[str]:
    summary = TraceSummarizer.summarize(traces)

    client: LLMClient
    if provider == "openai":
        client = OpenAIClient(api_key)
    elif provider == "ollama":
        client = OllamaClient()
    else:
        return "Unknown provider"

    return client.generate_diagnosis(summary)
