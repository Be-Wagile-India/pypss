Usage
=====

Core Concepts
-------------

pypss calculates a score based on:

*   **Timing Stability (TS)**
*   **Memory Stability (MS)**
*   **Error Volatility (EV)**
*   **Branching Entropy (BE)**
*   **Concurrency Chaos (CC)**

Instrumenting Code
------------------

Use the ``@monitor_function`` decorator:

.. code-block:: python

   from pypss.instrumentation import monitor_function

   @monitor_function("my_task")
   def my_task():
       ...

AsyncIO Support
^^^^^^^^^^^^^^^

``monitor_function`` fully supports ``async/await``. It correctly handles coroutines, ensuring accurate duration measurement and error capture.

.. code-block:: python

   @monitor_function("async_api_call")
   async def fetch_data():
       await asyncio.sleep(0.1)
       return "data"

Event Loop Monitoring
"""""""""""""""""""""

For deeper insights into async applications, you can enable background monitoring of the asyncio event loop. This tracks **Loop Lag** (jitter) and contributes to the **Concurrency Chaos** score.

.. code-block:: python

   from pypss.instrumentation import start_async_monitoring, monitor_async

   # 1. Start the background monitor (tracks lag & task churn)
   # Ideally call this at startup
   start_async_monitoring()

   async def main():
       # 2. Use the async context manager for fine-grained tracing
       async with monitor_async("my_async_block", branch_tag="io_wait"):
           await some_io_operation()

Or the context manager:

.. code-block:: python

   from pypss.instrumentation import monitor_block

   with monitor_block("critical_section"):
       ...

Distributed Trace Collection
----------------------------

To support large-scale microservices, ETL pipelines, and multi-process applications, PyPSS offers distributed trace collectors. Instead of storing traces in memory locally, these collectors send traces to a centralized or external location.

**Key Features:**

*   **Pluggable Collector Backend**: A simple interface to allow users to create their own custom collectors.
*   **Built-in Remote Collectors**:

    *   **Redis-backed collector** for high-throughput, low-latency trace ingestion.
    *   **gRPC trace ingestion** for efficient, cross-language observability.
    *   **File-based FIFO collector** for simple, durable multi-process communication.

**Usage Examples:**

To use a distributed collector, you need to set the `global_collector` instance early in your application's lifecycle.

.. code-block:: python

   from pypss.instrumentation.collectors import set_global_collector
   from pypss.instrumentation.collectors import RedisCollector, GRPCCollector, FileFIFOCollector

   # --- Redis-backed Collector ---
   # Requires: pip install pypss[distributed]
   # set_global_collector(RedisCollector("redis://localhost:6379/0"))

   # --- gRPC Collector (server needs to be running) ---
   # Requires: pip install pypss[distributed]
   # set_global_collector(GRPCCollector("localhost:50051"))

   # --- File-based FIFO Collector ---
   # set_global_collector(FileFIFOCollector("/tmp/pypss_traces"))

   # Example: Using RedisCollector
   set_global_collector(RedisCollector("redis://localhost:6379/0"))

   # Now, any instrumented code will send traces to the configured distributed collector
   # ... (your instrumented code) ...

CLI Usage
---------

PyPSS provides several powerful command-line tools:

*   **`pypss analyze`**: Analyze trace files from production logs or test runs.
*   **`pypss history`**: View and manage historical PSS trends.
*   **`pypss tune`**: Auto-tune PSS configuration parameters for optimal fault detection.
*   **`pypss ml-detect`**: Detect anomalous patterns using machine learning.
*   **`pypss board`**: Launch an interactive stability dashboard.

Analyze a trace file:

.. code-block:: bash

   pypss analyze --trace-file traces.json

**Scalability:** The ``analyze`` command uses streaming JSON parsing (via ``ijson``) and O(1) memory algorithms. It can process multi-gigabyte trace files with minimal RAM usage.

AI Diagnosis
------------

Ask an AI model (OpenAI or Ollama) to diagnose root causes of instability from your traces:

.. code-block:: bash

   # Use OpenAI (requires OPENAI_API_KEY env var)
   pypss diagnose --trace-file traces.json

   # Use local Ollama model
   pypss diagnose --trace-file traces.json --provider ollama

Metric Auto-Tuning
------------------

PyPSS can automatically tune its internal parameters (like metric weights and thresholds) to maximize its effectiveness in distinguishing between healthy and faulty application behavior. This process uses advanced **Bayesian Optimization** to efficiently find the best configuration.

.. code-block:: bash

    pypss tune --help

    Usage: pypss tune [OPTIONS]

      Auto-tune PyPSS configuration based on baseline traces.

      This command analyzes your 'healthy' traces, generates synthetic 'faulty'
      traces (latency spikes, memory leaks, error bursts), and finds the best
      parameters to maximize the score difference between them.

    Options:
      --baseline PATH         Path to the JSON trace file containing baseline
                              (healthy) behavior.  [required]
      --output PATH           Path to save the optimized configuration.  [default:
                              pypss_tuned.toml]
      --iterations INTEGER    Number of optimization iterations.  [default: 50]
      --help                  Show this message and exit.

**Example:**

.. code-block:: bash

    # 1. Run your application under normal conditions to get a baseline trace
    pypss run app.py --output baseline_traces.json

    # 2. Run the tuning process
    pypss tune --baseline baseline_traces.json --output my_tuned_config.toml

    # 3. Use the tuned configuration in your pyproject.toml or pypss.toml
    # [tool.pypss]
    # include_config = "my_tuned_config.toml"


ML-based Pattern Detection
--------------------------

Detect subtle, complex instability patterns using machine learning. This feature trains an anomaly detection model on your healthy baseline traces and then uses it to identify unusual behavior in new, unseen traces.

.. code-block:: bash

    pypss ml-detect --help

    Usage: pypss ml-detect [OPTIONS]

      Detects anomalous patterns in target traces using a Machine Learning model
      trained on baseline traces.

    Options:
      --baseline-file PATH      Path to the JSON trace file containing baseline
                                (normal) behavior.  [required]
      --target-file PATH        Path to the JSON trace file containing traces to
                                detect anomalies in.  [required]
      --contamination FLOAT     The proportion of outliers in the baseline dataset.
                                Used by IsolationForest.  [default: 0.1]
      --random-state INTEGER    Random seed for reproducibility of ML model
                                training.  [default: 42]
      --help                    Show this message and exit.

**Example:**

.. code-block:: bash

    # 1. Generate healthy baseline traces
    pypss run app.py --output healthy_traces.json

    # 2. Generate new traces from a potentially problematic run
    pypss run app.py --output new_run_traces.json

    # 3. Detect anomalies in the new traces
    pypss ml-detect --baseline-file healthy_traces.json --target-file new_run_traces.json

Interactive Dashboard
---------------------

Visualize your traces using the web-based dashboard:

.. code-block:: bash

   pypss board traces.json

The dashboard is divided into four main tabs:

Overview
^^^^^^^^

*   **KPI Cards**: Instant view of Overall PSS, Total Traces, Error Rate, and Avg Latency.
*   **Metric Breakdown**: Individual scores for Timing, Memory, Errors, Entropy, and Concurrency.
*   **AI Advisor**: An intelligent system that analyzes your data and provides natural language summaries and recommendations (e.g., "Investigate latency spikes in module X").
*   **Module Performance**: A sortable table showing PSS scores per module. Click on a module to see a dedicated detail view.

Metrics
^^^^^^^

*   **Real-time Stability Trends**: A live, multi-line chart plotting all 5 stability metrics over time. This allows you to correlate drops in stability with specific events (e.g., a memory spike coinciding with an error burst). You can adjust the time window (10s, 1min, 5min, etc.).

Diagnostics
^^^^^^^^^^^

Advanced visualizations for root cause analysis:

*   **Error Cluster Heatmap**: A density map showing *when* (time) and *where* (module) errors are occurring. Dense red spots indicate critical instability bursts.
*   **Logic Complexity Heatmap**: Visualizes Branching Entropy density. Helps identify which parts of your codebase are executing the most complex/unpredictable logic paths.

Performance
^^^^^^^^^^^

Deep dive into execution performance:

*   **Latency Percentiles**: A chart tracking P50 (median), P90 (heavy load), and P99 (worst case) latency over time. A wide gap between P50 and P99 indicates "jitter" or unpredictable performance.
*   **Concurrency Wait Times**: A violin plot comparing **CPU Time** (active execution) vs. **Wait Time** (blocked/sleeping). High wait times are a strong indicator of resource contention, I/O bottlenecks, or thread starvation (Concurrency Chaos).

PSS Configuration
-----------------

PyPSS is configured via ``pypss.toml``. See :doc:`advanced_config` for full details.

Quick example:

.. code-block:: toml

   [pypss]
   sample_rate = 0.1

   [pypss.score]
   # Make error detection more aggressive
   error_spike_threshold = 0.05
   consecutive_error_threshold = 2

   [pypss.ui]
   title = "My Production Stability"

Historical Trends & Regression Detection
----------------------------------------

PyPSS allows you to track the stability score of your application over time, enabling you to detect regressions and view long-term trends.

Enabling History
^^^^^^^^^^^^^^^^

To store the results of a run, use the ``--store-history`` flag:

.. code-block:: bash

   pypss run my_script.py --store-history
   pypss analyze --trace-file traces.json --store-history

Viewing History
^^^^^^^^^^^^^^^

Use the ``history`` command to view past runs:

.. code-block:: bash

   # View last 10 runs
   pypss history

   # View last 7 days
   pypss history --days 7

   # Export to CSV
   pypss history --export csv > history.csv

Automated Regression Detection
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

When ``--store-history`` is used, PyPSS automatically checks if the current run's score is significantly lower than the average of recent runs (default: last 5 runs). If a regression is detected, a warning is printed to the console.

You can tune the sensitivity in your configuration:

.. code-block:: toml

   [tool.pypss]
   regression_threshold_drop = 5.0  # Warn if score drops by more than 5 points
   regression_history_limit = 10    # Compare against last 10 runs