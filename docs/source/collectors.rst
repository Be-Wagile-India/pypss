Distributed Trace Collectors
============================

.. versionadded:: 1.1.0

PyPSS includes a robust set of distributed trace collectors designed for high-throughput microservices, multi-process applications, and ETL pipelines. These collectors allow you to offload trace data from the application process to external storage systems or separate processes, ensuring minimal overhead and high durability.

Why Distributed Collection?
---------------------------

The default in-memory collector is perfect for single-process scripts or development. However, in production environments with multiple workers (e.g., Gunicorn, Celery, Kubernetes pods), you need a way to aggregate traces centrally without blocking the main application thread.

Key Features:
* **Asynchronous Batching**: All distributed collectors inherit from ``ThreadedBatchCollector``, which buffers traces and flushes them in a background thread. This ensures that network I/O or disk writes never block your critical application path.
* **Load Shedding**: If the internal buffer fills up (e.g., downstream is slow), collectors automatically drop new traces to protect application stability.
* **Resilience**: Collectors are designed to handle connection failures gracefully without crashing the host application.

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
