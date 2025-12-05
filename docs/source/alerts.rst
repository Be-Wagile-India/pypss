Alerting Engine
===============

PyPSS includes a powerful alerting engine to proactively monitor your application's stability and notify you of significant changes or regressions.

Core Concepts
-------------

The alerting engine works by:

1.  **Rules**: Logic that evaluates your application's PSS report (and historical data) against predefined thresholds or patterns.
2.  **Alerts**: If a rule is triggered, an `Alert` object is created with details like severity, message, and metric values.
3.  **Channels**: The `Alert`s are then dispatched to configured notification channels (Slack, Microsoft Teams, Prometheus Alertmanager, or generic webhooks).

Enabling Alerting
-----------------

To enable the alerting engine, set `alerts_enabled = true` in your ``pypss.toml`` or ``pyproject.toml``:

.. code-block:: toml

   [tool.pypss]
   alerts_enabled = true

Integrating with CLI
--------------------

When alerting is enabled, the `pypss run` and `pypss analyze` commands will automatically evaluate rules and send alerts if any are triggered:

.. code-block:: bash

   pypss run my_app.py --store-history
   pypss analyze --trace-file traces.json

Built-in Alerting Rules
-----------------------

PyPSS comes with several pre-defined rules to detect common stability issues:

*   **Timing Stability Surge**: Detects significant drops in timing consistency.
*   **Memory Stability Spike**: Triggers on sudden or sustained increases in memory volatility.
*   **Error Burst**: Identifies abnormal increases in error rates.
*   **Entropy Anomaly**: Flags unusual changes in code execution paths.
*   **Concurrency Variance Spike**: Alerts on high inconsistency in concurrency-related wait times.
*   **Stability Regression**: Compares the current PSS score against historical averages and alerts on significant drops.

Notification Channels
---------------------

You can configure multiple channels to receive alerts:

*   **Slack**: Send formatted messages to Slack channels.
*   **Microsoft Teams**: Dispatch rich message cards to Teams.
*   **Generic Webhook**: Send raw JSON payloads to any endpoint.
*   **Prometheus Alertmanager**: Integrate with your existing Prometheus alerting infrastructure.

See :doc:`advanced_config` for detailed configuration of rules and channels.
