.. _adaptive_sampling:

#########################
Adaptive Sampling Modes
#########################

PyPSS supports adaptive sampling to balance observability depth with runtime overhead. By default, it uses a **Balanced** mode, but you can configure specialized behaviors.

Configure via ``pypss.toml``:

.. code-block:: toml

    [tool.pypss]
    adaptive_sampler_mode = "high_load"  # Choose your mode
    adaptive_sampler_high_qps_threshold = 1000.0

.. list-table::
   :widths: 15 30 55
   :header-rows: 1

   * - Mode
     - Behavior
     - Use Case
   * - **balanced** (Default)
     - Increases sampling on errors/lag, decreases when stable.
     - General purpose monitoring.
   * - **high_load**
     - Drops sampling rate to minimum when QPS exceeds threshold.
     - Protecting high-traffic production endpoints.
   * - **error_triggered**
     - Instantly maximizes sampling when error rate spikes.
     - Debugging crash loops or unstable releases.
   * - **surge**
     - Maximizes sampling during high latency (lag) events.
     - Investigating performance regressions.
   * - **low_noise**
     - Aggressively reduces sampling when system is stable.
     - Cost-saving for stable, long-running services.