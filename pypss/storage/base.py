from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class StorageBackend(ABC):
    @abstractmethod
    def save(self, report: Dict[str, Any], meta: Optional[Dict[str, Any]] = None) -> None:
        pass

    @abstractmethod
    def get_history(self, limit: int = 10, days: Optional[int] = None) -> List[Dict[str, Any]]:
        pass
