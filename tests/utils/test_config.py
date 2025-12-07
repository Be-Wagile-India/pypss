import os
import sys

if sys.version_info >= (3, 11):
    pass
else:
    pass
from pypss.utils.config import PSSConfig


class TestConfig:
    def test_load_defaults(self):
        config = PSSConfig.load()
        assert config.sample_rate == 1.0

    def test_load_from_pypss_toml(self, tmp_path):
        config_file = tmp_path / "pypss.toml"
        with open(config_file, "wb") as f:
            f.write(b"[pypss]\nsample_rate = 0.5")

        current_dir = os.getcwd()
        os.chdir(tmp_path)
        try:
            config = PSSConfig.load()
            assert config.sample_rate == 0.5
        finally:
            os.chdir(current_dir)

    def test_load_from_pyproject_toml(self, tmp_path):
        config_file = tmp_path / "pyproject.toml"
        with open(config_file, "wb") as f:
            f.write(b"[tool.pypss]\nsample_rate = 0.3")

        current_dir = os.getcwd()
        os.chdir(tmp_path)
        try:
            config = PSSConfig.load()
            assert config.sample_rate == 0.3
        finally:
            os.chdir(current_dir)

    def test_update_method(self):
        config = PSSConfig()
        config._update({"sample_rate": 0.1, "invalid_key": 123})
        assert config.sample_rate == 0.1
        # Invalid key should be ignored
        assert not hasattr(config, "invalid_key")

    def test_save_exception_handling(self, tmp_path):
        import toml
        from unittest.mock import patch

        config = PSSConfig()
        config.sample_rate = 0.9

        # Mock toml.dump to raise an exception
        with patch.object(toml, "dump", side_effect=IOError("Disk full")):
            # Redirect stdout to capture the print statement
            import io
            from contextlib import redirect_stdout

            f = io.StringIO()
            with redirect_stdout(f):
                config.save(tmp_path / "test_config.toml")

            s = f.getvalue()
            assert "Error saving config" in s
            assert "Disk full" in s
