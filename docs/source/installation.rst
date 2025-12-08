Installation
============

You can install ``pypss`` directly from source or via pip if it's published.

From Source (Core Package)
--------------------------

To install the core ``pypss`` package from a local source checkout:

.. code-block:: bash

   pip install .

For Development (with Extras)
-----------------------------

To install ``pypss`` with development and dashboard dependencies for local development:

.. code-block:: bash

   pip install -e .[dev,dashboard]

   # or, if you prefer using make:
   # make install

Optional Features
-----------------

PyPSS has optional dependencies for specific features. Install them as needed:

*   **Dashboard**: To use the web dashboard.

    .. code-block:: bash

       pip install "pypss[dashboard]"

*   **LLM Diagnosis**: To use OpenAI/Anthropic/Ollama for root cause analysis.

    .. code-block:: bash

       pip install "pypss[llm]"

*   **OpenTelemetry**: To integrate with OTel SDKs.

    .. code-block:: bash

       pip install "pypss[otel]"

*   **Distributed Collectors**: To use Redis or gRPC trace collectors.

    .. code-block:: bash

       pip install "pypss[distributed]"

*   **Monitoring**: To use Prometheus metrics exporter (PushGateway or Pull Mode).

    .. code-block:: bash

       pip install "pypss[monitoring]"