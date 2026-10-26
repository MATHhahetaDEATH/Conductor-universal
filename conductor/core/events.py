from __future__ import annotations
import logging
from collections import defaultdict
from typing import Any, Callable, Dict, List, Tuple

logger = logging.getLogger("conductor.events")

class EventDispatcher:
    """Manages event registrations and dispatching."""

    def __init__(self) -> None:
        # Dictionary mapping event_id -> list of tuples (priority, callback, plugin_id)
        self._listeners: Dict[str, List[Tuple[int, Callable, str]]] = defaultdict(list)

    def register_listener(self, event_id: str, callback: Callable, priority: int = 1000, plugin_id: str = "core") -> None:
        """Register a callback for a specific event with a priority and plugin source."""
        self._listeners[event_id].append((priority, callback, plugin_id))
        # Sort listeners by priority ascending (lower value = higher priority, executes first)
        self._listeners[event_id].sort(key=lambda x: x[0])
        logger.debug(f"Registered listener for '{event_id}' from '{plugin_id}' (priority: {priority})")

    def remove_listeners_by_plugin(self, plugin_id: str) -> int:
        """Remove all listeners registered by a specific plugin. Returns count of removed listeners."""
        count = 0
        for event_id in self._listeners:
            original_len = len(self._listeners[event_id])
            self._listeners[event_id] = [l for l in self._listeners[event_id] if l[2] != plugin_id]
            count += original_len - len(self._listeners[event_id])
        if count > 0:
            logger.debug(f"Removed {count} listeners for plugin '{plugin_id}'")
        return count

    def dispatch(self, event_id: str, *args: Any, **kwargs: Any) -> None:
        """Dispatch an event to all registered listeners."""
        listeners = self._listeners.get(event_id, [])
        logger.debug(f"Dispatching event '{event_id}' to {len(listeners)} listeners")
        
        for priority, callback, plugin_id in listeners:
            try:
                callback(*args, **kwargs)
            except Exception as e:
                logger.error(f"Error executing listener from '{plugin_id}' for '{event_id}': {e}", exc_info=True)

# Centralized registry for decorator-based registrations
_DECORATED_LISTENERS: List[Tuple[str, int, Callable]] = []

def event_listener(event_id: str, priority: int = 1000) -> Callable:
    """Decorator to register a function as an event listener."""
    def decorator(func: Callable) -> Callable:
        _DECORATED_LISTENERS.append((event_id, priority, func))
        return func
    return decorator
