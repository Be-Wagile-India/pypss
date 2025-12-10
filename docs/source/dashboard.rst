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

Customization & Settings
========================

You can customize the dashboard layout and parameters directly from the UI by clicking the **Settings (Gear Icon)** button in the header.

**Dashboard Builder**
---------------------
The **Dashboard Builder** tab in the settings dialog allows you to:
*   **Reorder Widgets**: Drag and drop widgets to arrange them to your liking.
*   **Resize Widgets**: Adjust the column span (1-12) for each widget.
*   **Add Custom Charts**: Create new charts visualizing any data field in your traces (e.g., specific memory metrics, custom instrumentation keys).
    *   Supported types: Line, Bar, Scatter.
    *   Configurable X and Y axes.

**Parameter Tuning**
--------------------
You can also adjust the PSS calculation weights and sensitivity thresholds in real-time to see how they affect your score. Changes are saved to `pypss.toml`.