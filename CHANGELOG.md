# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.8.0] - 2025-11-29

### 🚀 Major Improvements
- **Configuration Refactor:** Moved all hardcoded settings (UI colors, thresholds, integration prefixes) to a centralized `pypss.toml` file.
- **Enhanced Configuration:** Added support for nested TOML sections for better organization (`[pypss.ui]`, `[pypss.integration.celery]`, etc.).
- **Async Support:** Improved discovery logic to correctly identify and instrument `async def` functions.
- **Trace & Verify:** Added `scripts/verify_and_regenerate.py` for robust data verification.

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