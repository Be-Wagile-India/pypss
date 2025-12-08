# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.3.0] - Unreleased

### 🚀 New Features
- **AI Diagnosis CLI:** Added `diagnose` command to the CLI. Allows users to send trace data to LLM providers (OpenAI or Ollama) for automated root cause analysis.
- **Monitoring Integration:** Added formal support for Prometheus metrics (PushGateway and Pull mode) via `[monitoring]` optional dependency.

### 🛡️ Engineering & Quality
- **Type Safety:** Achieved full `mypy` compliance. Added missing type stubs (`types-grpcio`, `types-redis`, etc.) and fixed numerous type errors.
- **Dependencies:** Updated `pyproject.toml` and `requirements` files to explicitly list all optional dependencies and type stubs.

### 📚 Documentation
- **Installation Guide:** Updated with comprehensive details on optional dependencies (`[distributed]`, `[monitoring]`, `[llm]`).
- **CLI Usage:** Added documentation for the new `diagnose` command.
- **Advanced Config:** Detailed Prometheus configuration options.

---

## [1.2.0] - Unreleased

### 📈 Dashboard Overhaul
- **New UI/UX:** Complete redesign of the interactive dashboard with a cleaner, modern look.
- **AI Advisor:** Added an automated diagnostic engine that analyzes reports and provides actionable text recommendations.
- **Advanced Diagnostics:**
    - **Error Heatmaps:** Visualize error density over time and modules.
    - **Entropy Heatmaps:** Track logic complexity hot spots.
- **Performance Deep Dive:**
    - **Latency Percentiles:** P50/P90/P99 trends.
    - **Concurrency Analysis:** Violin plots for CPU vs. Wait time distributions.
- **Real-time Metrics:** Live streaming line charts for all stability metrics.

### 🐛 Bug Fixes
- **Dashboard:** Fixed infinite recursion issue when running dashboard in multiprocessing environments.
- **Dashboard:** Fixed "Starting dashboard..." log spam on page refresh.
- **Dashboard:** Fixed `AttributeError` in KPI cards.
- **Dashboard:** Fixed plotting issues with sparse data in trend charts.

---

## [1.1.0] - Unreleased

### 🚀 New Features
- **Distributed Trace Collectors:** Added robust collectors for distributed environments:
    - `RedisCollector`: High-throughput trace ingestion via Redis pipelines.
    - `FileFIFOCollector`: Multi-process safe logging with advisory locks.
    - `GRPCCollector`: Remote trace submission via gRPC.
- **Async Batch Processing:** Base `ThreadedBatchCollector` ensures zero blocking on main application threads.

---

## [1.0.0] - 2025-11-29

### 🚀 Major Release: Production Ready
- **Stability:** Reclassified as Production/Stable.
- **Configuration Refactor:** Moved all hardcoded settings to centralized `pypss.toml`.
- **Enhanced Configuration:** Support for nested TOML sections (`[pypss.ui]`, `[pypss.integration]`).
- **Async Support:** Improved discovery and instrumentation for `async def`.
- **Integrations:** OpenTelemetry export, plus Celery, Flask, and FastAPI support.
- **Verification:** Robust data verification scripts.

## [0.1.0] - 2025-11-26

### 🎉 Initial Release

#### ✨ Features
- **Core Stability Metrics:** Implemented calculation for:
    - Timing Stability (TS)
    - Memory Stability (MS)
    - Error Volatility (EV)
    - Branching Entropy (BE)
- **Instrumentation:** Added `@monitor_function` decorator and `monitor_block` context manager.
- **CLI:** Added `pypss` command-line tool with `analyze` command.
- **Reporting:** Basic text and JSON output formats.

#### 🔧 Engineering
- **Project Structure:** Established standard Python package layout.
- **Testing:** Added unit tests for core logic, utils, and instrumentation.
- **Dev Tools:** Integrated `ruff`, `mypy`, and `pytest`.
- **Docs:** Setup Sphinx documentation and created comprehensive `README.md`.
- **CI/CD:** Added `Makefile` for local automation.