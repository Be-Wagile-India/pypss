from typing import Any, Dict, List, Optional

from pypss.storage.base import StorageBackend


class ConcreteStorage(StorageBackend):
    """A concrete implementation that calls super() to test the base class."""

    def save(self, report: Dict[str, Any], meta: Optional[Dict[str, Any]] = None) -> None:
        # Explicitly call the abstract base method to ensure it is executable (coverage)
        super().save(report, meta)  # type: ignore[safe-super]

    def get_history(self, limit: int = 10, days: Optional[int] = None) -> List[Dict[str, Any]]:
        # Explicitly call the abstract base method
        super().get_history(limit, days)  # type: ignore[safe-super]
        return []


def test_base_storage_contract():
    """
    Verify that StorageBackend base methods are defined correctly and can be resolved.
    This effectively tests the 'pass' statements in the abstract base class.
    """
    storage = ConcreteStorage()

    # These calls should succeed (return None/Pass) without raising errors
    storage.save({"pss": 100})
    history = storage.get_history()

    assert history == []
