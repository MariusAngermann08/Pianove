"""Clears ~/.pianove/storage.json so the app starts fresh (onboarding re-runs)."""
from pathlib import Path

path = Path.home() / ".pianove" / "storage.json"

if path.exists():
    path.unlink()
    print(f"Deleted {path}")
else:
    print("Nothing to reset — storage file does not exist.")
