import logging
import os
import sys

import pytest

from pypss.plugins import loader

# Define a temporary directory for dummy modules
DUMMY_MODULE_DIR = os.path.join(os.path.dirname(__file__), "dummy_modules")


@pytest.fixture(autouse=True)
def setup_dummy_modules():
    """Fixture to set up and tear down dummy module directory and sys.path."""
    os.makedirs(DUMMY_MODULE_DIR, exist_ok=True)
    sys.path.insert(0, DUMMY_MODULE_DIR)
    yield
    sys.path.remove(DUMMY_MODULE_DIR)
    # Clean up dummy modules to avoid conflicts in subsequent tests
    for module_name in list(sys.modules.keys()):
        if module_name.startswith("dummy_") or module_name.startswith("broken_"):
            del sys.modules[module_name]
    # Clean up dummy_modules directory and its contents
    for root, dirs, files in os.walk(DUMMY_MODULE_DIR, topdown=False):
        for name in files:
            os.remove(os.path.join(root, name))
        for name in dirs:
            os.rmdir(os.path.join(root, name))
    os.rmdir(DUMMY_MODULE_DIR)


def test_load_plugins_success(caplog):
    """Test successful loading of a plugin module."""
    module_content = """
import logging
logger = logging.getLogger(__name__)
logger.info("Dummy module loaded successfully!")
"""
    with open(os.path.join(DUMMY_MODULE_DIR, "dummy_success.py"), "w") as f:
        f.write(module_content)

    with caplog.at_level(logging.INFO):
        loader.load_plugins(["dummy_success"])
        assert "Successfully loaded plugin module: dummy_success" in caplog.text
        assert "Dummy module loaded successfully!" in caplog.text
    assert "dummy_success" in sys.modules


def test_load_plugins_import_error(caplog):
    """Test handling of ImportError during plugin module loading."""
    with caplog.at_level(logging.ERROR):
        loader.load_plugins(["non_existent_module"])
        assert (
            "Failed to load plugin module 'non_existent_module': No module named 'non_existent_module'" in caplog.text
        )


def test_load_plugins_generic_exception(caplog):
    """Test handling of a generic Exception during plugin module loading."""
    module_content = """
raise ValueError("Something went wrong during import!")
"""
    with open(os.path.join(DUMMY_MODULE_DIR, "dummy_exception.py"), "w") as f:
        f.write(module_content)

    with caplog.at_level(logging.ERROR):
        loader.load_plugins(["dummy_exception"])
        assert "Error loading plugin module 'dummy_exception': Something went wrong during import!" in caplog.text
    assert "dummy_exception" not in sys.modules


def test_load_plugins_multiple_modules(caplog):
    """Test loading multiple modules, some successful, some failing."""
    success_content = """
import logging
logger = logging.getLogger(__name__)
logger.info("Dummy multiple success loaded.")
"""
    exception_content = """
raise TypeError("Multiple exception module error.")
"""
    with open(os.path.join(DUMMY_MODULE_DIR, "dummy_multi_success.py"), "w") as f:
        f.write(success_content)
    with open(os.path.join(DUMMY_MODULE_DIR, "dummy_multi_exception.py"), "w") as f:
        f.write(exception_content)

    modules_to_load = [
        "dummy_multi_success",
        "non_existent_multi_module",
        "dummy_multi_exception",
    ]

    with caplog.at_level(logging.INFO):
        loader.load_plugins(modules_to_load)

        assert "Successfully loaded plugin module: dummy_multi_success" in caplog.text
        assert "Dummy multiple success loaded." in caplog.text
        assert (
            "Failed to load plugin module 'non_existent_multi_module': No module named 'non_existent_multi_module'"
            in caplog.text
        )
        assert "Error loading plugin module 'dummy_multi_exception': Multiple exception module error." in caplog.text

    assert "dummy_multi_success" in sys.modules
    assert "non_existent_multi_module" not in sys.modules
    assert "dummy_multi_exception" not in sys.modules
