import time
from unittest.mock import MagicMock, patch
import pytest
import pypss


class TestIntegrations:
    @pytest.mark.asyncio
    async def test_fastapi_middleware_logic(self):
        try:
            from pypss.integrations.fastapi import PSSMiddleware
            from starlette.types import ASGIApp
        except ImportError:
            pytest.skip("FastAPI/Starlette not installed")

        pypss.init()
        collector = pypss.get_global_collector()
        # Clear collector
        collector.clear()

        # Mock App and Next
        app = MagicMock(spec=ASGIApp)
        mw = PSSMiddleware(app)

        request = MagicMock()
        request.method = "GET"
        request.url.path = "/test"

        async def call_next(req):
            return MagicMock(headers={})

        # Run middleware
        response = await mw.dispatch(request, call_next)

        # Verify Headers
        assert "X-PSS-Latency" in response.headers
        assert "X-PSS-Wait" in response.headers

        # Verify Trace
        traces = collector.get_traces()
        assert len(traces) == 1
        assert traces[0]["name"] == "GET /test"

    def test_flask_integration_logic(self):
        try:
            from flask import Flask
            from pypss.integrations.flask import init_pypss_flask_app
        except ImportError:
            pytest.skip("Flask not installed")

        pypss.init()
        collector = pypss.get_global_collector()
        collector.clear()

        app = Flask(__name__)
        init_pypss_flask_app(app)

        @app.route("/test")
        def test_route():
            time.sleep(0.01)
            return "ok"

        client = app.test_client()
        resp = client.get("/test")

        assert resp.headers.get("X-PSS-Latency")

        traces = collector.get_traces()
        assert len(traces) == 1
        assert traces[0]["name"] == "flask:GET /test"

    def test_celery_integration_logic(self):
        # Unit test the signal handlers directly
        try:
            # We import the module to get access to the private handlers
            # (or just trigger them if connected, but manual call is safer for unit test)
            import pypss.integrations.celery as celery_int
        except ImportError:
            pytest.skip("Celery deps missing")

        pypss.init()
        collector = pypss.get_global_collector()
        collector.clear()

        # Simulate Task
        task_id = "task-123"
        task = MagicMock()
        task.name = "my_task"

        # 1. Prerun
        celery_int._on_task_prerun(task_id=task_id, task=task)

        # Verify metrics stored
        assert task_id in celery_int._task_metrics

        # 2. Postrun
        time.sleep(0.01)
        celery_int._on_task_postrun(task_id=task_id, task=task, state="SUCCESS")

        traces = collector.get_traces()
        assert len(traces) == 1
        assert traces[0]["name"] == "celery:my_task"
        assert traces[0]["branch_tag"] == "SUCCESS"
        assert task_id not in celery_int._task_metrics

    def test_rq_integration_logic(self):
        try:
            from pypss.integrations.rq import PSSJob
        except ImportError:
            pytest.skip("RQ deps missing")

        pypss.init()
        collector = pypss.get_global_collector()
        collector.clear()

        # Subclass to mock perform
        class MockJob(PSSJob):
            def __init__(self):
                self.func_name = "test_func"
                # Mock internals needed by RQ Job
                self.origin = "default"
                self._id = "job_id"

            def perform(self):
                # Call parent wrapper logic, but we need to mock super().perform()
                # PSSJob.perform calls super().perform().
                # Since PSSJob inherits from rq.job.Job, we can't easily mock super() without complexity.
                # Instead, we just rely on the fact that PSSJob wraps logic.
                # We can try to patch rq.job.Job.perform?
                with patch("rq.job.Job.perform"):
                    return super().perform()

        job = MockJob()
        job.perform()

        traces = collector.get_traces()
        assert len(traces) == 1
        assert traces[0]["name"] == "rq:test_func"
