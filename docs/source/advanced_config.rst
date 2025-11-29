Advanced Configuration
======================

The Python Program Stability Score (PSS) calculation is highly configurable to adapt to different application characteristics and performance goals. You can tune the PSS algorithm by adjusting parameters defined in the ``PSSConfig`` class, located in ``pypss/utils/config.py``.

Configuration can be done via:

1.  **Environment Variables**: Variables prefixed with ``PYPSS_`` (e.g., ``PYPSS_SAMPLE_RATE``).
2.  **TOML Files**: A ``pypss.toml`` file in the project root, or a ``[tool.pypss]`` section in ``pyproject.toml``.

Key Configuration Parameters:
-----------------------------

.. list-table::
   :header-rows: 1
   :widths: 30, 60, 10

   * - Parameter
     - Description
     - Default Value

   * - ``sample_rate``
     - The fraction of traces to collect (0.01 to 1.0). A value of 1.0 collects all traces, while lower values sample traces to reduce overhead in high-traffic applications.
     - ``1.0``

   * - ``max_traces``
     - The maximum number of traces to keep in the internal ring buffer. This limits memory usage.
     - ``10000``

   * - ``w_ts``
     - Weight for Timing Stability. Higher value means timing consistency is more critical.
     - ``0.30``

   * - ``w_ms``
     - Weight for Memory Stability. Higher value means predictable memory usage is more critical.
     - ``0.20``

   * - ``w_ev``
     - Weight for Error Volatility. Higher value means fewer/less bursty errors are more important.
     - ``0.20``

   * - ``w_be``
     - Weight for Branching Entropy. Higher value means predictable execution paths are more important.
     - ``0.15``

   * - ``w_cc``
     - Weight for Concurrency Chaos. Higher value means low contention and efficient parallel execution is more important.
     - ``0.15``

   * - ``alpha``
     - Sensitivity for Timing Stability variance. Higher values penalize timing variance more strictly.
     - ``2.0``

   * - ``beta``
     - Sensitivity for Timing Stability tail (latency spikes). Higher values penalize latency spikes more strictly.
     - ``1.0``

   * - ``gamma``
     - Sensitivity for Memory Stability. Higher values penalize memory usage fluctuations more strictly.
     - ``2.0``

   * - ``mem_spike_threshold_ratio``
     - Ratio of peak memory usage to median memory usage to detect a significant spike (e.g., 1.5 means peak can be 50% higher than median).
     - ``1.5``

   * - ``delta``
     - Sensitivity for Error Volatility. Higher values penalize bursts of errors more strictly.
     - ``1.0``

   * - ``error_spike_threshold``
     - The error rate threshold (as a decimal, e.g., 0.1 for 10%) that triggers a penalty for Error Volatility.
     - ``0.1``

   * - ``consecutive_error_threshold``
     - The number of consecutive errors that triggers an additional penalty for Error Volatility.
     - ``3``

   * - ``concurrency_wait_threshold``
     - The minimum average wait time (in seconds) considered significant for calculating Concurrency Chaos.
     - ``0.001``

Example ``pypss.toml`` Configuration:

.. code-block:: toml

   # Adjust memory spike sensitivity: penalize peak memory usage if it's
   # more than 20% higher than the median.
   mem_spike_threshold_ratio = 1.2

   # Make error detection more aggressive: penalize if error rate exceeds 5%,
   # and penalize consecutive errors more heavily (threshold of 2).
   error_spike_threshold = 0.05
   consecutive_error_threshold = 2

   # Increase sensitivity to timing variance and latency spikes.
   alpha = 3.0
   beta = 1.5

   # Make Concurrency Chaos score more sensitive to wait times.
   concurrency_wait_threshold = 0.005

   # Set a lower sample rate to reduce overhead for high-traffic apps
   sample_rate = 0.1

   # Limit the trace buffer size
   max_traces = 5000

   # Adjust weights: Make timing stability more important
   w_ts = 0.4
   w_ms = 0.15
   w_ev = 0.15
   w_be = 0.15
   w_cc = 0.15
