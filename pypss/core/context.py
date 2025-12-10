from contextvars import ContextVar
from typing import Any, Dict, Optional

_current_tags: ContextVar[Optional[Dict[str, Any]]] = ContextVar("pypss_tags", default=None)


def add_tag(key: str, value: Any):
    """
    Adds a custom tag to the current trace context.
    These tags will be attached to the metadata of the active monitored function.

    Example:
        pypss.add_tag("user_id", "12345")
    """
    tags = _current_tags.get()
    if tags is None:
        tags = {}
    else:
        tags = tags.copy()
    tags[key] = value
    _current_tags.set(tags)


def get_tags() -> Dict[str, Any]:
    """Returns the current tags."""
    tags = _current_tags.get()
    return tags if tags is not None else {}


def clear_tags():
    """Clears the tags for the current context."""
    _current_tags.set({})
