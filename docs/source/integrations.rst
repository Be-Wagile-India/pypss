.. _integrations:

###########
Integrations
###########

`pypss` provides built-in integrations for popular Python frameworks and tools:

*   **FastAPI**: Easily instrument your FastAPI endpoints.
*   **Flask**: Monitor Flask routes and background tasks.
*   **Celery**: Track the stability of your Celery tasks.
*   **RQ**: Observe the stability of your RQ jobs.
*   **OpenTelemetry**: Export `pypss` traces to OpenTelemetry collectors.

Pytest Integration
==================

`pypss` includes a powerful pytest plugin to measure the stability of your test suite. It automatically wraps your tests, calculates a PSS score for each test case, and can fail the build if stability drops.

Usage
=====

1.  **Enable PSS monitoring**:
    
    .. code-block:: bash

        pytest --pss

2.  **Generate Stability Scores (Requires multiple runs)**:
    To statistically measure stability (variance), you need multiple data points. Use ``pytest-repeat`` or simply run the loop:
    
    .. code-block:: bash

        pytest --pss --count=10

3.  **Fail on Instability**:
    Fail the test session if *any* individual test's PSS score drops below a threshold (e.g., 80):
    
    .. code-block:: bash

        pytest --pss --count=10 --pss-fail-below 80

Sample Output:
==============

.. code-block:: text

    ======================= PyPSS Stability Report ========================
    Test Node ID                                     | Runs | PSS | Status
    -----------------------------------------------------------------------
    tests/test_api.py::test_login_latency            | 10   | 98  | ✅ Stable
    tests/test_api.py::test_flaky_endpoint           | 10   | 45  | ❌ Unstable
    tests/test_utils.py::test_helper                 | 1    | N/A | ⚠️  Need >1 run
    ================================================================-------