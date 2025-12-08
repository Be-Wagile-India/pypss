import importlib
import logging

logger = logging.getLogger(__name__)


def load_plugins(plugin_modules: list[str]):
    """
    Dynamically load plugin modules specified by name.
    This allows external plugins to register themselves with the MetricRegistry.
    """
    for module_name in plugin_modules:
        try:
            importlib.import_module(module_name)
            logger.info(f"PyPSS: Successfully loaded plugin module: {module_name}")
        except ImportError as e:
            logger.error(f"PyPSS: Failed to load plugin module '{module_name}': {e}")
        except Exception as e:
            logger.error(f"PyPSS: Error loading plugin module '{module_name}': {e}")
