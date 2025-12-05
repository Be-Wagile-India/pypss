from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional


class StorageBackend(ABC):
    @abstractmethod
    def save(
        self, report: Dict[str, Any], meta: Optional[Dict[str, Any]] = None
    ) -> None:
        """Save a PSS report to the storage backend."""
        pass

    @abstractmethod
    def get_history(
        self, limit: int = 10, days: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Retrieve historical PSS reports."""
        pass
