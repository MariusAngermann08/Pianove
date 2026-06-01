import json
from pathlib import Path
from pylay import State

_LOCALES_DIR = Path(__file__).parent / "locales"
_cache: dict[str, dict] = {}

language_state = State("en")


def _load(lang: str) -> dict:
    if lang not in _cache:
        path = _LOCALES_DIR / f"{lang}.json"
        _cache[lang] = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    return _cache[lang]


def t(key: str, **kwargs) -> str:
    lang = language_state.value
    text = _load(lang).get(key) or _load("en").get(key, key)
    return text.format(**kwargs) if kwargs else text


def available_languages() -> list[str]:
    return [p.stem for p in sorted(_LOCALES_DIR.glob("*.json"))]
