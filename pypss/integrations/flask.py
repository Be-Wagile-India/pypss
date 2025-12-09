import time
import threading
from flask import Flask, request
import pypss
from ..utils.trace_utils import get_memory_usage
from ..utils.config import GLOBAL_CONFIG

# Thread-local storage for request-specific metrics
_request_metrics = threading.local()


def init_pypss_flask_app(app: Flask):
    """
    Initializes PyPSS monitoring for a Flask application.
    Call this after creating your Flask app:
    `init_pypss_flask_app(app)`
    """

    @app.before_request
    def before_request_hook():
        _request_metrics.start_wall = time.time()
        _request_metrics.start_cpu = time.process_time()
        _request_metrics.start_mem = get_memory_usage()
        _request_metrics.error_occurred = False

    @app.after_request
    def after_request_hook(response):
        end_wall = time.time()
        end_cpu = time.process_time()
        end_mem = get_memory_usage()

        duration_wall = end_wall - getattr(_request_metrics, "start_wall", end_wall)
        duration_cpu = end_cpu - getattr(_request_metrics, "start_cpu", end_cpu)
        wait_time = max(0.0, duration_wall - duration_cpu)

        trace = {
            "name": f"{GLOBAL_CONFIG.integration_flask_trace_prefix}{request.method} {request.path}",
            "duration": duration_wall,
            "cpu_time": duration_cpu,
            "wait_time": wait_time,
            "memory": end_mem,
            "memory_diff": end_mem - getattr(_request_metrics, "start_mem", end_mem),
            "error": getattr(_request_metrics, "error_occurred", False),
            "timestamp": getattr(_request_metrics, "start_wall", end_wall),
        }

        collector = pypss.get_global_collector()
        if collector:
            collector.add_trace(trace)

        # Add headers
        response.headers[GLOBAL_CONFIG.integration_flask_header_latency] = (
            f"{duration_wall * 1000:.2f}ms"
        )
        response.headers[GLOBAL_CONFIG.integration_flask_header_wait] = (
            f"{wait_time * 1000:.2f}ms"
        )

        return response

    @app.errorhandler(Exception)
    def handle_exception(e):
        _request_metrics.error_occurred = True
        raise e

    return app
