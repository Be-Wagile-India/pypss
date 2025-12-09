.. _dashboard:

###########
Interactive Dashboard
###########

`pypss` includes a real-time interactive dashboard to visualize stability metrics and traces.

To use the dashboard, first install the optional dependencies:
.. code-block:: bash

    pip install "pypss[dashboard]"

Then, run the `board` command with your trace file:
.. code-block:: bash

    pypss board traces.json

Dashboard Features
==================

*   **Overview Tab**:
    *   **Real-time KPIs**: Instant gauges for Overall PSS, Error Rate, and Throughput.
    *   **AI Advisor**: Automated root cause analysis and actionable recommendations.
    *   **Module Breakdown**: Drill down into specific modules to find the weakest link.
*   **Metrics Tab**:
    *   **Real-time Trends**: Live line charts showing the evolution of all 5 stability metrics (TS, MS, EV, BE, CC) over time.
*   **Diagnostics Tab**:
    *   **Error Heatmap**: Visualize *when* and *where* error bursts are happening across your system.
    *   **Complexity Heatmap**: Identify "hot spots" of high branching entropy (logic complexity).
*   **Performance Tab**:
    *   **Latency Percentiles**: Detailed P50, P90, and P99 latency tracking.
    *   **Concurrency Analysis**: Violin plots comparing CPU time vs. Wait time to detect resource contention.