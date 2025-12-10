import sys
import types
from unittest.mock import patch

from pypss.cli.runner import AutoInstrumentor, run_with_instrumentation


class TestRunner:
    def test_auto_instrumentor_patching(self):
        # Create a dummy module in sys.modules
        mod_name = "dummy_module_for_test"
        module = types.ModuleType(mod_name)

        def target_func():
            return 1

        module.target_func = target_func  # type: ignore[attr-defined]
        sys.modules[mod_name] = module

        targets = {mod_name: ["target_func"]}
        instrumentor = AutoInstrumentor(targets)

        # Apply instrumentation
        instrumentor.apply()

        assert instrumentor.instrumented_count == 1

        # Check if patched
        patched_func = module.target_func
        assert getattr(patched_func, "_is_pypss_monitored", False)

        # Clean up
        del sys.modules[mod_name]

    def test_auto_instrumentor_skip_non_routines(self):
        mod_name = "dummy_module_vars"
        module = types.ModuleType(mod_name)
        module.some_var = 123  # type: ignore[attr-defined]
        sys.modules[mod_name] = module

        targets = {mod_name: ["some_var"]}
        instrumentor = AutoInstrumentor(targets)
        instrumentor.apply()

        assert instrumentor.instrumented_count == 0
        del sys.modules[mod_name]

    @patch("pypss.cli.runner.runpy.run_path")
    @patch("pypss.cli.runner.CodebaseDiscoverer")
    @patch("pypss.cli.runner.AutoInstrumentor")
    def test_run_with_instrumentation(self, mock_instr, mock_disc, mock_runpy, tmp_path):
        # Setup mocks
        mock_disc_instance = mock_disc.return_value
        mock_disc_instance.discover.return_value = {"mod": ["func"]}

        mock_instr_instance = mock_instr.return_value
        mock_instr_instance.instrumented_count = 1

        script_path = tmp_path / "script.py"
        script_path.touch()

        run_with_instrumentation(str(script_path), str(tmp_path))

        # Verification
        mock_disc.assert_called_once()
        mock_instr.assert_called_once()
        mock_instr_instance.apply.assert_called_once()
        mock_runpy.assert_called_once_with(str(script_path), run_name="__main__")

        # Check sys.path modification
        assert str(tmp_path) in sys.path
