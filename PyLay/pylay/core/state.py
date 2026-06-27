from typing import Callable, Any, List
from pylay.core import _dirty


class State:
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
        self.value = new_val

    def bind(self, callback: Callable[[Any], None]):
        self._listeners.append(callback)
        try:
            callback(self._value)
        except Exception:
            pass
            
    def __str__(self) -> str:
        return str(self._value)
