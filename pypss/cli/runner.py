import logging
import sys
import importlib
import inspect
import os
import runpy
from types import ModuleType
from .discovery import CodebaseDiscoverer
from ..instrumentation import monitor_function


class AutoInstrumentor:
    """
    Dynamically imports modules and wraps their functions with the monitor decorator.
    """

    def __init__(self, targets: dict):
        self.targets = targets  # module_name -> [func_names]
        self.instrumented_count = 0

    def apply(self):
        """Attempts to import modules and wrap functions."""
        # Add current directory to sys.path so we can import local modules
        if os.getcwd() not in sys.path:
            sys.path.insert(0, os.getcwd())

        for module_name, functions in self.targets.items():
            # Skip pypss itself to avoid recursion in instrumentation logic
            if module_name.startswith("pypss.") or module_name == "pypss":
                continue

            try:
                # We use safe import. If it fails (e.g., missing dependency), we skip.
                module = importlib.import_module(module_name)
                self._patch_module(module, module_name, functions)
            except ImportError:
                continue
            except Exception:
                continue

    def _patch_module(self, module: ModuleType, module_name: str, functions: list):
        for func_name in functions:
            if not hasattr(module, func_name):
                continue

            original_func = getattr(module, func_name)

            # Ensure it's actually a function/method defined in this module (not an import)
            if not inspect.isroutine(original_func):
                continue

            # Avoid double instrumentation
            if getattr(original_func, "_is_pypss_monitored", False):
                continue

            # Full qualified name for the report
            fqn = f"{module_name}.{func_name}"

            # Apply decorator
            wrapped_func = monitor_function(name=fqn)(original_func)
            wrapped_func._is_pypss_monitored = True

            # Patch the module
            setattr(module, func_name, wrapped_func)
            self.instrumented_count += 1


def run_with_instrumentation(target_script: str, root_dir: str):
    """
    1. Discovers code.
    2. Auto-instruments it.
    3. Runs the target script.
    """
    from ..utils import GLOBAL_CONFIG
    import pypss  # Import pypss to access pypss.init()

    pypss.init()  # Initialize PyPSS components
    logging.basicConfig(level=logging.INFO)
    logging.info(f"Initial max_traces: {GLOBAL_CONFIG.max_traces}")

    print(f"🔍 Scanning {root_dir} for Python modules...")

    # Ensure script directory is in sys.path for imports to work
    script_dir = os.path.dirname(os.path.abspath(target_script))
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)

    discoverer = CodebaseDiscoverer(root_dir)
    targets = discoverer.discover()
    logging.info(f"Discovered targets for instrumentation: {targets.keys()}")

    print(f"🔌 Auto-instrumenting {len(targets)} modules...")
    instrumentor = AutoInstrumentor(targets)
    instrumentor.apply()
    print(f"✅ Instrumented {instrumentor.instrumented_count} functions.")

    print(f"🚀 Launching {target_script}...\n" + "=" * 50)

    # Patch sys.argv so the script sees only itself as argument
    original_argv = sys.argv
    sys.argv = [target_script]

    try:
        # Run the user's script in the current process
        runpy.run_path(target_script, run_name="__main__")
    except Exception as e:
        print(f"\n💥 Application crashed: {e}")
        # We still want to report on what happened before the crash
        pass
    finally:
        sys.argv = original_argv
