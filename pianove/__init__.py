import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
for _lib in ("PyLay", "PyLute"):
    _p = str(_root / _lib)
    if _p not in sys.path:
        sys.path.insert(0, _p)
