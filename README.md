# pypss

[![PyPI version](https://img.shields.io/pypi/v/pypss.svg)](https://pypi.org/project/pypss/)
[![Downloads](https://img.shields.io/pypi/dm/pypss.svg)](https://pypi.org/project/pypss/)
[![Python Versions](https://img.shields.io/pypi/pyversions/pypss.svg)](https://pypi.org/project/pypss/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Docs Status](https://github.com/Be-Wagile-India/pypss/actions/workflows/docs.yml/badge.svg)](https://github.com/Be-Wagile-India/pypss/actions/workflows/docs.yml)
[![Code Style: Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Type Checked: Mypy](https://img.shields.io/badge/type%20checked-mypy-blue.svg)](http://mypy-lang.org/)
[![Tests](https://img.shields.io/badge/tests-431%20passing-success.svg)](tests/)
[![Coverage](https://img.shields.io/badge/coverage-91.19%25-brightgreen.svg)](htmlcov/index.html)

Python systems often fail not because they are slow — but because they are unstable. `pypss` gives you the first metric that measures runtime flakiness, reliability, and stability in a single score.

**A zero-config runtime stability analyzer that scores your Python program’s reliability (0–100).**

<!-- SEO: Python stability score, runtime analyzer, performance monitoring, code reliability, flaky tests, microservices, ETL jobs, CI/CD, observability, Python metrics, latency, memory, errors, branching entropy, concurrency chaos -->

---

## 💡 Why Use pypss?

### Real Benefits for Your Engineering Team

| Benefit | Impact | Example |
| :--- | :--- | :--- |
| **📉 Catch Flakiness** | Detect intermittent issues early | Identify jittery API calls before production |
| **📊 Quantify Reliability** | A single score for stability | "Service A has a PSS of 92, Service B is 45" |
| **🚀 CI/CD Gates** | Block unstable builds automatically | Fail build if PSS < 80 |
| **🧠 Memory Insights** | Spot uncontrolled growth | Detect memory leaks in long-running jobs |
| **⚡ Performance Consistency** | Measure variance, not just speed | Ensure p95 latency is stable under load |
| **🔧 Zero Config** | Works out of the box | Just add `@monitor_function` and run |

## 🤔 When Should You Use pypss?

*   Flaky test suites
*   Microservices with unpredictable latency
*   Long-running ETL jobs with memory uncertainty
*   API clients with intermittent failures
*   CI pipelines needing release gating
*   Any project where “performance varies a lot”

## 🏗️ High-Level Architecture

```text
+-------------------------+
|   Instrumentation       |  (@monitor_function, etc.)
| (Your Code)             |
+-----------|-------------+
            | (Traces)
            v
+-----------|-------------+
|   Trace Collector       |  (In-Memory Buffer)
+-----------|-------------+
            |
            v
+-----------|-------------+
|   PSS Analyzer          |  (5 Stability Scores)
+-----------|-------------+
            | (Report)
            v
+-----------|-------------+
|   Reporting             |  (CLI, JSON, HTML)
+-------------------------+
```

## 📚 Documentation

For full documentation, please visit our [ReadTheDocs page](https://pypss.readthedocs.io/en/latest/).

*   :package: `Installation <docs/source/installation.rst>`_
*   :zap: `Quick Start <docs/source/quick_start.rst>`_
*   :rocket: `Key Features <docs/source/features.rst>`_
*   :chart_with_upwards_trend: `Benchmarks & Overhead <docs/source/benchmarks.rst>`_
*   :scroll: `Sample PSS Reports <docs/source/reports.rst>`_
*   :bar_chart: `Interactive Dashboard <docs/source/dashboard.rst>`_
*   :gear: `Configuration <docs/source/configuration.rst>`_
*   :computer: `CLI Usage <docs/source/cli_usage.rst>`_
*   :date: `Historical Trends & Regression Detection <docs/source/history_regression.rst>`_
*   :link: `Integrations <docs/source/integrations.rst>`_
*   :balance_scale: `Understanding the Metrics <docs/source/metrics_explained.rst>`_
*   :puzzle_piece: `Plugin System & Extensions <docs/source/plugins.rst>`_
*   :control_knobs: `Adaptive Sampling Modes <docs/source/adaptive_sampling.rst>`_

## 🔒 Safety for Production Use

Designed for minimal overhead and safe integration into production environments.

## ⚖️ Comparison with Existing Tools

| Tool | Purpose | `pypss` Difference |
| :--- | :--- | :--- |
| `pytest` | Unit/Integration testing | Measures stability *during* tests, not just pass/fail. |
| `timeit`/`cProfile` | Performance measurement (speed) | Measures *consistency* (jitter), not just average speed. |
| `memory-profiler`| Memory usage analysis | Focuses on stability and spikes, not just total allocation. |
| **`pypss`** | **Holistic Stability Scoring** | **Combines timing, memory, errors, and more into a single reliability score.** |

## 🛠️ Development

We use `make` to manage common development tasks.

```bash
make install     # Install dependencies
make test        # Run tests with coverage
make lint-fix    # Auto-fix linting issues
make check       # Run full suite (lint, type-check, test)
make docs        # Build HTML documentation
```

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

## 👥 Contributors

[![Contributors](https://contrib.rocks/image?repo=Be-Wagile-India/pypss)](https://github.com/Be-Wagile-India/pypss/graphs/contributors)

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **The Data Migration Company Team** & **Be-Wagile India Team** for their support.
- Inspired by the need for better observability in complex Python systems.

---

**Package Name**: `pypss` | **CLI Command**: `pypss` | **Import**: `import pypss`

TheDataMigrationCompany @2025 | BWI @2025