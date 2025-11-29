import time
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from ..instrumentation import global_collector, get_memory_usage
from ..utils.config import GLOBAL_CONFIG


class PSSMiddleware(BaseHTTPMiddleware):
    """
    FastAPI/Starlette Middleware to measure request stability.
    Adds X-PSS-Score header to responses.
    """

    def __init__(self, app: ASGIApp, sample_rate: float = 1.0):
        super().__init__(app)
        self.sample_rate = sample_rate

    async def dispatch(self, request, call_next):
        # Start Metrics
        start_wall = time.time()
        start_cpu = time.process_time()
        start_mem = get_memory_usage()

        try:
            response = await call_next(request)
            error = False
        except Exception as e:
            error = True
            raise e
        finally:
            # End Metrics
            end_wall = time.time()
            end_cpu = time.process_time()
            end_mem = get_memory_usage()

            duration_wall = end_wall - start_wall
            duration_cpu = end_cpu - start_cpu
            wait_time = max(0.0, duration_wall - duration_cpu)

            trace = {
                "name": f"{request.method} {request.url.path}",
                "duration": duration_wall,
                "cpu_time": duration_cpu,
                "wait_time": wait_time,
                "memory": end_mem,
                "memory_diff": end_mem - start_mem,
                "error": error,
                "timestamp": start_wall,
            }

            # Add to global collector for aggregate reporting
            global_collector.add_trace(trace)

            # Compute single-request score (micro-PSS)
            # Note: PSS is statistical, so score of 1 request is usually 100 unless error/slow
            # But over time, this header becomes useful.
            # For a single request, we can't compute variance, so we return a simple status.
            pass

        # Inject headers if response exists
        if "response" in locals():
            # We can't easily compute full PSS for 1 request, but we can show latency
            response.headers[GLOBAL_CONFIG.header_pss_latency] = (
                f"{duration_wall * 1000:.2f}ms"
            )
            response.headers[GLOBAL_CONFIG.header_pss_wait] = (
                f"{wait_time * 1000:.2f}ms"
            )

        return response
