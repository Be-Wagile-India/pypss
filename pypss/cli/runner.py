import importlib
import inspect
import logging
import os
import runpy
import sys
from types import ModuleType

from ..instrumentation import monitor_function
from .discovery import CodebaseDiscoverer


class AutoInstrumentor:
    """
    Dynamically imports modules and wraps their functions with the monitor decorator.
    """

    def __init__(self, targets: dict):
        self.targets = targets
        self.instrumented_count = 0

    def apply(self):
        if os.getcwd() not in sys.path:
            sys.path.insert(0, os.getcwd())

        for module_name, functions in self.targets.items():
            if module_name.startswith("pypss.") or module_name == "pypss":
                continue

            try:
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

            if not inspect.isroutine(original_func):
                continue

            if getattr(original_func, "_is_pypss_monitored", False):
                continue

            fqn = f"{module_name}.{func_name}"

            wrapped_func = monitor_function(name=fqn)(original_func)
            wrapped_func._is_pypss_monitored = True

            setattr(module, func_name, wrapped_func)
            self.instrumented_count += 1


def run_with_instrumentation(target_script: str, root_dir: str):
    """
    1. Discovers code.
    2. Auto-instruments it.
    3. Runs the target script.
    """
    import pypss

    from ..utils import GLOBAL_CONFIG

    pypss.init()
    logging.basicConfig(level=logging.INFO)
    logging.info(f"Initial max_traces: {GLOBAL_CONFIG.max_traces}")

    print(f"🔍 Scanning {root_dir} for Python modules...")

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

    original_argv = sys.argv
    sys.argv = [target_script]

    try:
        runpy.run_path(target_script, run_name="__main__")
    except Exception as e:
        print(f"\n💥 Application crashed: {e}")
        pass
    finally:
        sys.argv = original_argv
