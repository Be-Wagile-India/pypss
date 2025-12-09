Advanced Configuration
======================

The Python Program Stability Score (PSS) is highly configurable via a centralized ``pypss.toml`` file in your project root. This allows you to tune everything from scoring algorithms to UI colors without touching the code.

Configuration File Structure
----------------------------

The ``pypss.toml`` file uses sections to organize settings.

Core Settings ``[pypss]``
~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 30, 60, 10

   * - Parameter
     - Description
     - Default

   * - ``sample_rate``
     - Fraction of calls to sample (0.0 to 1.0).
     - ``1.0``

   * - ``max_traces``
     - Ring buffer size for storing trace data.
     - ``10000``

   * - ``w_ts``, ``w_ms``, ``w_ev``, ``w_be``, ``w_cc``
     - Weights for the 5 stability pillars. Must sum to approx 1.0. **Can be auto-tuned via `pypss tune`.**
     - (Various)

   * - ``alpha``, ``beta``, ``gamma``, ``delta``
     - Sensitivity coefficients for scoring algorithms. **Can be auto-tuned via `pypss tune`.**
     - (Various)

   * - ``plugins``
     - List of strings specifying external python modules to load as plugins.
     - ``[]``

Metric Auto-Tuning ``[pypss.tuning]``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

While the `pypss tune` command automatically optimizes configuration parameters, you can also manually set initial ranges or values. The tuning process will optimize parameters like ``alpha``, ``beta``, ``gamma``, ``mem_spike_threshold_ratio``, ``concurrency_wait_threshold``, and the individual metric weights (``w_ts``, ``w_ms``, etc.).

When running ``pypss tune``, the output configuration file (e.g., `pypss_tuned.toml`) will contain the optimized values for these parameters.

Adaptive Sampling ``[pypss]``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Settings to control the dynamic adjustment of the sample rate.

.. list-table::
   :header-rows: 1
   :widths: 30, 60, 10

   * - Parameter
     - Description
     - Default

   * - ``adaptive_sampler_mode``
     - Strategy: ``balanced``, ``high_load``, ``error_triggered``, ``surge``, ``low_noise``.
     - ``balanced``

   * - ``adaptive_sampler_high_qps_threshold``
     - Trace QPS threshold to trigger ``high_load`` mode.
     - ``1000.0``

   * - ``adaptive_sampler_low_noise_sample_rate``
     - Sample rate used when ``low_noise`` mode is active.
     - ``0.01``

UI Configuration ``[pypss.ui]``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Customize the dashboard appearance and behavior.

.. code-block:: toml

   [pypss.ui]
   port = 8080
   title = "My Stability Dashboard"

   [pypss.ui.theme]
   primary = "#4285F4"
   secondary = "#607D8B"
   # ... other colors

Dashboard Logic ``[pypss.dashboard]``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Thresholds for visual indicators on the dashboard.

.. code-block:: toml

   [pypss.dashboard]
   critical_pss_threshold = 60.0
   warning_error_rate = 0.05

Background Dumpers ``[pypss.background]``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Control how trace data is persisted to disk.

.. code-block:: toml

   [pypss.background]
   dump_interval = 60
   archive_dir = "archive"

Scoring Tuning ``[pypss.score]``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Fine-tune the mathematical models.

.. code-block:: toml

   [pypss.score]
   latency_tail_percentile = 94
   memory_epsilon = 1e-9
   error_vmr_multiplier = 0.5
   error_spike_impact_multiplier = 0.5
   consecutive_error_decay_multiplier = 2.0

Collector Performance ``[pypss.collector]``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Optimize the in-memory collector for high-concurrency workloads.

.. code-block:: toml

   [pypss.collector]
   max_traces_sharding_threshold = 1000
   shard_count = 16

Advisor Thresholds ``[pypss.advisor]``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Configure when the AI Advisor triggers specific warnings.

.. code-block:: toml

   [pypss.advisor]
   threshold_excellent = 90
   metric_score_critical = 0.6
   # ...

Integrations ``[pypss.integration.*]``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Configure prefixes and headers for various integrations.

.. code-block:: toml

   [pypss.integration.celery]
   trace_prefix = "celery:"

   [pypss.integration.flask]
   trace_prefix = "flask:"
   header_latency = "X-PSS-Latency"

   [pypss.integration.otel]
   metric_prefix = "pypss."

LLM Advisor ``[pypss.llm]``
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Configure the AI backend for the ``diagnose`` command.

.. code-block:: toml

   [pypss.llm]
   openai_model = "gpt-4o"
   ollama_url = "http://localhost:11434/api/generate"

ML-based Pattern Detection ``[pypss.ml]``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Configure the default parameters for the `pypss ml-detect` command.

.. list-table::
   :header-rows: 1
   :widths: 30, 60, 10

   * - Parameter
     - Description
     - Default

   * - ``contamination``
     - The proportion of outliers expected in the baseline dataset. Used by IsolationForest.
     - ``0.1``

   * - ``random_state``
     - Random seed for reproducibility of ML model training.
     - ``42``

Alerting Configuration ``[tool.pypss.alerts]``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Configure alerting behavior, channels, and rule thresholds.

.. code-block:: toml

   [tool.pypss]
   alerts_enabled = true             # Enable or disable the alerting engine
   alerts_cooldown_seconds = 3600    # Cooldown period (in seconds) for suppressing duplicate alerts

   # Webhook Channels
   alerts_slack_webhook = "https://hooks.slack.com/services/..."
   alerts_teams_webhook = "https://outlook.office.com/webhook/..."
   alerts_generic_webhook = "https://your.webhook.site/..."
   alerts_alertmanager_url = "http://localhost:9093/api/v2/alerts" # Prometheus Alertmanager URL

   # Rule Thresholds (Scores are 0.0-1.0 for sub-metrics)
   alert_threshold_ts = 0.70         # Timing Stability score below this triggers an alert
   alert_threshold_ms = 0.70         # Memory Stability score below this triggers an alert
   alert_threshold_ev = 0.80         # Error Volatility score below this triggers an alert
   alert_threshold_be = 0.70         # Branching Entropy score below this triggers an alert
   alert_threshold_cc = 0.70         # Concurrency Chaos score below this triggers an alert

Custom Metrics Configuration ``[pypss.custom_metric_weights]``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Adjust the weight of specific custom plugins in the overall score.

.. code-block:: toml

   [pypss.custom_metric_weights]
   IO = 0.25
   DB = 0.20
   MY_PLUGIN = 0.5

Storage & Monitoring
--------------------

PyPSS supports persisting stability scores to enable long-term trend analysis and integration with monitoring systems.

SQLite (Default)
~~~~~~~~~~~~~~~~

For local development and CI environments, SQLite is the easiest way to track history.

.. code-block:: toml

   [tool.pypss]
   storage_backend = "sqlite"
   storage_uri = "pypss_history.db"
   # Automatically remove records older than 90 days
   retention_days = 90

Prometheus (Production)
~~~~~~~~~~~~~~~~~~~~~~~

PyPSS supports two modes for Prometheus integration:

1.  **Push Mode (Default)**: Pushes metrics to a PushGateway at the end of execution. Ideal for batch jobs or CLI runs.
2.  **Pull Mode**: Starts an HTTP server to expose metrics. Ideal for long-running services.

**Prerequisites:**

1.  Install optional dependencies: ``pip install pypss[monitoring]``

**Configuration:**

.. code-block:: toml

   [tool.pypss]
   storage_backend = "prometheus"

   # Push Mode
   storage_mode = "push"
   storage_uri = "pushgateway.example.com:9091"

   # Pull Mode
   # storage_mode = "pull"
   # storage_uri = "8000"  # Port to listen on

**How it works:**

When you run ``pypss run ... --store-history`` (Push Mode) or initialize the app (Pull Mode), PyPSS exposes/pushes the following metrics:

*   ``pypss_score``: The overall PSS score (0-100).
*   ``pypss_ts``: Timing Stability score.
*   ``pypss_ms``: Memory Stability score.
*   ``pypss_ev``: Error Volatility score.
*   ``pypss_be``: Branching Entropy score.
*   ``pypss_cc``: Concurrency Chaos score.

**Grafana Integration:**

You can then query these metrics in Prometheus (e.g., ``pypss_score{job="pypss"}``) and build dashboards in Grafana.
