# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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