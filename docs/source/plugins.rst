.. _plugins:

###########
Plugin System & Extensions
###########

PyPSS now features a powerful plugin system allowing you to add custom stability metrics or use built-in specialized ones.

**Built-in Plugins:**
*   **IO Stability (``IO``)**: Consistent disk I/O.
*   **Database Stability (``DB``)**: Stable DB query times.
*   **GC Stability (``GC``)**: Predictable garbage collection.
*   **Thread Starvation (``STARVE``)**: Low system lag.
*   **Network Stability (``NET``)**: Consistent network latency.
*   **Kafka Lag Stability (``KAFKA``)**: Predictable consumer lag.
*   **GPU Memory Stability (``GPU``)**: Stable GPU memory usage.

Loading Plugins
===============

Enable plugins in your configuration:

.. code-block:: toml

    [pypss]
    plugins = ["my_custom.metrics", "pypss.plugins.custom_metric"]

See the `documentation <https://pypss.readthedocs.io/en/latest/plugins.html>`_ for how to write your own!