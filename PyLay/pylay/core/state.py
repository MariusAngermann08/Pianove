from typing import Callable, Any, List
from pylay.core import _dirty


class State:
    """
    A reactive state wrapper.
    Allows declarative bindings to widgets so that UI elements automatically
    update their contents or values whenever the state variable changes.
    """
    def __init__(self, initial_value: Any):
        self._value = initial_value
        self._listeners: List[Callable[[Any], None]] = []
        
    @property
    def value(self) -> Any:
        return self._value
        
    @value.setter
    def value(self, new_val: Any):
        if self._value != new_val:
            self._value = new_val
            _dirty.mark()
            for callback in list(self._listeners):
                try:
                    callback(new_val)
                except Exception:
                    pass  # Safely handle orphaned bindings
                    
    def set(self, new_val: Any):
        """Update value (alias for assignment, matches demo/snippet style)."""
        self.value = new_val

    def bind(self, callback: Callable[[Any], None]):
        """Bind a callback to be executed immediately and on every value change."""
        self._listeners.append(callback)
        try:
            callback(self._value)
        except Exception:
            pass
            
    def __str__(self) -> str:
        return str(self._value)
