Integrations
============

PyPSS can be integrated with various popular Python frameworks and libraries to automatically collect stability metrics.

This section outlines how to set up PyPSS with different integrations.

Celery
------

To instrument Celery tasks with PyPSS, use the ``enable_celery_integration`` function.

.. code-block:: python

   from celery import Celery
   from pypss.integrations.celery import enable_celery_integration

   app = Celery("my_app")

   # Initialize PyPSS integration
   enable_celery_integration()

   @app.task
   def my_celery_task(arg1):
       # Your task logic here
       pass

FastAPI
-------

Integrate PyPSS with FastAPI by adding ``PSSMiddleware``:

.. code-block:: python

   from fastapi import FastAPI
   from pypss.integrations.fastapi import PSSMiddleware

   app = FastAPI()

   # Add PyPSS middleware
   app.add_middleware(PSSMiddleware)

   @app.get("/")
   async def read_root():
       return {"Hello": "World"}

Flask
-----

Use PyPSS with Flask by initializing it with your app instance:

.. code-block:: python

   from flask import Flask
   from pypss.integrations.flask import init_pypss_flask_app

   app = Flask(__name__)

   # Initialize PyPSS integration
   init_pypss_flask_app(app)

   @app.route("/")
   def hello_world():
       return "Hello, World!"

OpenTelemetry (OTel)
--------------------

PyPSS can export its metrics to OpenTelemetry. Ensure you have installed the `otel` optional dependencies (`pip install "pypss[otel]"`).

.. code-block:: python

   from pypss.integrations.otel import enable_otel_integration

   # Initialize PyPSS OTel integration
   # You can pass a specific MeterProvider if needed, otherwise uses global default.
   enable_otel_integration()

RQ (Redis Queue)
----------------

Instrument RQ jobs by using the ``PSSJob`` class:

.. code-block:: python

   from redis import Redis
   from rq import Queue
   from pypss.integrations.rq import PSSJob

   q = Queue(connection=Redis(), job_class=PSSJob)

   # Enqueue jobs as normal
   # q.enqueue(my_func, args)

Pytest Plugin
-------------

PyPSS includes a powerful pytest plugin to measure the stability of your test suite. It automatically wraps your tests, calculates a PSS score for each test case, and can fail the build if stability drops.

Ensure `pypss` is installed in your test environment.

**Basic Usage:**

To run tests and generate stability reports, simply use the `--pss` flag:

.. code-block:: bash

   pytest --pss

**Measuring Stability (Variance):**

To statistically measure stability (variance), you need multiple data points for each test. You can use `pytest-repeat` or simply run a loop:

.. code-block:: bash

   pytest --pss --count=10

**Fail on Instability:**

You can fail the test session if *any* individual test's PSS score drops below a threshold (e.g., 80):

.. code-block:: bash

   pytest --pss --count=10 --pss-fail-below 80

**Distributed Testing Support:**

PyPSS supports distributed test execution (e.g., using `pytest-xdist`). It automatically synchronizes traces from worker processes to the master process to generate the final report.

.. code-block:: bash

   # Run with 4 workers
   pytest --pss --count=10 -n 4