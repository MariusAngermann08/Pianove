import json
from pathlib import Path


class Storage:
    def __init__(self, app_name: str = "app"):
        self._path = Path.home() / f".{app_name}" / "storage.json"
        self._data: dict = {}
        self._load()

    def _load(self):
        if self._path.exists():
            try:
                self._data = json.loads(self._path.read_text(encoding="utf-8"))
            except Exception:
                self._data = {}

    def _save(self):
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(self._data, indent=2), encoding="utf-8")

    def get(self, key: str, default=None):
        return self._data.get(key, default)

    def set(self, key: str, value):
        self._data[key] = value
        self._save()

    def remove(self, key: str):
        self._data.pop(key, None)
        self._save()

    def clear(self):
        self._data = {}
        self._save()

    def __contains__(self, key: str) -> bool:
        return key in self._data
