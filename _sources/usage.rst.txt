Usage
=====

Core Concepts
-------------

pypss calculates a score based on:

*   **Timing Stability (TS)**
*   **Memory Stability (MS)**
*   **Error Volatility (EV)**
*   **Branching Entropy (BE)**

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

**Note:** For async functions, the **Concurrency Chaos** metric is calculated based on the variance of the total wall-clock time (latency), rather than CPU vs Wait time, to accurately reflect event loop contention and I/O delays.

Or the context manager:

.. code-block:: python

   from pypss.instrumentation import monitor_block

   with monitor_block("critical_section"):
       ...

CLI Usage
---------

Analyze a trace file:

.. code-block:: bash

   pypss analyze traces.json

**Scalability:** The ``analyze`` command uses streaming JSON parsing (via ``ijson``) and O(1) memory algorithms. It can process multi-gigabyte trace files with minimal RAM usage.

Interactive Dashboard
---------------------

Visualize your traces using the web-based dashboard:

.. code-block:: bash

   pypss board traces.json

Features:

*   **Overall PSS Gauge**: Instant view of system health.
*   **Metric Breakdown**: Scores for Timing, Memory, Errors, etc.
*   **Latency Trends**: P50/P95/Max latency over time.
*   **Error Analysis**: Click the **Error Rate** box to view a detailed table of all failed traces, including error messages and timestamps.
*   **Module Details**: Click on any module in the table to see module-specific metrics and trends.
*   **AI Advisor**: Auto-generated insights and recommendations based on your data.

PSS Configuration
-----------------

The Python Program Stability Score (PSS) calculation can be fine-tuned using various parameters defined in the ``PSSConfig`` class within ``pypss/utils/config.py``. These parameters can be overridden by creating a ``pypss.toml`` file in your project root or by adding a ``[tool.pypss]`` section to your ``pyproject.toml``.

Here are the key configuration parameters and their impact on the PSS:

*   **`mem_spike_threshold_ratio`**:
    *   **Description**: This parameter (default: 1.5) defines the ratio by which peak memory usage can exceed the median memory usage before an additional penalty is applied to the Memory Stability (MS) score. For example, a value of 1.5 means that if peak memory is more than 50% higher than median memory, the MS score will be negatively affected.
    *   **Impact**: A lower `mem_spike_threshold_ratio` makes the MS score more sensitive to sudden memory consumption spikes, helping to detect potential memory leaks or inefficient memory usage patterns more aggressively.

*   **`error_spike_threshold`**:
    *   **Description**: This parameter (default: 0.1) sets a threshold for the mean error rate (e.g., 0.1 means 10% error rate). If the observed mean error rate exceeds this threshold, an additional penalty is applied to the Error Volatility (EV) score.
    *   **Impact**: A lower `error_spike_threshold` makes the EV score more sensitive to sudden increases in error rates, allowing for earlier detection of system instability or outages.

*   **`consecutive_error_threshold`**:
    *   **Description**: This integer parameter (default: 3) specifies the number of consecutive errors that must occur to trigger an additional, more aggressive penalty to the Error Volatility (EV) score.
    *   **Impact**: This parameter helps in identifying sustained failure conditions, which are often stronger indicators of a severe outage than isolated errors. A lower threshold will penalize shorter sequences of consecutive errors more heavily.

*   **`concurrency_wait_threshold`**:
    *   **Description**: This parameter (default: 0.001 seconds) sets the minimum mean wait time for concurrency chaos calculation. Wait times below this threshold are considered negligible and do not contribute to concurrency chaos.
    *   **Impact**: Adjusting this threshold allows you to focus the Concurrency Chaos (CC) score on more significant contention issues, ignoring very short, potentially insignificant wait times.

Example ``pypss.toml`` configuration:

.. code-block:: toml

   [pypss]
   # Adjust memory spike sensitivity
   mem_spike_threshold_ratio = 1.2

   # Make error detection more aggressive
   error_spike_threshold = 0.05
   consecutive_error_threshold = 2

   # Adjust concurrency sensitivity
   concurrency_wait_threshold = 0.005

