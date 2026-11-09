"""A screen's music, written once.

A screen (a "beat" of a scene in steps.json) can carry its music as a phrase, in the
same form as an exercise (see exercise_format.py), with fingers and rhythm:

    "music": {"time": [4, 4], "tempo": 80, "bars": [["C4@1", "D4@2", "E4@3"]],
              "types": [["quarter", "quarter", "half"]]}

The lesson player doesn't read the phrase itself; compile() writes what it reads from it
(the notes played, their rhythm and fingers, the keys of the left hand, the staff's
notes), so the demo, the learner's turn and the staff always show the same music.

A screen also has a kind, which the editor uses to show the right controls (the player
ignores it): "explain", "listen" (Pianove plays, the learner repeats), "find" (the
learner finds keys) or "hand" (where the hand rests).
"""
from __future__ import annotations

from pianove import exercise_format as ef
from pianove.creator_notes import parse_note, parse_chord

KINDS = ("explain", "listen", "find", "hand")


def kind_of(beat: dict) -> str:
    k = beat.get("kind")
    if k in KINDS:
        return k
    if beat.get("play") or beat.get("music"):
        return "listen"
    if beat.get("try"):
        return "find"
    if beat.get("hand"):
        return "hand"
    return "explain"


def _staff_notes_match(beat: dict) -> bool:
    st = beat.get("staff")
    if not st:
        return True
    norm = lambda xs: [tuple(sorted(parse_chord(x) or [])) for x in xs]
    return norm(st.get("notes", [])) == norm(beat.get("play", []))


def music_from_beat(beat: dict) -> dict:
    """A phrase for a screen written before phrases existed: each note played one beat,
    as the player has always played them, with the fingers it had."""
    play = beat.get("play") or []
    fingers = beat.get("fingers") or []
    entries = []
    for k, ev in enumerate(play):
        names = sorted([p.strip() for p in str(ev).split("+") if p.strip()],
                       key=lambda p: parse_note(p) or 0)
        fs = [int(f) for f in str(fingers[k]).split("+")] if k < len(fingers) and fingers[k] else []
        # fingers are listed in the order the player sorts the chord: low to high
        entries.append(ef.join_parts((p, fs[i] if i < len(fs) else None, False)
                                     for i, p in enumerate(names)))
    bars = [entries[i:i + 4] for i in range(0, len(entries), 4)] or [[]]
    music = {"time": [4, 4], "tempo": int(beat.get("tempo", 76)),
             "bars": bars, "types": [["quarter"] * len(b) for b in bars]}
    if beat.get("side") == "left" or (play and max(parse_note(p) or 60 for ev in play
                                                   for p in str(ev).split("+")) < 60):
        music["clef"] = "bass"
    return music


def ensure_music(beat: dict) -> dict:
    """The screen's phrase, made from its notes if it has none yet. A staff that showed
    other notes than the ones played keeps them (staff_own)."""
    if not isinstance(beat.get("music"), dict):
        beat["music"] = music_from_beat(beat)
        if beat.get("staff") and not _staff_notes_match(beat):
            beat["staff_own"] = True
    return beat["music"]


def _bar_starts(music: dict) -> list[float]:
    ps = ef.parts(music)
    bar_q = ef.bar_length(ef.time_of(music))
    n = max(len(b) for b, _ in ps)
    out, q = [], 0.0
    for k in range(n):
        out.append(q)
        q += max([bar_q] + [ef.used(t[k]) for _, t in ps if k < len(t)])
    return out


def events(music: dict):
    """The phrase as played: [(start, length, [(pitch, finger, staff)])], in beats, one
    event per moment something is struck (both hands together); tied notes add to the
    length of the note they continue."""
    starts = _bar_starts(music)
    at: dict[float, dict] = {}
    for s, (bars, types) in enumerate(ef.parts(music)):
        sm = ef.staff_music(bars, types)
        for k, (bar, tys) in enumerate(zip(bars, types)):
            pos, ni = starts[k], 0
            for e, t in zip(bar, tys):
                for p, f, _ in ef.parts_of(e):
                    if not sm["ties"][k][ni] and parse_note(p) is not None:
                        ev = at.setdefault(round(pos, 6), {"len": 0.0, "notes": []})
                        ev["len"] = max(ev["len"], sm["durs"][k][ni])
                        if all(parse_note(q) != parse_note(p) for q, _, _ in ev["notes"]):
                            ev["notes"].append((p, f, s))
                    ni += 1
                pos += ef.quarters(t)
    out = []
    for st in sorted(at):
        notes = sorted(at[st]["notes"], key=lambda n: parse_note(n[0]))
        out.append((st, at[st]["len"], notes))
    return out


def compile_beat(beat: dict, key_fn=None) -> dict:
    """Write the fields the player reads from the screen's phrase (in place)."""
    music = beat.get("music")
    if not isinstance(music, dict):
        return beat
    evs = events(music)
    old_len = len(beat.get("play") or [])
    if not evs:
        for k in ("play", "rhythm", "fingers", "left", "velocities"):
            beat.pop(k, None)
        if beat.get("try") == "play":
            beat.pop("try")
    else:
        beat["play"] = ["+".join(p for p, _, _ in notes) for _, _, notes in evs]
        beat["rhythm"] = [[round(st, 4), round(ln, 4)] for st, ln, _ in evs]
        if all(f for _, _, notes in evs for _, f, _ in notes):
            # one note: its finger as a number (as lessons are written); a chord: "1+3+5"
            beat["fingers"] = [notes[0][1] if len(notes) == 1 else "+".join(str(f) for _, f, _ in notes)
                               for _, _, notes in evs]
        else:
            beat.pop("fingers", None)                # the player plans them itself
        left = sorted({p for _, _, notes in evs for p, _, s in notes if s == 1},
                      key=lambda p: parse_note(p))
        if left:
            beat["left"] = left
        else:
            beat.pop("left", None)
        if len(beat["play"]) != old_len:
            beat.pop("velocities", None)
    beat["tempo"] = ef.tempo_of(music)
    if ef.has_lh(music):
        beat.pop("side", None)
    elif music.get("clef") == "bass":
        beat["side"] = "left"
    st = beat.get("staff")
    if st is not None and not beat.get("staff_own"):
        st["notes"] = list(beat.get("play") or [])
        st["clef"] = "grand" if ef.has_lh(music) else music.get("clef", "treble")
        if key_fn is not None:
            k = key_fn(beat["play"])
            if k:
                st["key"] = k
            else:
                st.pop("key", None)
        if st.get("under") == "count" or st.get("time"):
            st["time"] = ef.time_of(music)
    return beat
