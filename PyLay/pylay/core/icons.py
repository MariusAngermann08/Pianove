"""
Material Icons codepoint registry.

Usage:
    from pylay.core.icons import ICONS
    codepoint = ICONS["home"]          # → ""
    codepoint = ICONS.get("missing")   # → None
"""

import os as _os

_CODEPOINTS_FILE = _os.path.join(
    _os.path.dirname(__file__),
    "..", "assets", "fonts", "MaterialIcons-Regular.codepoints",
)

def _load() -> dict[str, str]:
    result: dict[str, str] = {}
    try:
        with open(_os.path.abspath(_CODEPOINTS_FILE), encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split()
                if len(parts) == 2:
                    name, hex_cp = parts
                    # Names with hyphens in the file use underscores in our API
                    result[name.replace("-", "_")] = chr(int(hex_cp, 16))
    except Exception:
        pass
    return result


ICONS: dict[str, str] = _load()


def get(name: str, fallback: str = "?") -> str:
    """Return the glyph character for *name*, or *fallback* if unknown."""
    return ICONS.get(name, fallback)
