import ast
import os
from typing import Dict, List

from ..core.core import compute_pss_from_traces
from ..utils.config import GLOBAL_CONFIG


class CodebaseDiscoverer:
    """
    Scans a directory for Python files and identifies functions suitable for instrumentation.
    """

    def __init__(self, root_dir: str):
        self.root_dir = os.path.abspath(root_dir)
        self.ignore_dirs = set(GLOBAL_CONFIG.discovery_ignore_dirs)
        self.ignore_modules = set(GLOBAL_CONFIG.discovery_ignore_modules)

    def discover(self) -> Dict[str, List[str]]:
        """
        Returns a mapping of module_name -> list of function_names.
        """
        targets = {}

        for root, dirs, files in os.walk(self.root_dir):
            dirs[:] = [d for d in dirs if d not in self.ignore_dirs]

            for file in files:
                if not file.endswith(GLOBAL_CONFIG.discovery_file_extension):
                    continue

                full_path = os.path.join(root, file)
                module_name = self._path_to_module(full_path)

                if any(ignored in module_name for ignored in self.ignore_modules):
                    continue

                functions = self._extract_functions(full_path)
                if functions:
                    targets[module_name] = functions

        return targets

    def _path_to_module(self, path: str) -> str:
        rel_path = os.path.relpath(path, self.root_dir)
        module_path = os.path.splitext(rel_path)[0]
        return module_path.replace(os.path.sep, ".")

    def _extract_functions(self, file_path: str) -> List[str]:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                tree = ast.parse(f.read())
        except Exception:
            return []

        funcs = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name.startswith(GLOBAL_CONFIG.discovery_ignore_funcs_prefix):
                    continue
                funcs.append(node.name)
        return funcs


def get_module_score_breakdown(traces) -> Dict[str, Dict]:
    module_traces: Dict[str, List] = {}
    for t in traces:
        mod = t.get("module", GLOBAL_CONFIG.discovery_unknown_module_name)
        if mod not in module_traces:
            module_traces[mod] = []
        module_traces[mod].append(t)

    scores = {}
    for mod, t_list in module_traces.items():
        scores[mod] = compute_pss_from_traces(t_list)

    return scores
