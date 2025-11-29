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

Features:

*   **Overall PSS Gauge**: Instant view of system health.
*   **Metric Breakdown**: Scores for Timing, Memory, Errors, etc.
*   **Latency Trends**: P50/P95/Max latency over time.
*   **Error Analysis**: Click the **Error Rate** box to view a detailed table of all failed traces.
*   **Module Details**: Click on any module in the table to see module-specific metrics.
*   **AI Advisor**: Auto-generated insights and recommendations.

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