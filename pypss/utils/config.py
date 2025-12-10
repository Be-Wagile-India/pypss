import os
import re
import sys
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List

import toml

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

    sample_rate: float = 1.0
    max_traces: int = 10_000

    w_ts: float = 0.30
    w_ms: float = 0.20
    w_ev: float = 0.20
    w_be: float = 0.15
    w_cc: float = 0.15
    custom_metric_weights: Dict[str, float] = field(default_factory=dict)

    alpha: float = 2.0
    beta: float = 1.0
    gamma: float = 2.0
    mem_spike_threshold_ratio: float = 1.5  # Peak memory / Median memory ratio threshold.
    delta: float = 1.0
    error_spike_threshold: float = 0.1
    consecutive_error_threshold: int = 3
    concurrency_wait_threshold: float = 0.001

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

    ui_theme_primary: str = "#4285F4"
    ui_theme_secondary: str = "#607D8B"
    ui_theme_accent: str = "#34A853"
    ui_theme_positive: str = "#34A853"
    ui_theme_negative: str = "#EA4335"
    ui_theme_info: str = "#FBBC04"
    ui_theme_warning: str = "#FBBC04"
    ui_port: int = 8080
    ui_title: str = "PyPSS | Reliability Platform"

    dashboard_critical_pss_threshold: float = 60.0
    dashboard_warning_error_rate: float = 0.05

    background_dump_interval: int = 60
    background_archive_dir: str = "archive"

    default_trace_file: str = "pypss_output/traces.json"
    default_html_report_title: str = "PyPSS Stability Report"

    score_latency_tail_percentile: int = 94  # 95th percentile (0-indexed 94)
    score_memory_epsilon: float = 1e-9
    score_error_vmr_multiplier: float = 0.5
    score_error_spike_impact_multiplier: float = 0.5
    score_consecutive_error_decay_multiplier: float = 2.0

    collector_max_traces_sharding_threshold: int = 1000
    collector_shard_count: int = 16

    adaptive_sampler_min_interval: float = 5.0
    adaptive_sampler_lag_threshold: float = 0.05
    adaptive_sampler_churn_threshold: float = 20.0
    adaptive_sampler_error_threshold: float = 0.1
    adaptive_sampler_increase_step: float = 0.1
    adaptive_sampler_decrease_step: float = 0.05
    adaptive_sampler_max_rate: float = 1.0
    adaptive_sampler_min_rate: float = 0.01
    adaptive_sampler_mode: str = "balanced"
    adaptive_sampler_high_qps_threshold: float = 1000.0
    adaptive_sampler_low_noise_sample_rate: float = 0.01

    thread_starvation_sensitivity: float = 100.0
    plugins: List[str] = field(default_factory=list)

    error_sample_rate: float = 1.0
    context_sampling_rules: List[Dict[str, Any]] = field(default_factory=list)

    advisor_threshold_excellent: int = 90
    advisor_threshold_good: int = 75
    advisor_threshold_warning: int = 50
    advisor_metric_score_critical: float = 0.6
    advisor_metric_score_warning: float = 0.85
    advisor_error_critical: float = 0.7
    advisor_error_warning: float = 0.9
    advisor_entropy_threshold: float = 0.8

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

    discovery_file_extension: str = ".py"
    discovery_ignore_modules: list = field(default_factory=lambda: ["pypss"])
    discovery_ignore_funcs_prefix: str = "_"
    discovery_unknown_module_name: str = "unknown"

    llm_openai_model: str = "gpt-4o"
    llm_ollama_url: str = "http://localhost:11434/api/generate"
    llm_ollama_model: str = "llama3"
    llm_max_tokens: int = 1000

    alerts_enabled: bool = False
    alerts_slack_webhook: str = ""
    alerts_teams_webhook: str = ""
    alerts_generic_webhook: str = ""
    alerts_alertmanager_url: str = ""
    alerts_cooldown_seconds: int = 3600

    custom_alert_rules: List[Dict[str, Any]] = field(default_factory=list)

    alert_threshold_ts: float = 0.70
    alert_threshold_ms: float = 0.70
    alert_threshold_ev: float = 0.80
    alert_threshold_be: float = 0.70
    alert_threshold_cc: float = 0.70

    dashboard_layout: List[Dict[str, Any]] = field(
        default_factory=lambda: [
            {"type": "pss_gauge", "col_span": 3, "tab": "overview"},
            {"type": "total_traces_kpi", "col_span": 3, "tab": "overview"},
            {"type": "error_rate_kpi", "col_span": 3, "tab": "overview"},
            {"type": "avg_latency_kpi", "col_span": 3, "tab": "overview"},
            {"type": "metric_breakdown", "col_span": 4, "tab": "overview"},
            {"type": "ai_advisor", "col_span": 8, "tab": "overview"},
            {"type": "historical_trend", "col_span": 6, "tab": "overview"},
            {"type": "module_table", "col_span": 6, "tab": "overview"},
            {"type": "metrics_stability_trends", "col_span": 12, "tab": "metrics"},
            {"type": "error_heatmap", "col_span": 6, "tab": "diagnostics"},
            {"type": "entropy_heatmap", "col_span": 6, "tab": "diagnostics"},
            {"type": "latency_percentiles_chart", "col_span": 12, "tab": "performance"},
            {"type": "concurrency_distribution", "col_span": 12, "tab": "performance"},
        ]
    )

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

        # 3. Pre-compile regex patterns for sampling rules
        for rule in config.context_sampling_rules:
            if "pattern" in rule and isinstance(rule["pattern"], str):
                try:
                    rule["pattern_compiled"] = re.compile(rule["pattern"])
                except re.error:
                    pass

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

        # Remove compiled patterns before saving
        if "context_sampling_rules" in config_dict:
            for rule in config_dict["context_sampling_rules"]:
                if "pattern_compiled" in rule:
                    del rule["pattern_compiled"]

        output_data = {"pypss": config_dict}

        try:
            with open(file_path, "w") as f:
                toml.dump(output_data, f)
        except Exception as e:
            print(f"Error saving config to {file_path}: {e}")


class SamplingStrategy(Enum):
    ALWAYS = "always"
    NEVER = "never"
    RANDOM = "random"
    ON_ERROR = "on_error"

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}.{self.name}: '{self.value}'>"

    @classmethod
    def _missing_(cls, value: object):
        if isinstance(value, str):
            for member in cls:
                if member.value == value:
                    return member
        return super()._missing_(value)


def _get_effective_sample_rate(is_error: bool, trace_name: str, trace_module: str) -> float:
    """
    Determines the effective sample rate based on context-aware rules and error status.
    Precedence: error_sample_rate > context_sampling_rules > GLOBAL_CONFIG.sample_rate
    """
    if is_error:
        return GLOBAL_CONFIG.error_sample_rate

    for rule in GLOBAL_CONFIG.context_sampling_rules:
        pattern_compiled = rule.get("pattern_compiled")

        matched = False
        if pattern_compiled:
            if pattern_compiled.match(trace_name) or pattern_compiled.match(trace_module):
                matched = True
        else:
            pattern = rule.get("pattern")
            if pattern and (re.match(pattern, trace_name) or re.match(pattern, trace_module)):
                matched = True

        if matched:
            strategy_str = rule.get("strategy", SamplingStrategy.RANDOM.value)
            rule_sample_rate = rule.get("sample_rate")

            strategy = SamplingStrategy(strategy_str)

            if strategy == SamplingStrategy.ALWAYS:
                return 1.0
            elif strategy == SamplingStrategy.NEVER:
                return 0.0
            elif strategy == SamplingStrategy.ON_ERROR:
                if is_error:
                    return 1.0
                else:
                    return 0.0

            elif strategy == SamplingStrategy.RANDOM:
                if isinstance(rule_sample_rate, (int, float)):
                    return float(rule_sample_rate)
                else:
                    return GLOBAL_CONFIG.sample_rate

    return GLOBAL_CONFIG.sample_rate


GLOBAL_CONFIG = PSSConfig.load()
