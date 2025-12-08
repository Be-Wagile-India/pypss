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

Analyze a trace file:

.. code-block:: bash

   pypss analyze --trace-file traces.json

**Scalability:** The ``analyze`` command uses streaming JSON parsing (via ``ijson``) and O(1) memory algorithms. It can process multi-gigabyte trace files with minimal RAM usage.

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