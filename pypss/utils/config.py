import os
import sys
import toml
from dataclasses import dataclass, asdict, field
from typing import Dict, Any

if sys.version_info >= (3, 11):
    import tomllib as tomli
else:
    import tomli


@dataclass
class PSSConfig:
    """
    Configuration holder for PyPSS.

    This dataclass defines all tunable parameters for the library, including:
    - Sampling rates and buffer sizes.
    - Weights for the 5 stability pillars (Timing, Memory, Error, Entropy, Concurrency).
    - Sensitivity thresholds for scoring algorithms.
    - Integration settings (Celery, Flask, OTel, etc.).
    - UI customization for the dashboard.

    It is automatically populated from `pypss.toml` or `pyproject.toml` (under `[tool.pypss]`)
    via the `load()` method.
    """

    # Sampling
    sample_rate: float = 1.0  # 0.0 to 1.0
    max_traces: int = 10_000  # Ring buffer size

    # Weights
    w_ts: float = 0.30  # Timing Stability
    w_ms: float = 0.20  # Memory Stability
    w_ev: float = 0.20  # Error Volatility
    w_be: float = 0.15  # Branching Entropy
    w_cc: float = 0.15  # Concurrency Chaos

    # Thresholds / Sensitivity
    alpha: float = 2.0  # Timing CV sensitivity
    beta: float = 1.0  # Timing Tail sensitivity
    gamma: float = 2.0  # Memory sensitivity
    mem_spike_threshold_ratio: float = 1.5  # Peak memory / Median memory ratio threshold. A ratio of 1.5 means peak can be 50% higher than median.
    delta: float = 1.0  # Error sensitivity
    error_spike_threshold: float = 0.1  # Threshold for a significant jump in error rate (e.g., 0.1 means 10% error rate is concerning)
    consecutive_error_threshold: int = (
        3  # Number of consecutive errors to trigger an additional penalty
    )
    concurrency_wait_threshold: float = 0.001  # Minimum mean wait time (in seconds) to consider for concurrency chaos calculation

    # Discovery
    discovery_ignore_dirs: list = field(
        default_factory=lambda: [
            ".venv",
            "venv",
            "tests",
            "test",
            "__pycache__",
            ".git",
            "build",
            "dist",
            "docs",
            "examples",
            "scripts",
            "notebooks",
            ".vscode",
            ".idea",
        ]
    )

    # UI Configuration
    ui_theme_primary: str = "#4285F4"
    ui_theme_secondary: str = "#607D8B"
    ui_theme_accent: str = "#34A853"
    ui_theme_positive: str = "#34A853"
    ui_theme_negative: str = "#EA4335"
    ui_theme_info: str = "#FBBC04"
    ui_theme_warning: str = "#FBBC04"
    ui_port: int = 8080
    ui_title: str = "PyPSS | Reliability Platform"

    # Dashboard Logic
    dashboard_critical_pss_threshold: float = 60.0
    dashboard_warning_error_rate: float = 0.05

    # Background Instrumentation
    background_dump_interval: int = 60
    background_archive_dir: str = "archive"

    # Defaults
    default_trace_file: str = "pypss_output/traces.json"
    default_html_report_title: str = "PyPSS Stability Report"

    # Core Logic
    score_latency_tail_percentile: int = 94  # 95th percentile (0-indexed 94)
    score_memory_epsilon: float = 1e-9
    score_error_vmr_multiplier: float = 0.5
    score_error_spike_impact_multiplier: float = 0.5
    score_consecutive_error_decay_multiplier: float = 2.0

    # Collector
    collector_max_traces_sharding_threshold: int = 1000
    collector_shard_count: int = 16

    # Advisor
    advisor_threshold_excellent: int = 90
    advisor_threshold_good: int = 75
    advisor_threshold_warning: int = 50
    advisor_metric_score_critical: float = 0.6
    advisor_metric_score_warning: float = 0.85
    advisor_error_critical: float = 0.7
    advisor_error_warning: float = 0.9
    advisor_entropy_threshold: float = 0.8

    # Integrations
    header_pss_latency: str = "X-PSS-Latency"
    header_pss_wait: str = "X-PSS-Wait"
    integration_celery_trace_prefix: str = "celery:"
    integration_flask_trace_prefix: str = "flask:"
    integration_flask_header_latency: str = "X-PSS-Latency"
    integration_flask_header_wait: str = "X-PSS-Wait"
    integration_rq_trace_prefix: str = "rq:"
    integration_pytest_trace_prefix: str = "test::"
    integration_otel_metric_prefix: str = "pypss."
    integration_otel_meter_name: str = "pypss"
    integration_otel_meter_version: str = "0.1.0"

    # Discovery (Scanning)
    discovery_file_extension: str = ".py"
    discovery_ignore_modules: list = field(default_factory=lambda: ["pypss"])
    discovery_ignore_funcs_prefix: str = "_"
    discovery_unknown_module_name: str = "unknown"

    # LLM Advisor
    llm_openai_model: str = "gpt-4o"
    llm_ollama_url: str = "http://localhost:11434/api/generate"
    llm_ollama_model: str = "llama3"
    llm_max_tokens: int = 1000

    # Storage
    storage_backend: str = "sqlite"
    storage_uri: str = "pypss_history.db"
    regression_threshold_drop: float = 10.0
    regression_history_limit: int = 5

    @classmethod
    def load(cls) -> "PSSConfig":
        """
        Loads config from pypss.toml, pyproject.toml, or env vars.
        """
        config = cls()

        # 1. Try pypss.toml
        if os.path.exists("pypss.toml"):
            with open("pypss.toml", "rb") as f:
                data = tomli.load(f)
                config._update(data.get("pypss", {}))

        # 2. Try pyproject.toml
        elif os.path.exists("pyproject.toml"):
            with open("pyproject.toml", "rb") as f:
                data = tomli.load(f)
                config._update(data.get("tool", {}).get("pypss", {}))

        return config

    def _update(self, data: Dict[str, Any], prefix: str = ""):
        for k, v in data.items():
            full_key = f"{prefix}{k}"
            if isinstance(v, dict):
                self._update(v, prefix=f"{full_key}_")
            elif hasattr(self, full_key):
                setattr(self, full_key, v)

    def save(self, file_path: str = "pypss.toml"):
        """
        Saves the current config to a TOML file.
        """
        config_dict = asdict(self)
        output_data = {"pypss": config_dict}

        try:
            with open(file_path, "w") as f:
                toml.dump(output_data, f)
        except Exception as e:
            print(f"Error saving config to {file_path}: {e}")


# Global singleton
GLOBAL_CONFIG = PSSConfig.load()
