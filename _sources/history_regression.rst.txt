.. _history_regression:

###########
Historical Trends & Regression Detection
###########

PyPSS can store stability scores over time to help you track long-term trends and detect regressions.

Usage
=====

1.  **Store History**: Add the ``--store-history`` flag to your run or analysis.
    
    .. code-block:: bash

        pypss run my_app.py --store-history
        pypss analyze --trace-file traces.json --store-history

2.  **View Trends**: Use the ``history`` command to see a table of recent runs.
    
    .. code-block:: bash

        # Show last 20 runs
        pypss history --limit 20
        
        # Show history for the last 7 days
        pypss history --days 7
        
        # Export to CSV for spreadsheet analysis
        pypss history --days 30 --export csv > stability_report.csv

3.  **Automated Regression Detection**:
    When ``--store-history`` is used, PyPSS automatically compares the current PSS against the average of the last 5 runs. If a significant drop (default > 10 points) is detected, it will print a warning:
    
    .. code-block:: text

        ⚠️ REGRESSION DETECTED: Current PSS (75.0) is significantly lower than the 5-run average (90.0).

Configuration
=============

Configure storage backends in ``pyproject.toml``:

.. code-block:: toml

    [tool.pypss]
    storage_backend = "sqlite"  # or "prometheus"
    storage_uri = "pypss_history.db"  # path to db or pushgateway url
    regression_threshold_drop = 10.0
    regression_history_limit = 5

**Prometheus Support**:
To use Prometheus PushGateway (Push Mode):
.. code-block:: toml

    storage_backend = "prometheus"
    storage_uri = "localhost:9091"

To expose metrics via HTTP server (Pull Mode):
.. code-block:: toml

    storage_backend = "prometheus"
    storage_mode = "pull"
    storage_uri = "8000"  # Port number

*Note: Requires ``pip install pypss[monitoring]``.*