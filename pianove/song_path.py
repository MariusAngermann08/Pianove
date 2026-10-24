"""A learning path through an imported song: the piece cut into parts, what each part
asks of you for the first time, and the steps that get you from the first bars to the
whole piece.

The song is cut into phrases of a few bars (about twelve beats: four bars of 3/4 or 4/4,
eight of 2/4). A phrase that repeats an earlier one is not learned again; one that is
nearly the same (a few notes changed) only gets a short "both hands" step. For every new
phrase you learn each hand on its own, then both together; every two parts are joined,
and the path ends with the whole piece.

    path = build_path(song_id)      # {"parts": [...], "steps": [...]}
    progress(song_id)               # {step_id: stars}
"""
from __future__ import annotations

from collections import Counter

_BLACK = {1, 3, 6, 8, 10}
_SEMITONES = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
_STORAGE_KEY = "song_paths"
_ALONE_MIN = 5          # fewer notes than this in a part: that hand is not learned on its own


def _midi(p: str) -> int:
    name, rest = p[0].upper(), p[1:]
    acc = 0
    while rest and rest[0] in "#b":
        acc += 1 if rest[0] == "#" else -1
        rest = rest[1:]
    return (int(rest) + 1) * 12 + _SEMITONES[name] + acc


def _phrase_len(bar_len_q: float) -> int:
    """Bars per phrase: about twelve beats, in a round number of bars."""
    target = 12.0 / max(0.5, bar_len_q)
    return min((2, 4, 8), key=lambda n: (abs(n - target), -n))


class _Hand:
    """One hand's notes in a stretch of bars: onsets → MIDI numbers."""

    def __init__(self, bars, onsets, durs, bar_lens, a, b):
        self.events: list[tuple[float, tuple[int, ...]]] = []
        self.shortest = None
        pos = 0.0
        for i in range(a, b):
            groups: dict[float, list[int]] = {}
            for k, p in enumerate(bars[i] if i < len(bars) else []):
                try:
                    m = _midi(p)
                except (ValueError, KeyError, IndexError):
                    continue
                on = (onsets[i][k] if onsets and i < len(onsets) and k < len(onsets[i]) else k)
                groups.setdefault(round(pos + on, 3), []).append(m)
                if durs and i < len(durs) and k < len(durs[i]):
                    d = durs[i][k]
                    if d and (self.shortest is None or d < self.shortest):
                        self.shortest = d
            for on in sorted(groups):
                self.events.append((on, tuple(sorted(groups[on]))))
            pos += bar_lens[i] if bar_lens and i < len(bar_lens) else 4.0

    @property
    def notes(self) -> list[int]:
        return [m for _, ms in self.events for m in ms]

    def sig(self):
        """What identifies this hand's music here (to recognise repeats)."""
        start = self.events[0][0] if self.events else 0.0
        return tuple((round(on - start, 2), ms) for on, ms in self.events)


def _similar(a, b) -> float:
    """How alike two phrases are, 0..1: the share of their (when, which keys) events
    that line up, as a diff would match them (a note added, changed or left out costs
    only that note)."""
    if not a or not b:
        return 1.0 if a == b else 0.0
    from difflib import SequenceMatcher
    return SequenceMatcher(None, a, b, autojunk=False).ratio()


def _topics(rh: _Hand, lh: _Hand, seen: dict) -> list[str]:
    """What this phrase asks for the first time in the piece (keys into the locales)."""
    out = []
    for hand, key in ((rh, "rh"), (lh, "lh")):
        if any(len(ms) >= 3 for _, ms in hand.events) and not seen.get(f"{key}_chord"):
            out.append("path_topic_chords")
            seen[f"{key}_chord"] = True
        notes = hand.notes
        if notes:
            lo, hi = min(notes), max(notes)
            if key in seen.get("range", {}):
                plo, phi = seen["range"][key]
                if lo < plo - 4 or hi > phi + 4:
                    out.append("path_topic_new_position")
                seen["range"][key] = (min(plo, lo), max(phi, hi))
            else:
                seen.setdefault("range", {})[key] = (lo, hi)
        tops = [max(ms) for _, ms in hand.events]
        if any(abs(b - a) > 7 for a, b in zip(tops, tops[1:])) and not seen.get(f"{key}_leap"):
            out.append("path_topic_leaps")
            seen[f"{key}_leap"] = True
    if any(m % 12 in _BLACK for m in rh.notes + lh.notes) and not seen.get("black"):
        out.append("path_topic_black_keys")
        seen["black"] = True
    short = min((h.shortest for h in (rh, lh) if h.shortest), default=None)
    if short is not None and short < seen.get("shortest", 99) * 0.99:
        if "shortest" in seen:
            out.append("path_topic_faster")
        seen["shortest"] = short
    if rh.events and lh.events:
        rh_on = {on for on, _ in rh.events}
        if sum(on in rh_on for on, _ in lh.events) >= 2 and not seen.get("together"):
            out.append("path_topic_together")
            seen["together"] = True
    return list(dict.fromkeys(out))


def _difficulty(rh: _Hand, lh: _Hand, quarters: float) -> float:
    """How hard a phrase is to play: notes per beat, chords, leaps, both hands at once."""
    notes = len(rh.notes) + len(lh.notes)
    density = notes / max(1.0, quarters)
    chords = sum(len(ms) >= 3 for _, ms in rh.events + lh.events)
    leaps = 0
    for h in (rh, lh):
        tops = [max(ms) for _, ms in h.events]
        leaps += sum(abs(b - a) > 7 for a, b in zip(tops, tops[1:]))
    return density + 0.15 * chords + 0.2 * leaps + (0.5 if rh.events and lh.events else 0)


_cache: dict = {}


def build_path(song_id: str) -> dict | None:
    """The song's path (worked out once per version of the song)."""
    from pianove.song_store import get_song
    song = get_song(song_id)
    if not song or not song.get("bars_rh"):
        return None
    stamp = (song.get("parser"), song.get("n_bars"), len(song["bars_rh"]), song.get("filepath"))
    hit = _cache.get(song_id)
    if hit is None or hit[0] != stamp:
        hit = _cache[song_id] = (stamp, _build(song))
    return hit[1]


def _build(song: dict) -> dict:
    rh_bars, lh_bars = song.get("bars_rh") or [], song.get("bars_lh") or []
    n = max(len(rh_bars), len(lh_bars))
    bar_lens = song.get("bar_lens") or [4.0] * n
    common = Counter(round(b, 3) for b in bar_lens).most_common(1)
    per = _phrase_len(common[0][0] if common else 4.0)
    while n / per > 12 and per < 8:                         # a long piece: longer parts
        per *= 2

    # phrases: `per` bars each; a short first bar (a pickup) goes with the first phrase
    starts = [0]
    i = 1 if n > 1 and bar_lens[0] < (common[0][0] if common else 4.0) - 1e-3 else 0
    while i + per < n:
        i += per
        starts.append(i)
    bounds = list(zip(starts, starts[1:] + [n]))
    if len(bounds) > 1 and bounds[-1][1] - bounds[-1][0] < max(2, per // 2):
        bounds[-2] = (bounds[-2][0], bounds[-1][1])         # a short tail joins the last one
        bounds.pop()

    parts, seen, letters = [], {}, []
    for a, b in bounds:
        rh = _Hand(rh_bars, song.get("onsets_rh"), song.get("durs_rh"), bar_lens, a, b)
        lh = _Hand(lh_bars, song.get("onsets_lh"), song.get("durs_lh"), bar_lens, a, b)
        if not rh.events and not lh.events:
            continue                                           # only rests: nothing to learn
        sig = (rh.sig(), lh.sig())
        kind, letter = "new", None
        best, best_part = 0.0, None
        for prev in parts:
            if prev["kind"] == "repeat":
                continue
            sim = (len(sig[0]) * _similar(prev["sig"][0], sig[0]) + len(sig[1]) * _similar(prev["sig"][1], sig[1]))                 / max(1, len(sig[0]) + len(sig[1]))
            if sim > best:
                best, best_part = sim, prev
        if best_part is not None and best >= 0.95:
            kind, letter = "repeat", best_part["letter"]
        elif best_part is not None and best >= 0.7:
            kind, letter = "variant", best_part["letter"].rstrip("'") + "'"
        if letter is None:
            letter = chr(ord("A") + len(letters)) if len(letters) < 26 else str(len(letters) + 1)
            letters.append(letter)
        quarters = sum(bar_lens[a:b])
        parts.append({
            "letter": letter, "kind": kind, "bars": (a, b), "sig": sig,
            "hands": [h for h, ev in (("right", rh.events), ("left", lh.events)) if ev],
            "events": {"right": len(rh.events), "left": len(lh.events)},
            "topics": _topics(rh, lh, seen) if kind != "repeat" else [],
            "difficulty": _difficulty(rh, lh, quarters),
        })

    # difficulty 1..3 within this piece: its easiest third of the parts, its middle, its hardest
    ranked = sorted(p["difficulty"] for p in parts)
    for p in parts:
        rank = ranked.index(p["difficulty"]) / max(1, len(ranked) - 1)
        p["difficulty"] = 1 if rank < 1 / 3 else 2 if rank < 2 / 3 else 3

    steps = []

    def step(kind, title_key, a, b, hand, info=None, **fmt):
        steps.append({"id": f"{kind}:{a}-{b}:{hand}", "kind": kind, "title": (title_key, fmt),
                      "bars": (a, b), "hand": hand,
                      "topics": info["topics"] if info else [],
                      "difficulty": info["difficulty"] if info else None,
                      "part": info["letter"] if info else None})

    learned = []
    for part in parts:
        a, b = part["bars"]
        L = part["letter"]
        if part["kind"] == "new":
            # each hand on its own first where the part is not easy (not a hand with only
            # a few notes to play there); then both
            if len(part["hands"]) == 1:
                step("learn", f"path_step_{part['hands'][0]}", a, b, part["hands"][0], part, part=L)
            elif part["difficulty"] >= 2:
                for hand in part["hands"]:
                    if part["events"][hand] >= _ALONE_MIN:
                        step("learn", f"path_step_{hand}", a, b, hand, part, part=L)
            if len(part["hands"]) == 2:
                step("learn", "path_step_both", a, b, "both", part, part=L)
        elif part["kind"] == "variant":
            step("learn", "path_step_variant", a, b, "both" if len(part["hands"]) == 2 else part["hands"][0],
                 part, part=L)
        else:
            continue
        learned.append(part)
        if len(learned) >= 2 and len(learned) % 2 == 0:       # join the last two parts learned
            p, q = learned[-2], learned[-1]
            step("join", "path_step_join", p["bars"][0], q["bars"][1], "both",
                 None, first=p["letter"], second=q["letter"])
    if len(parts) > 1:
        step("full", "path_step_full", 0, n, "both")
    for p in parts:
        p.pop("sig", None)
        p.pop("events", None)
    return {"parts": parts, "steps": steps, "phrase_bars": per}


# ── progress ─────────────────────────────────────────────────────────────────────────

def progress(song_id: str) -> dict:
    from pianove.state import storage
    return dict((storage.get(_STORAGE_KEY) or {}).get(song_id, {}))


def record(song_id: str, step_id: str, accuracy: float):
    """A step played to the end: stars by how well (1..3); the best stays."""
    from pianove.state import storage
    stars = 3 if accuracy >= 0.9 else 2 if accuracy >= 0.7 else 1
    allp = dict(storage.get(_STORAGE_KEY) or {})
    mine = dict(allp.get(song_id, {}))
    mine[step_id] = max(stars, mine.get(step_id, 0))
    allp[song_id] = mine
    storage.set(_STORAGE_KEY, allp)
    return stars


def forget(song_id: str):
    """The song is gone: so is the way through it."""
    from pianove.state import storage
    _cache.pop(song_id, None)
    allp = dict(storage.get(_STORAGE_KEY) or {})
    if allp.pop(song_id, None) is not None:
        storage.set(_STORAGE_KEY, allp)


def next_step(path: dict, done: dict) -> int:
    """The index of the first step not yet done (len(steps) when all are)."""
    for i, s in enumerate(path["steps"]):
        if s["id"] not in done:
            return i
    return len(path["steps"])
