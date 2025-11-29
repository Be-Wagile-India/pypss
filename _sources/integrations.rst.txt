Integrations
============

PyPSS can be integrated with various popular Python frameworks and libraries to automatically collect stability metrics.

This section outlines how to set up PyPSS with different integrations.

Celery
------

To instrument Celery tasks with PyPSS:

.. code-block:: python

   from pypss.instrumentation import monitor_function
   from pypss.integrations.celery import PyPssCeleryIntegration

   # Initialize PyPSS integration (e.g., in your Celery app setup)
   PyPssCeleryIntegration.init()

   @monitor_function("my_celery_task", module_name="celery_worker")
   def my_celery_task(arg1, arg2):
       # Your task logic here
       pass

FastAPI
-------

Integrate PyPSS with FastAPI by adding it as middleware:

.. code-block:: python

   from fastapi import FastAPI
   from pypss.integrations.fastapi import PyPssFastAPIMiddleware
   from pypss.instrumentation import monitor_function

   app = FastAPI()

   # Add PyPSS middleware
   app.add_middleware(PyPssFastAPIMiddleware)

   @app.get("/")
   @monitor_function("root_endpoint", module_name="api_gateway")
   async def read_root():
       return {"Hello": "World"}

Flask
-----

Use PyPSS with Flask by adding it as a Flask extension or using decorators:

.. code-block:: python

   from flask import Flask
   from pypss.integrations.flask import PyPssFlaskIntegration
   from pypss.instrumentation import monitor_function

   app = Flask(__name__)

   # Initialize PyPSS integration with Flask app
   PyPssFlaskIntegration.init(app)

   @app.route("/")
   @monitor_function("root_route", module_name="web_framework")
   def hello_world():
       return "Hello, World!"

OpenTelemetry (OTel)
--------------------

PyPSS can leverage OpenTelemetry for trace collection. Ensure you have installed the `otel` optional dependencies (`pip install "pypss[otel]"`).

.. code-block:: python

   from pypss.integrations.otel import PyPssOtelIntegration
   from pypss.instrumentation import monitor_function

   # Initialize OpenTelemetry and then PyPSS OTel integration
   PyPssOtelIntegration.init()

   @monitor_function("otel_instrumented_function", module_name="otel_integration")
   def my_otel_function():
       pass

RQ (Redis Queue)
----------------

Instrument RQ workers and jobs:

.. code-block:: python

   from pypss.instrumentation import monitor_function
   from pypss.integrations.rq import PyPssRQIntegration

   # Initialize PyPSS integration for RQ
   PyPssRQIntegration.init()

   @monitor_function("my_rq_job", module_name="rq_worker")
   def my_rq_job(data):
       # Your job logic
       pass

Pytest Plugin
-------------

PyPSS includes a pytest plugin to automatically capture stability metrics during your test runs.

Ensure `pypss` is installed with its dev dependencies, including pytest (`pip install -e .[dev]`).

Your ``pytest.ini`` or ``pyproject.toml`` might need to be configured to load the plugin, although it is often discovered automatically.

Example test function:

.. code-block:: python

   from pypss.instrumentation import monitor_function

   @monitor_function("test_stability", module_name="tests")
   def test_that_code_is_stable():
       assert True

To run tests and generate stability reports:

.. code-block:: bash

   pytest --pypss-report=stability_report.json

PyPSS will collect stability data during the test execution and save it to the specified file.
