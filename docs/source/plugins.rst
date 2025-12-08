Plugin System
=============

PyPSS features a robust plugin system that allows you to extend its functionality by adding custom stability metrics. This is particularly useful for monitoring domain-specific behaviors, such as business logic consistency, specific hardware metrics (like GPU), or external system interactions (like Kafka or specialized databases).

.. contents:: Table of Contents
    :local:
    :depth: 2

Built-in Plugins
----------------

PyPSS comes with several powerful built-in plugins that are ready to use.

**Core System Plugins:**

*   **IO Stability (`IO`)**: Measures the consistency of disk I/O wait times.
*   **Database Stability (`DB`)**: Tracks the stability of database query durations.
*   **GC Stability (`GC`)**: Monitors Garbage Collection pauses and memory deallocation consistency.
*   **Thread Starvation (`STARVE`)**: Detects thread starvation by analyzing system lag metrics.
*   **Network Jitter Stability (`NET`)**: Analyzes variance in network request latencies.
*   **Cache Stability (`CACHE`)**: Tracks the consistency of cache hit ratios.

**Integration Plugins:**

*   **Kafka Consumer Lag (`KAFKA`)**: Measures stability of Kafka consumer lag (requires `pypss.integrations.kafka.report_kafka_lag`).
*   **GPU Memory Stability (`GPU`)**: Monitors GPU memory usage for spikes (requires `pypss.instrumentation.gpu.start_gpu_monitoring`).

Using Plugins
-------------

To use plugins, you simply need to ensure they are registered. Built-in plugins are registered automatically.

For custom external plugins, you can specify them in your `pypss.toml` configuration file to be loaded at runtime.

**Configuration (`pypss.toml`):**

.. code-block:: toml

    [pypss]
    # List of python modules to import that contain your plugins
    plugins = [
        "my_project.plugins.my_custom_metric",
        "another_package.metrics"
    ]

    # Optional: Override weights for specific metrics
    [pypss.custom_metric_weights]
    IO = 0.25
    MY_METRIC = 0.5

Writing a Custom Plugin
-----------------------

Creating a custom metric is straightforward. You need to subclass `pypss.plugins.BaseMetric` and implement the `compute` method.

1.  **Create your metric class:**

    .. code-block:: python

        # my_project/plugins/my_custom_metric.py
        from typing import Iterable, Dict
        from pypss.plugins import BaseMetric, MetricRegistry

        class MyCustomMetric(BaseMetric):
            """
            A custom metric to measure the stability of 'foobar' operations.
            """
            code = "FOO"  # Unique code for the metric (used in reports)
            name = "Foobar Stability"
            default_weight = 0.15

            def compute(self, traces: Iterable[Dict]) -> float:
                # Filter relevant traces
                relevant_values = []
                for t in traces:
                    if "foobar" in t.get("name", ""):
                        relevant_values.append(t.get("duration", 0))
                
                if not relevant_values:
                    return 1.0  # Return 1.0 (stable) if no data
                
                # Implement your scoring logic (0.0 to 1.0)
                # Example: Simple threshold
                avg = sum(relevant_values) / len(relevant_values)
                if avg > 0.5:
                    return 0.5
                return 1.0

        # Automatically register the metric when the module is imported
        MetricRegistry.register(MyCustomMetric)

2.  **Configure PyPSS to load it:**

    Add `my_project.plugins.my_custom_metric` to the `plugins` list in `pypss.toml`.

3.  **Run PyPSS:**

    When you run `pypss run` or `pypss analyze`, your plugin will be loaded, its `compute` method will be called with the traces, and its score will be included in the final PSS report.

API Reference
-------------

.. autoclass:: pypss.plugins.base.BaseMetric
    :members:
    :undoc-members:
    :show-inheritance:

.. autoclass:: pypss.plugins.registry.MetricRegistry
    :members:
    :undoc-members:
