import pypss
import pypss.core
import pypss.instrumentation
import pypss.integrations
import pypss.utils
import pypss.cli


def test_root_exports():
    # Test __init__.py itself

    assert hasattr(pypss, "__all__")

    assert "monitor_function" in pypss.__all__

    assert pypss.monitor_function is not None

    assert pypss.compute_pss_from_traces is not None

    assert pypss.GLOBAL_CONFIG is not None


def test_core_exports():
    assert hasattr(pypss.core, "__all__")

    assert "StabilityAdvisor" in pypss.core.__all__

    assert pypss.core.StabilityAdvisor is not None

    assert pypss.core.generate_advisor_report is not None

    assert pypss.core.compute_pss_from_traces is not None


def test_instrumentation_exports():
    assert hasattr(pypss.instrumentation, "__all__")

    assert "Collector" in pypss.instrumentation.__all__

    assert pypss.instrumentation.Collector is not None


def test_integrations_exports():
    assert hasattr(pypss.integrations, "__all__")

    # These might be None if deps missing, but the symbols should exist in __all__

    assert "PSSMiddleware" in pypss.integrations.__all__

    assert "enable_celery_integration" in pypss.integrations.__all__

    assert "PSSJob" in pypss.integrations.__all__

    assert "init_pypss_flask_app" in pypss.integrations.__all__

    assert "enable_otel_integration" in pypss.integrations.__all__


def test_utils_exports():
    assert hasattr(pypss.utils, "__all__")

    assert "calculate_cv" in pypss.utils.__all__

    assert pypss.utils.calculate_cv is not None

    assert pypss.utils.PSSConfig is not None

    assert pypss.utils.GLOBAL_CONFIG is not None


def test_cli_exports():
    assert hasattr(pypss.cli, "__all__")

    assert "main" in pypss.cli.__all__

    assert pypss.cli.main is not None
