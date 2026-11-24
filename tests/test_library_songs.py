"""The songs Pianove brings along: each imports with both hands, builds a learning path,
and is added to the library once (a deleted one stays deleted)."""
import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402
import pianove  # noqa: E402,F401
from pianove import song_store, song_path  # noqa: E402

FILES = sorted((ROOT / "pianove" / "assets" / "songs").glob("*.musicxml"))


@pytest.fixture(autouse=True)
def library(tmp_path, monkeypatch):
    store = tmp_path / "songs"
    monkeypatch.setattr(song_store, "_STORE_DIR", str(store))
    monkeypatch.setattr(song_store, "_FILES_DIR", str(store / "files"))
    monkeypatch.setattr(song_store, "_INDEX_FILE", str(store / "index.json"))
    monkeypatch.setattr(song_store, "_BUNDLED_SEEN", str(store / "bundled.json"))
    monkeypatch.setattr(song_path, "forget", lambda sid: None)


def test_there_are_songs():
    assert len(FILES) >= 10


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.stem)
def test_each_song_reads_with_both_hands(path):
    entry = song_store.import_song(str(path))
    song = song_store.get_song(entry["id"])
    assert song["title"] and song["composer"]
    assert song["n_bars"] >= 8
    assert any(song["bars_rh"]) and any(song["bars_lh"])           # melody and bass
    assert song["difficulty"] in ("beginner", "intermediate", "advanced")
    assert song.get("bpm")
    steps = song_path.build_path(entry["id"])["steps"]
    assert steps


def test_the_easiest_are_rated_beginner():
    for name in ("01_mary_had_a_little_lamb", "02_twinkle_twinkle_little_star", "05_ode_to_joy"):
        entry = song_store.import_song(str(next(p for p in FILES if p.stem == name)))
        assert entry["difficulty"] == "beginner", name


def test_added_once_and_deleted_stays_deleted():
    assert song_store.add_bundled_songs() == len(FILES)
    assert song_store.add_bundled_songs() == 0
    songs = song_store.list_songs()
    assert len(songs) == len(FILES) and all(s.get("bundled") for s in songs)
    song_store.delete_song(songs[0]["id"])
    assert song_store.add_bundled_songs() == 0
    assert len(song_store.list_songs()) == len(FILES) - 1


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
