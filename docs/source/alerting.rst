.. _alerting:

#################
Alerting Engine
#################

PyPSS includes a powerful alerting engine to proactively monitor your application's stability and notify you of significant changes or regressions.

Configuration
=============

Alerts are configured in your `pypss.toml` file under the `[tool.pypss]` section.

.. code-block:: toml

    [tool.pypss]
    alerts_enabled = true
    alerts_slack_webhook = "https://hooks.slack.com/..."
    alerts_teams_webhook = "https://outlook.office.com/..."
    alerts_generic_webhook = "https://example.com/webhook"
    alerts_alertmanager_url = "http://localhost:9093"
    alerts_cooldown_seconds = 3600

Standard Rules
==============

The engine comes with built-in rules that monitor the core stability pillars:

*   **Timing Stability Surge**: Triggered when timing stability drops below `alert_threshold_ts`.
*   **Memory Stability Spike**: Triggered when memory stability drops below `alert_threshold_ms`.
*   **Error Burst**: Triggered when error volatility drops below `alert_threshold_ev`.
*   **Entropy Anomaly**: Triggered when branching entropy drops below `alert_threshold_be`.
*   **Concurrency Variance**: Triggered when concurrency chaos score drops below `alert_threshold_cc`.
*   **Stability Regression**: Triggered when the overall PSS score drops significantly compared to historical average.

Custom Alert Rules
==================

You can define sophisticated, user-specific alert rules via the **Settings > Alert Rules** tab in the Dashboard, or manually in `pypss.toml`.

**Features:**
*   **Multi-condition Logic**: Combine multiple checks (e.g., `PSS < 80` AND `Error Rate > 5%`).
*   **Module Targeting**: Apply rules only to specific modules using Regex patterns (e.g., `^service_auth.*`).
*   **Severity Levels**: Assign `info`, `warning`, or `critical` severity.

**Example Configuration (UI generated):**

.. code-block:: toml

    [[tool.pypss.custom_alert_rules]]
    name = "Critical Auth Service Failure"
    severity = "critical"
    module_pattern = "^auth_service"
    
    [[tool.pypss.custom_alert_rules.conditions]]
    metric = "pss"
    operator = "<"
    value = 70.0

    [[tool.pypss.custom_alert_rules.conditions]]
    metric = "error_volatility"
    operator = "<"
    value = 0.6