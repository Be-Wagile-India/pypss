from unittest.mock import patch
from pypss.cli.discovery import CodebaseDiscoverer, get_module_score_breakdown


class TestDiscovery:
    def test_discovery_ignores(self, tmp_path):
        # Create structure
        # /root
        #   main.py
        #   ignored_folder/
        #     ignored.py
        #   .venv/
        #     lib.py

        (tmp_path / "main.py").write_text("def foo(): pass")

        ignored_dir = tmp_path / "ignored_folder"
        ignored_dir.mkdir()
        (ignored_dir / "ignored.py").write_text("def bar(): pass")

        venv_dir = tmp_path / ".venv"
        venv_dir.mkdir()
        (venv_dir / "lib.py").write_text("def baz(): pass")

        # Test with custom ignore by patching the global config
        with patch("pypss.cli.discovery.GLOBAL_CONFIG") as mock_config:
            mock_config.discovery_ignore_dirs = ["ignored_folder", ".venv"]
            mock_config.discovery_file_extension = ".py"
            mock_config.discovery_ignore_modules = []
            mock_config.discovery_ignore_funcs_prefix = "_"
            discoverer = CodebaseDiscoverer(str(tmp_path))
            targets = discoverer.discover()

        assert "main" in targets
        assert "ignored_folder.ignored" not in targets
        assert ".venv.lib" not in targets

    def test_analyze_file_parsing(self, tmp_path):
        f = tmp_path / "test_mod.py"
        f.write_text("""
def public_func():
    pass

def _private_func():
    pass

async def async_func():
    pass

class MyClass:
    def method(self):
        pass
""")
        discoverer = CodebaseDiscoverer(str(tmp_path))
        targets = discoverer.discover()

        funcs = targets.get("test_mod", [])
        assert "public_func" in funcs
        assert "async_func" in funcs
        assert "_private_func" not in funcs
        # Currently CodebaseDiscoverer only looks for top-level functions in ast.walk loop
        # It iterates all nodes, so if ast.walk visits class methods, it might find them if they are FunctionDef
        # Let's check logic: ast.walk visits all nodes recursively.
        # So "method" inside MyClass is a FunctionDef.
        assert "method" in funcs

    def test_get_module_score_breakdown(self):
        traces = [
            {"name": "mod_a.func1", "module": "mod_a", "duration": 0.1, "error": False},
            {"name": "mod_a.func2", "module": "mod_a", "duration": 0.2, "error": False},
            {"name": "mod_b.func1", "module": "mod_b", "duration": 0.1, "error": True},
            {"name": "unknown_func", "duration": 0.1},  # No module key
        ]

        breakdown = get_module_score_breakdown(traces)

        assert "mod_a" in breakdown
        assert "mod_b" in breakdown
        assert "unknown" in breakdown

        assert breakdown["mod_a"]["pss"] > 0
        assert breakdown["mod_b"]["breakdown"]["error_volatility"] < 1.0
