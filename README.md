# pypss

[![PyPI version](https://img.shields.io/pypi/v/pypss.svg)](https://pypi.org/project/pypss/)
[![Downloads](https://img.shields.io/pypi/dm/pypss.svg)](https://pypi.org/project/pypss/)
[![Python Versions](https://img.shields.io/pypi/pyversions/pypss.svg)](https://pypi.org/project/pypss/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Docs Status](https://github.com/Be-Wagile-India/pypss/actions/workflows/docs.yml/badge.svg)](https://github.com/Be-Wagile-India/pypss/actions/workflows/docs.yml)
[![Code Style: Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Type Checked: Mypy](https://img.shields.io/badge/type%20checked-mypy-blue.svg)](http://mypy-lang.org/)
[![Tests](https://img.shields.io/badge/tests-563%20passing-success.svg)](tests/)
[![Coverage](https://img.shields.io/badge/coverage-81.03%25-brightgreen.svg)](htmlcov/index.html)

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

## 🚀 Key Features

### Core Capabilities
- **Multi-dimensional Scoring**: Combines 5 distinct stability dimensions into one 0-100 score.
- **Timing Stability (TS)**: Penalizes high variance (CV) and long tail latencies (p95/p50).
- **Memory Stability (MS)**: Tracks erratic memory spikes and growth patterns.
- **Error Volatility (EV)**: Distinguishes between consistent failures and chaotic, bursty errors.
- **Branching Entropy (BE)**: Measures the unpredictability of code execution paths.
- **Async-Aware Instrumentation**: Natively handles `async` functions to measure event loop stability.
- **Concurrency Chaos (CC)**: *(Experimental)* Quantifies thread contention and locking overhead.
- **Alerting Engine**: Proactively monitors and notifies on stability changes with configurable rules and channels.

### Developer Experience
- **Non-Intrusive Instrumentation**: Lightweight decorators and context managers.
- **CLI Analysis**: Analyze trace files from production logs or test runs.
- **Type Safe**: Fully typed codebase with `mypy` compliance.
- **Production Ready**: Minimal overhead for sampling stability in critical paths.

## ⏱️ Benchmarks & Overhead

Runtime Overhead:
*   Decorator overhead: ~0.8–1.2 μs per call
*   Trace flush: background + negligible
*   No heavy memory sampling
*   Suitable for production with sampling rate control

## 🔒 Safety for Production Use

Designed for minimal overhead and safe integration into production environments.

## 📦 Installation

### Basic Installation

```bash
pip install pypss
```

### Development Installation

```bash
git clone https://github.com/Be-Wagile-India/pypss.git
cd pypss
make install
```

## ⚡ Quick Start

### Simple Instrumentation

```python
import time
import random
from pypss.instrumentation import monitor_function, global_collector
from pypss.core import compute_pss_from_traces
from pypss.reporting import render_report_text

# 1. Decorate functions you want to measure
@monitor_function("critical_op")
def critical_operation():
    # Simulate work with some jitter
    time.sleep(random.uniform(0.01, 0.02))
    if random.random() < 0.05:
        raise ValueError("Random failure!")

# 2. Run your workload
print("Running workload...")
for _ in range(100):
    try:
        critical_operation()
    except ValueError:
        pass

# 3. Compute and print the PSS Score
traces = global_collector.get_traces()
report = compute_pss_from_traces(traces)

print(render_report_text(report))
```

### Context Manager Usage

For fine-grained control over specific blocks of code:

```python
from pypss.instrumentation import monitor_block

def process_data(items):
    with monitor_block("data_processing", branch_tag="batch_start"):
        # ... complex logic ...
        pass
```

#### Using `branch_tag` for Deeper Insights

The `branch_tag` parameter is a powerful feature for analyzing different code paths within the same function. For example, you can measure the stability of a cache hit versus a cache miss:

```python
def get_user_data(user_id):
    if is_cached(user_id):
        with monitor_block("get_user_data", branch_tag="cache_hit"):
            return from_cache(user_id)
    else:
        with monitor_block("get_user_data", branch_tag="cache_miss"):
            return from_database(user_id)
```

## ✨ Sample PSS Report

### Example 1: An Unstable Program (Low PSS)

```text
Python Program Stability Score (PSS) Report
===========================================
PSS: 61/100

Breakdown:
  - Timing Stability: 0.27
  - Memory Stability: 0.99
  - Error Volatility: 0.59
  - Branching Entropy: 1.00
  - Concurrency Chaos: 0.42

🧠 AI Stability Diagnosis
=========================
⚠️ System is exhibiting significant flakiness. Reliability is at risk.

🔍 Observations:
- Severe latency jitter detected (High variance or heavy tail).
- High Error Volatility: Failures are bursty and unpredictable.
- Severe Concurrency Chaos: Thread/Process wait times are highly inconsistent.
```

### Example 2: A Stable Program (High PSS)

```text
Python Program Stability Score (PSS) Report
===========================================
PSS: 98/100

Breakdown:
  - Timing Stability: 0.95
  - Memory Stability: 0.99
  - Error Volatility: 1.00
  - Branching Entropy: 1.00
  - Concurrency Chaos: 0.98

🧠 AI Stability Diagnosis
=========================
✅ System is stable. No significant issues detected.
```

## 📈 Interactive Dashboard

`pypss` includes a real-time interactive dashboard to visualize stability metrics and traces.

To use the dashboard, first install the optional dependencies:
```bash
pip install pypss[dashboard]
```

Then, run the `board` command with your trace file:
```bash
pypss board traces.json
```

## ⚙️ Configuration

You can configure `pypss` using `pypss.toml` or `pyproject.toml` in your project root. This allows you to tune weights, thresholds, and sampling rates.

### Example `pyproject.toml`

```toml
[tool.pypss]
sample_rate = 0.1       # Sample 10% of calls
max_traces = 5000       # Ring buffer size

# Weights (Must sum to ~1.0)
w_ts = 0.30             # Timing Stability
w_ms = 0.20             # Memory Stability
w_ev = 0.20             # Error Volatility
w_be = 0.15             # Branching Entropy
w_cc = 0.15             # Concurrency Chaos
```

## 🖥️ CLI Usage

`pypss` comes with a powerful CLI to analyze trace files generated by your application.

```bash
# Analyze a saved JSON trace file and output report
pypss analyze --trace-file traces.json --output report.txt

# Fail the command if PSS is below a threshold (great for CI)
pypss analyze --trace-file traces.json --fail-if-below 80
```

## 📜 Historical Trends & Regression Detection

PyPSS can store stability scores over time to help you track long-term trends and detect regressions.

### Usage

1.  **Store History**: Add the `--store-history` flag to your run or analysis.
    ```bash
    pypss run my_app.py --store-history
    pypss analyze --trace-file traces.json --store-history
    ```

2.  **View Trends**: Use the `history` command to see a table of recent runs.
    ```bash
    # Show last 20 runs
    pypss history --limit 20
    
    # Show history for the last 7 days
    pypss history --days 7
    
    # Export to CSV for spreadsheet analysis
    pypss history --days 30 --export csv > stability_report.csv
    ```

3.  **Automated Regression Detection**:
    When `--store-history` is used, PyPSS automatically compares the current PSS against the average of the last 5 runs. If a significant drop (default > 10 points) is detected, it will print a warning:
    > ⚠️ REGRESSION DETECTED: Current PSS (75.0) is significantly lower than the 5-run average (90.0).

### Configuration

Configure storage backends in `pyproject.toml`:

```toml
[tool.pypss]
storage_backend = "sqlite"  # or "prometheus"
storage_uri = "pypss_history.db"  # path to db or pushgateway url
regression_threshold_drop = 10.0
regression_history_limit = 5
```

**Prometheus Support**:
To use Prometheus PushGateway (Push Mode):
```toml
storage_backend = "prometheus"
storage_uri = "localhost:9091"
```

To expose metrics via HTTP server (Pull Mode):
```toml
storage_backend = "prometheus"
storage_mode = "pull"
storage_uri = "8000"  # Port number
```
*Note: Requires `pip install pypss[monitoring]`.*

## 🧩 Integrations

`pypss` provides built-in integrations for popular Python frameworks and tools:

*   **FastAPI**: Easily instrument your FastAPI endpoints.
*   **Flask**: Monitor Flask routes and background tasks.
*   **Celery**: Track the stability of your Celery tasks.
*   **RQ**: Observe the stability of your RQ jobs.
*   **OpenTelemetry**: Export `pypss` traces to OpenTelemetry collectors.

### Pytest Integration

`pypss` includes a powerful pytest plugin to measure the stability of your test suite. It automatically wraps your tests, calculates a PSS score for each test case, and can fail the build if stability drops.

**Usage:**

1.  **Enable PSS monitoring**:
    ```bash
    pytest --pss
    ```

2.  **Generate Stability Scores (Requires multiple runs)**:
    To statistically measure stability (variance), you need multiple data points. Use `pytest-repeat` or simply run the loop:
    ```bash
    pytest --pss --count=10
    ```

3.  **Fail on Instability**:
    Fail the test session if *any* individual test's PSS score drops below a threshold (e.g., 80):
    ```bash
    pytest --pss --count=10 --pss-fail-below 80
    ```

**Sample Output:**
```text
======================= PyPSS Stability Report ========================
Test Node ID                                     | Runs | PSS | Status
-----------------------------------------------------------------------
tests/test_api.py::test_login_latency            | 10   | 98  | ✅ Stable
tests/test_api.py::test_flaky_endpoint           | 10   | 45  | ❌ Unstable
tests/test_utils.py::test_helper                 | 1    | N/A | ⚠️  Need >1 run
================================================================-------
```

## ⚖️ Comparison with Existing Tools

| Tool | Purpose | `pypss` Difference |
| :--- | :--- | :--- |
| `pytest` | Unit/Integration testing | Measures stability *during* tests, not just pass/fail. |
| `timeit`/`cProfile` | Performance measurement (speed) | Measures *consistency* (jitter), not just average speed. |
| `memory-profiler`| Memory usage analysis | Focuses on stability and spikes, not just total allocation. |
| **`pypss`** | **Holistic Stability Scoring** | **Combines timing, memory, errors, and more into a single reliability score.** |

## 📊 Understanding the Metrics

The Python Program Stability Score (PSS) is a composite metric designed to provide a holistic view of a program's runtime stability. The final score is a weighted average of five individual sub-scores, each targeting a different dimension of stability.

| Metric | Code | Description |
| :--- | :---: | :--- |
| **Timing Stability** | `TS` | **Goal:** Measures the consistency and predictability of your code's execution time. <br/> **How it's calculated:** It primarily uses the **Coefficient of Variation (CV)** of latencies. A lower CV means latencies are consistent, resulting in a higher score. It also penalizes high **tail latency** (p95/p50 ratio). |
| **Memory Stability** | `MS` | **Goal:** Measures how consistently the program uses memory. <br/> **How it's calculated:** The score is lowered by high memory fluctuation (standard deviation relative to the median) and is heavily penalized by large, sudden memory spikes (peak memory relative to the median). |
| **Error Volatility** | `EV` | **Goal:** Measures not just the presence of errors, but their frequency and tendency to occur in bursts. <br/> **How it's calculated:** It considers the overall **mean error rate** and uses the **Variance-to-Mean Ratio (VMR)** to penalize bursty, unpredictable errors more than consistent failures. |
| **Branching Entropy**| `BE` | **Goal:** Measures the predictability of the code paths taken at runtime. <br/> **How it's calculated:** This requires `branch_tag`s. It calculates the **Shannon entropy** of the branch tags that are executed. Lower entropy (more predictable paths) results in a higher score. |
| **Concurrency Chaos**| `CC` | **Goal:** Measures stability in concurrent applications by quantifying time spent waiting. <br/> **How it's calculated:** It analyzes the "wait time" (wall time minus CPU time). A high **Coefficient of Variation (CV)** of these wait times indicates inconsistent waiting periods and lowers the score. |

### Final PSS Calculation

1. Each of the five sub-scores is calculated, resulting in a value between 0.0 and 1.0.
2. These scores are combined using configurable weights (e.g., `w_ts`, `w_ms`, etc.) found in your `pyproject.toml` or `pypss.toml`.
3. The final weighted average is normalized and scaled to produce the final PSS score from 0 to 100.

## 🛣️ Future Roadmap



### Distributed Trace Collector



To support large-scale microservices, ETL pipelines, and multi-process applications, we will develop a distributed trace collector. The current in-process collector is not suitable for these environments.



**Key Features:**

*   **Pluggable Collector Backend**: A simple interface to allow users to create their own custom collectors.

*   **Built-in Remote Collectors**:

    *   **Redis-backed collector** for high-throughput, low-latency trace ingestion.

    *   **gRPC trace ingestion** for efficient, cross-language observability.

    *   **File-based FIFO collector** for simple, durable multi-process communication.



Example usage (conceptual):

```python

from pypss.collectors import RedisCollector

global_collector = RedisCollector("redis://localhost:6379/0")

```



### Advanced Dashboard Visualizations



To provide deeper, at-a-glance insights, we plan to enhance the interactive dashboard with more advanced visualizations:



*   **Time-series for All Metrics**: Plot not just Timing Stability, but all five stability scores (TS, MS, EV, BE, CC) over time.

*   **Error Cluster Heatmaps**: Visually identify periods of high error density to pinpoint systemic failures.

*   **Entropy Heatmaps**: Visualize changes in code path predictability (Branching Entropy) over time.

*   **Concurrency Wait-Time Distributions**: Analyze the distribution of wait times to better understand Concurrency Chaos.

*   **Overall PSS Score Trend**: A top-level chart showing how the final PSS score has trended throughout the application's runtime.



### Advanced Async Support



To provide even deeper insights into `asyncio`-based applications, we plan to add:



*   **Async Context Manager**: A native `async with monitor_block()` for instrumenting asynchronous code blocks.

*   **Event Loop Wait-Time Measurement**: More precise metrics on time spent waiting for the event loop.

*   **Task Switching Analysis**: Detect patterns of excessive task switching that could indicate concurrency issues.



### Adaptive Sampling Modes



To make `pypss` even more efficient for production environments, we plan to move beyond static `sample_rate` to intelligent, adaptive sampling. This will reduce overhead during normal operation while increasing precision when anomalies are detected.



**Adaptive Modes:**

*   **High-Load Mode**: Automatically reduce sampling (e.g., to 1%) when QPS (queries per second) is high.

*   **Error-Triggered Mode**: Automatically increase sampling to maximum when error volatility is detected.

*   **Surge Detection**: Trigger burst sampling during sudden performance or memory anomalies.

*   **Low-Noise Mode**: Reduce or temporarily halt sampling when the system is consistently stable, saving resources.



**Conceptual Logic:**

```python

if volatility_score < threshold:

    current_sample_rate = max_rate  # Instability detected, capture everything

else:

    current_sample_rate = min_rate  # System is stable, reduce overhead

```



### Plugin System for Custom Metrics



To transform `pypss` from a library into a true stability analysis framework, we plan to introduce a plugin system. This will allow the community and large engineering teams to extend `pypss` with custom, domain-specific stability metrics.



**Examples of Potential Plugins:**

*   **I/O Stability**: Measure the consistency of disk read/write operations.

*   **Database Roundtrip Stability**: Track the stability of database query times.

*   **Network Jitter Stability**: Analyze the variance in network requests to external services.

*   **Cache Hit Ratio Stability**: Ensure your cache hit rates are predictable.

*   **GPU Memory Spike Stability**: For ML applications, monitor GPU memory for unexpected spikes.

*   **Kafka Consumer Lag Stability**: For streaming applications, track the stability of consumer lag.



**Conceptual API Sketch:**

```python

from pypss.plugins import register_metric, BaseMetric



@register_metric("io_stability")

class IOStabilityMetric(BaseMetric):

    def compute(self, traces):

        # Custom logic to calculate I/O stability score

        ...

        return io_stability_score

```



### Metric Auto-Tuning (AI/Statistical)



To further enhance the accuracy and reduce manual configuration, we envision AI and statistical methods for auto-tuning `pypss` metrics:



*   **Auto-tune Metric Weights**: Dynamically adjust the `w_ts`, `w_ms`, etc., based on observed historical variance and the specific characteristics of your application.

*   **Bayesian Optimization for Thresholds**: Use advanced statistical techniques to automatically find optimal thresholds for alerts and scoring (e.g., `mem_spike_threshold_ratio`).

*   **ML-based Pattern Detection**: In later phases, leverage machine learning to detect subtle, complex instability patterns that are hard to define with static rules.



Example usage (conceptual):

```python

pss = compute_pss(traces, mode="auto_tune")

```



This will increase accuracy and relevance automatically, making `pypss` even smarter.



## 🚨 Alerting Engine



PyPSS includes a powerful alerting engine to proactively monitor your application's stability and notify you of significant changes or regressions.



### Core Concepts



The alerting engine works by:



1.  **Rules**: Logic that evaluates your application's PSS report (and historical data) against predefined thresholds or patterns.

2.  **Alerts**: If a rule is triggered, an `Alert` object is created with details like severity, message, and metric values.

3.  **Channels**: The `Alert`s are then dispatched to configured notification channels (Slack, Microsoft Teams, Prometheus Alertmanager, or generic webhooks).



### Enabling Alerting



To enable the alerting engine, set `alerts_enabled = true` in your ``pypss.toml`` or ``pyproject.toml``:



```toml

[tool.pypss]

alerts_enabled = true

```



### Integrating with CLI



When alerting is enabled, the `pypss run` and `pypss analyze` commands will automatically evaluate rules and send alerts if any are triggered:



```bash

pypss run my_app.py --store-history

pypss analyze --trace-file traces.json

```



### Built-in Alerting Rules



PyPSS comes with several pre-defined rules to detect common stability issues:



*   **Timing Stability Surge**: Detects significant drops in timing consistency.

*   **Memory Stability Spike**: Triggers on sudden or sustained increases in memory volatility.

*   **Error Burst**: Identifies abnormal increases in error rates.

*   **Entropy Anomaly**: Flags unusual changes in code execution paths.

*   **Concurrency Variance Spike**: Alerts on high inconsistency in concurrency-related wait times.

*   **Stability Regression**: Compares the current PSS score against historical averages and alerts on significant drops.



### Notification Channels



You can configure multiple channels to receive alerts:



*   **Slack**: Send formatted messages to Slack channels.

*   **Microsoft Teams**: Dispatch rich message cards to Teams.

*   **Generic Webhook**: Send raw JSON payloads to any endpoint.

*   **Prometheus Alertmanager**: Integrate with your existing Prometheus alerting infrastructure.



See :doc:`advanced_config` for detailed configuration of rules and channels.

To support large-scale microservices, ETL pipelines, and multi-process applications, we will develop a distributed trace collector. The current in-process collector is not suitable for these environments.

**Key Features:**
*   **Pluggable Collector Backend**: A simple interface to allow users to create their own custom collectors.
*   **Built-in Remote Collectors**:
    *   **Redis-backed collector** for high-throughput, low-latency trace ingestion.
    *   **gRPC trace ingestion** for efficient, cross-language observability.
    *   **File-based FIFO collector** for simple, durable multi-process communication.

Example usage (conceptual):
```python
from pypss.collectors import RedisCollector
global_collector = RedisCollector("redis://localhost:6379/0")
```

### Advanced Dashboard Visualizations

To provide deeper, at-a-glance insights, we plan to enhance the interactive dashboard with more advanced visualizations:

*   **Time-series for All Metrics**: Plot not just Timing Stability, but all five stability scores (TS, MS, EV, BE, CC) over time.
*   **Error Cluster Heatmaps**: Visually identify periods of high error density to pinpoint systemic failures.
*   **Entropy Heatmaps**: Visualize changes in code path predictability (Branching Entropy) over time.
*   **Concurrency Wait-Time Distributions**: Analyze the distribution of wait times to better understand Concurrency Chaos.
*   **Overall PSS Score Trend**: A top-level chart showing how the final PSS score has trended throughout the application's runtime.

### Advanced Async Support

To provide even deeper insights into `asyncio`-based applications, we plan to add:

*   **Async Context Manager**: A native `async with monitor_block()` for instrumenting asynchronous code blocks.
*   **Event Loop Wait-Time Measurement**: More precise metrics on time spent waiting for the event loop.
*   **Task Switching Analysis**: Detect patterns of excessive task switching that could indicate concurrency issues.

### Adaptive Sampling Modes

To make `pypss` even more efficient for production environments, we plan to move beyond static `sample_rate` to intelligent, adaptive sampling. This will reduce overhead during normal operation while increasing precision when anomalies are detected.

**Adaptive Modes:**
*   **High-Load Mode**: Automatically reduce sampling (e.g., to 1%) when QPS (queries per second) is high.
*   **Error-Triggered Mode**: Automatically increase sampling to maximum when error volatility is detected.
*   **Surge Detection**: Trigger burst sampling during sudden performance or memory anomalies.
*   **Low-Noise Mode**: Reduce or temporarily halt sampling when the system is consistently stable, saving resources.

**Conceptual Logic:**
```python
if volatility_score < threshold:
    current_sample_rate = max_rate  # Instability detected, capture everything
else:
    current_sample_rate = min_rate  # System is stable, reduce overhead
```

### Plugin System for Custom Metrics

To transform `pypss` from a library into a true stability analysis framework, we plan to introduce a plugin system. This will allow the community and large engineering teams to extend `pypss` with custom, domain-specific stability metrics.

**Examples of Potential Plugins:**
*   **I/O Stability**: Measure the consistency of disk read/write operations.
*   **Database Roundtrip Stability**: Track the stability of database query times.
*   **Network Jitter Stability**: Analyze the variance in network requests to external services.
*   **Cache Hit Ratio Stability**: Ensure your cache hit rates are predictable.
*   **GPU Memory Spike Stability**: For ML applications, monitor GPU memory for unexpected spikes.
*   **Kafka Consumer Lag Stability**: For streaming applications, track the stability of consumer lag.

**Conceptual API Sketch:**
```python
from pypss.plugins import register_metric, BaseMetric

@register_metric("io_stability")
class IOStabilityMetric(BaseMetric):
    def compute(self, traces):
        # Custom logic to calculate I/O stability score
        ...
        return io_stability_score
```

### Metric Auto-Tuning (AI/Statistical)

To further enhance the accuracy and reduce manual configuration, we envision AI and statistical methods for auto-tuning `pypss` metrics:

*   **Auto-tune Metric Weights**: Dynamically adjust the `w_ts`, `w_ms`, etc., based on observed historical variance and the specific characteristics of your application.
*   **Bayesian Optimization for Thresholds**: Use advanced statistical techniques to automatically find optimal thresholds for alerts and scoring (e.g., `mem_spike_threshold_ratio`).
*   **ML-based Pattern Detection**: In later phases, leverage machine learning to detect subtle, complex instability patterns that are hard to define with static rules.

Example usage (conceptual):
```python
pss = compute_pss(traces, mode="auto_tune")
```

This will increase accuracy and relevance automatically, making `pypss` even smarter.

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
