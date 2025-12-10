Core Concepts
=============

pypss calculates a score based on:

*   **Timing Stability (TS)**
*   **Memory Stability (MS)**
*   **Error Volatility (EV)**
*   **Branching Entropy (BE)**
*   **Concurrency Chaos (CC)**

Simple Instrumentation
======================

Use the ``@monitor_function`` decorator:

.. code-block:: python

    from pypss.instrumentation import monitor_function, global_collector
    from pypss.core import compute_pss_from_traces
    from pypss.reporting import render_report_text
    import time
    import random

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

Context Manager Usage
=====================

For fine-grained control over specific blocks of code:

.. code-block:: python

    from pypss.instrumentation import monitor_block

    def process_data(items):
        with monitor_block("data_processing", branch_tag="batch_start"):
            # ... complex logic ...
            pass

Async Monitoring
================

For modern `asyncio` applications, PyPSS offers dedicated tools:

.. code-block:: python

    from pypss.instrumentation import monitor_async, start_async_monitoring
    import asyncio # Added for async example

    # 1. Enable background loop monitoring (measures lag/jitter)
    start_async_monitoring()

    async def fetch_data():
        # 2. Use the async context manager
        async with monitor_async("fetch_data", branch_tag="network_io"):
            # Example client.get to be replaced
            await asyncio.sleep(0.05) # Simulate IO

    # Example function for monitor_block with async
    async def some_io_operation():
        await asyncio.sleep(0.01)

    async def main_async_example():
        # Use the async context manager for fine-grained tracing
        async with monitor_async("my_async_block", branch_tag="io_wait"):
            await some_io_operation()


**Features:**
*   **Loop Lag**: Automatically tracks event loop latency as a system metric (contributes to Concurrency Chaos).
*   **Yield Counting**: On Python 3.12+, automatically counts task yields/switches to detect concurrency thrashing (zero-overhead).


Distributed Trace Collection
============================

.. versionadded:: 1.1.0

PyPSS includes a robust set of distributed trace collectors designed for high-throughput microservices, multi-process applications, and ETL pipelines. These collectors allow you to offload trace data from the application process to external storage systems or separate processes, ensuring minimal overhead and high durability.

Why Distributed Collection?
---------------------------

The default in-memory collector is perfect for single-process scripts or development. However, in production environments with multiple workers (e.g., Gunicorn, Celery, Kubernetes pods), you need a way to aggregate traces centrally without blocking the main application thread.

Key Features:
*   **Asynchronous Batching**: All distributed collectors inherit from ``ThreadedBatchCollector``, which buffers traces and flushes them in a background thread. This ensures that network I/O or disk writes never block your critical application path.
*   **Load Shedding**: If the internal buffer fills up (e.g., downstream is slow), collectors automatically drop new traces to protect application stability.
*   **Resilience**: Collectors are designed to handle connection failures gracefully without crashing the host application.

Available Collectors
--------------------

Redis Collector
~~~~~~~~~~~~~~~

Push traces to a Redis list using high-performance pipelines. Ideal for high-throughput distributed systems.

**Usage:**

.. code-block:: python

    from pypss.instrumentation import RedisCollector, monitor_function

    # Initialize with your Redis URL
    # Recommended: Set a generous batch size for better throughput
    collector = RedisCollector(
        redis_url="redis://localhost:6379/0",
        key_name="pypss:traces",
        batch_size=500,
        flush_interval=2.0
    )

    # Use explicitly (or set as global_collector if supported by your setup)
    @monitor_function(collector=collector)
    def my_func():
        ...

**Requirements:**
Install with ``pip install pypss[distributed]``.

File FIFO Collector
~~~~~~~~~~~~~~~~~~~

Write traces to a local file (or named pipe) using NDJSON format. This collector uses OS-level advisory locks (``flock``) to ensure safe concurrent writes from multiple processes (e.g., multiprocessing workers).

**Usage:**

.. code-block:: python

    from pypss.instrumentation import FileFIFOCollector

    # Ideal for multi-process applications on a single node
    collector = FileFIFOCollector(
        file_path="/var/log/pypss/traces.jsonl",
        batch_size=100
    )

**Requirements:**
No extra dependencies needed (uses standard library ``fcntl`` on Linux/Unix).

gRPC Collector
~~~~~~~~~~~~~~

Send traces to a remote gRPC server. This is useful for cross-language observability or sending data to a centralized observability agent.

**Usage:**

.. code-block:: python

    from pypss.instrumentation import GRPCCollector

    collector = GRPCCollector(
        target="observability-agent:50051",
        secure=False
    )

**Requirements:**
Install with ``pip install pypss[distributed]``.

Custom Collectors
-----------------

You can implement your own collector by subclassing ``BaseCollector`` or ``ThreadedBatchCollector``.

.. code-block:: python

    from pypss.instrumentation.collectors import ThreadedBatchCollector
    from typing import List, Dict

    class MyCustomCollector(ThreadedBatchCollector):
        def _flush_batch(self, batch: List[Dict]):
            # Implement your custom logic to send batch to S3, Kafka, etc.
            send_to_kafka(batch)

API Reference
-------------

See the :doc:`api` section for detailed class reference.


Using ``branch_tag`` for Deeper Insights
========================================

The ``branch_tag`` parameter is a powerful feature for analyzing different code paths within the same function. For example, you can measure the stability of a cache hit versus a cache miss:

.. code-block:: python

    def get_user_data(user_id):
        if is_cached(user_id):
            with monitor_block("get_user_data", branch_tag="cache_hit"):
                return from_cache(user_id)
        else:
            with monitor_block("get_user_data", branch_tag="cache_miss"):
                return from_database(user_id)