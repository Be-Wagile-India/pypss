from .base import StorageBackend
from .prometheus import PrometheusStorage
from .sqlite import SQLiteStorage


def get_storage_backend(config: dict) -> StorageBackend:
    backend_type = config.get("storage_backend", "sqlite")

    if backend_type == "sqlite":
        db_path = config.get("storage_uri", "pypss_history.db")
        return SQLiteStorage(db_path=db_path)

    elif backend_type == "prometheus":
        uri = config.get("storage_uri")
        mode = config.get("storage_mode", "push")

        if mode == "pull":
            try:
                port = int(uri) if uri else 8000
            except (ValueError, TypeError):
                port = 8000
            return PrometheusStorage(http_port=port)
        else:
            return PrometheusStorage(push_gateway=uri)

    else:
        raise ValueError(f"Unknown storage backend: {backend_type}")


__all__ = [
    "StorageBackend",
    "SQLiteStorage",
    "PrometheusStorage",
    "get_storage_backend",
    "check_regression",
]


def check_regression(
    current_report: dict,
    storage: StorageBackend,
    limit: int = 5,
    threshold_drop: float = 10.0,
) -> str | None:
    """
    Check if the current PSS is significantly lower than the average of recent history.
    Returns a warning message if regression is detected, else None.
    """
    try:
        history = storage.get_history(limit=limit)
        if not history:
            return None

        avg_pss = sum(h["pss"] for h in history) / len(history)
        current_pss = current_report["pss"]

        if current_pss < (avg_pss - threshold_drop):
            return (
                f"⚠️  REGRESSION DETECTED: Current PSS ({current_pss:.1f}) is "
                f"significantly lower than the {limit}-run average ({avg_pss:.1f})."
            )
    except Exception:
        return None

    return None
