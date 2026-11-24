"""How a run in tempo is judged and kept: accuracy, timing, the last time, the take."""
import os
import sys
import wave
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402
import pianove  # noqa: E402,F401
from pianove.state import storage  # noqa: E402


@pytest.fixture(autouse=True)
def fresh(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "_path", tmp_path / "storage.json")
    monkeypatch.setattr(storage, "_data", {})
    monkeypatch.setenv("HOME", str(tmp_path))


def test_result_and_the_last_time():
    from pianove.pages.lesson import store_result, result_title
    first = store_result("song:x", 7, 10, [0.0, 0.05, -0.12, 0.2])
    assert first["acc"] == 0.7 and first["prev_acc"] is None
    assert first["on_time"] == 0.5                        # 0.0 and 0.05 are within 90 ms
    assert first["mean_ms"] == 32
    second = store_result("song:x", 9, 10, [0.0])
    assert second["prev_acc"] == 0.7 and second["acc"] == 0.9
    assert result_title(0.95) != result_title(0.2)


def test_take_is_saved_as_audio():
    pytest.importorskip("fluidsynth")
    from pianove import recording
    recording.keep([(0.0, 1, 60, 80, 0), (0.5, 0, 60, 0, 0), (0.5, 1, 64, 80, 0), (1.0, 0, 64, 0, 0)],
                   "Test take")
    assert recording.has_take()
    path = recording.save(rate=22050)
    with wave.open(str(path)) as w:
        assert w.getnchannels() == 2 and w.getnframes() > 22050    # the notes plus the tail
