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
