.. _installation:

############
Installation
############

Basic Installation
==================

.. code-block:: bash

    pip install pypss

Optional Features
=================

Install only what you need to keep your environment light:

.. code-block:: bash

    # Distributed Collectors (Redis, gRPC, etc.)
    pip install "pypss[distributed]"

    # Web Dashboard
    pip install "pypss[dashboard]"

    # AI Diagnosis (OpenAI/Ollama)
    pip install "pypss[llm]"

    # Prometheus Monitoring
    pip install "pypss[monitoring]"

    # OpenTelemetry Integration
    pip install "pypss[otel]"

Development Installation
========================

.. code-block:: bash

    git clone https://github.com/Be-Wagile-India/pypss.git
    cd pypss
    make install