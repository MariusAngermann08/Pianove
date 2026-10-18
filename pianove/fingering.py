"""Automatic piano fingering.

`finger_hand(steps, hand)` finds the most comfortable fingering for a whole passage at
once. Every note (and every chord) is tried with each possible finger (or combination of
fingers), and a Viterbi search picks the sequence with the lowest total cost.

The cost model is the ergonomic rule set of Parncutt, Sloboda, Clarke, Raekallio and
Desain (1997), with these extensions:

  * finger length: black keys sit further back, so a short finger on a black key next to
    a long finger on a white one is awkward (generalising Parncutt's "4 on black" rule);
  * wider thumb crossings: arpeggios pass the thumb under a fourth as a matter of course,
    and the thumb slips under a finger on a black key easily;
  * chords: spans inside the chord, and how far the hand is from its relaxed shape;
  * tempo: a stretch or a change of hand position costs less when there is time for it
    (a slow note, or a rest, before the next one);
  * a second-order search, so the three-note rules (position changes, 3-4-5) see every
    candidate, and a scale gets its thumb-under exactly where a pianist puts it.

Span rules use semitones, as Parncutt's table does; hand shape and hand position use
physical key positions (white-key widths). Fingers are numbered as in printed music:
1 = thumb … 5 = little finger, in both hands. The left hand is mirrored, so one set of
rules serves both hands.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

# ── Key geometry ──────────────────────────────────────────────────────────────
_WHITE_IDX = {0: 0, 2: 1, 4: 2, 5: 3, 7: 4, 9: 5, 11: 6}
_BLACK = {1, 3, 6, 8, 10}


def is_black(midi: int) -> bool:
    return midi % 12 in _BLACK


def key_x(midi: int) -> float:
    """Horizontal centre of a key, in white-key widths (the C of octave -1 is at 0.5)."""
    octave, pc = divmod(midi, 12)
    if pc in _WHITE_IDX:
        return octave * 7 + _WHITE_IDX[pc] + 0.5
    return octave * 7 + _WHITE_IDX[pc - 1] + 1.0      # a black key sits on the white-key border


# ── Comfortable spans between two fingers (Parncutt et al. 1997, Table 1) ────
# (MinPrac, MinComf, MinRel, MaxRel, MaxComf, MaxPrac) in semitones, from the
# lower-numbered finger's key to the higher-numbered one's, right hand. Negative = the
# fingers cross, which only the thumb can do. The thumb's crossing limits are wider than
# Parncutt's: arpeggios pass the thumb under a fourth (G with 3, then C with 1).
_SPANS = {
    (1, 2): (-7, -4, 1, 5, 8, 10),
    (1, 3): (-7, -3, 3, 7, 10, 12),
    (1, 4): (-5, -2, 5, 9, 12, 14),
    (1, 5): (-1, 1, 7, 10, 13, 15),
    (2, 3): (1, 1, 1, 2, 3, 5),
    (2, 4): (1, 1, 3, 4, 5, 7),
    (2, 5): (2, 2, 5, 6, 8, 10),
    (3, 4): (1, 1, 1, 2, 2, 4),
    (3, 5): (1, 1, 3, 4, 5, 7),
    (4, 5): (1, 1, 1, 2, 3, 5),
}

# Where each fingertip rests in a relaxed five-finger position, in white keys from the thumb
NATURAL = {1: 0.0, 2: 1.0, 3: 2.0, 4: 3.0, 5: 4.0}
# How far each finger reaches towards the fallboard, relative to the middle finger
_LENGTH = {1: 0.55, 2: 0.85, 3: 1.0, 4: 0.92, 5: 0.72}

_SAME_FINGER   = 12.0   # one finger playing two different keys in a row (no legato possible)
_REPEAT_CHANGE = 0.4    # a repeated key taken by another finger
_CROSSING      = 1.0    # every thumb-under or finger-over moves the hand
_BLACK_UNDER   = 1.5    # semitones of extra room when the thumb slips under a black key
_SHAPE_WEIGHT  = 1.5    # a chord's finger spacing away from the relaxed hand
_RELATIVE      = 1.0    # a finger moving inside the hand between chords, per white key
_SHIFT_WEIGHT  = 1.2    # the whole hand moving between chords, per white key
_STAY_WEIGHT   = 2.5    # a melody's hand drifting from its position, per white key
_LEAP          = 2.0    # past the practical span the hand jumps instead of stretching


@dataclass
class Step:
    """Notes one hand starts together.

    notes  MIDI numbers
    time   onset, in seconds
    hold   how long the notes are held, in seconds
    """
    notes: tuple[int, ...]
    time: float = 0.0
    hold: float = 0.5


@dataclass(frozen=True)
class _Note:
    p: int            # pitch in semitones, mirrored for the left hand
    x: float          # key position in white keys, mirrored for the left hand
    black: bool
    finger: int


def _make(midi: int, finger: int, mirror: int) -> _Note:
    return _Note(mirror * midi, mirror * key_x(midi), is_black(midi), finger)


# ── Cost rules ────────────────────────────────────────────────────────────────

def _span(a: _Note, b: _Note) -> tuple[int, tuple]:
    """Semitones from the lower-numbered finger's key to the higher-numbered one's."""
    if a.finger < b.finger:
        return b.p - a.p, _SPANS[(a.finger, b.finger)]
    return a.p - b.p, _SPANS[(b.finger, a.finger)]


def _stretch(span: float, limits: tuple, thumb: bool, leap: bool = False) -> float:
    """Parncutt rules 1–3: stretch, small span, large span, plus a wall past the practical
    limits. With `leap`, notes in a row: past the practical span the hand simply jumps,
    which costs a fixed amount plus a little per semitone instead of a wall."""
    min_prac, min_comf, min_rel, max_rel, max_comf, max_prac = limits
    if leap and (span > max_prac or span < min_prac):
        edge = max_prac if span > max_prac else min_prac
        return _stretch(edge, limits, thumb) + _LEAP + abs(span - edge)
    c = 0.0
    if span > max_comf:
        c += 2 * (span - max_comf)
    elif span < min_comf:
        c += 2 * (min_comf - span)
    if span > max_prac:
        c += 10 * (span - max_prac)
    elif span < min_prac:
        c += 10 * (min_prac - span)
    rate = 1 if thumb else 2
    if span < min_rel:
        c += rate * (min_rel - span)
    elif span > max_rel:
        c += rate * (span - max_rel)
    return c


def _connection(dt: float, held: float) -> float:
    """How tightly two notes are joined: 1 for fast legato, lower when there is time (a
    slow note, or a rest) to move the hand."""
    c = 1.0 - 0.6 * min(1.0, max(0.0, dt - 0.3) / 0.9)
    if held < dt * 0.75:                         # released early: a rest before the next note
        c *= 0.75
    return c


def _crosses(a: _Note, b: _Note) -> bool:
    """The thumb passes under a finger, or a finger passes over the thumb."""
    return ((a.finger != 1 and b.finger == 1 and b.p > a.p)
            or (a.finger == 1 and b.finger != 1 and b.p < a.p))


def _reach(a: _Note, b: _Note) -> float:
    """Parncutt's rule 9 (4 on black next to 3 on white), generalised by finger length: a
    shorter finger on the black key, next to a longer one on a white key, is awkward."""
    if a.black == b.black or 1 in (a.finger, b.finger):
        return 0.0
    on_black, on_white = (a, b) if a.black else (b, a)
    return 10.0 * max(0.0, _LENGTH[on_white.finger] - _LENGTH[on_black.finger])


def _pair(a: _Note, b: _Note, conn: float) -> float:
    """Cost of playing b right after a (Parncutt rules 1–3 and 8–12)."""
    if a.finger == b.finger:
        if a.p == b.p:
            return 0.0                              # the same key again
        return (_SAME_FINGER + abs(b.p - a.p)) * max(conn, 0.5)
    fa, fb = a.finger, b.finger
    if a.p == b.p:
        c = _REPEAT_CHANGE
    else:
        span, limits = _span(a, b)
        crossing = _crosses(a, b)
        if crossing:
            finger_key, thumb_key = (a, b) if fb == 1 else (b, a)
            if finger_key.black and not thumb_key.black:
                span += _BLACK_UNDER                # the raised key leaves room for the thumb
        c = _stretch(span, limits, min(fa, fb) == 1, leap=True) * conn
        if crossing:                                # rule 12: thumb under / finger over
            c += _CROSSING
            if finger_key.black == thumb_key.black:
                c += 1.0
            elif not finger_key.black and thumb_key.black:
                c += 3.0
    if fa == 3 and fb == 4:                         # rule 8: 3 followed by 4
        c += 1.0
    c += _reach(a, b)                               # rule 9
    if fb == 1 and b.black and not a.black:         # rule 10: the thumb on a black key
        c += 2.0
    if fa == 1 and a.black and not b.black:
        c += 2.0
    if fb == 5 and b.black and not a.black:         # rule 11: the little finger on a black key
        c += 2.0
    if fa == 5 and a.black and not b.black:
        c += 2.0
    return c


def _triple(a: _Note, b: _Note, c: _Note, conn: float) -> float:
    """Parncutt rules 4, 5 and 7 over three single notes in a row, plus a finger that
    comes back to another key and a zig-zag of crossings."""
    cost = 0.0
    if a.finger != c.finger:
        span, limits = _span(a, c)
        min_prac, min_comf, _, _, max_comf, max_prac = limits
        if span > max_comf or span < min_comf:      # rule 4: a change of hand position
            lo, hi = min(a.p, c.p), max(a.p, c.p)
            full = b.finger == 1 and lo < b.p < hi and (span > max_prac or span < min_prac)
            cost += 2.0 if full else 1.0
            # rule 5: how far the hand has to move
            cost += ((min_comf - span) if span < min_comf else (span - max_comf)) * conn
    elif a.p != c.p:
        # one finger on two different keys: the hand has moved by the whole distance
        full = b.finger == 1 and min(a.p, c.p) < b.p < max(a.p, c.p)
        cost += (2.0 if full else 1.0) + abs(c.p - a.p) * conn
    if {a.finger, b.finger, c.finger} == {3, 4, 5}:  # rule 7
        cost += 1.0
    if _crosses(a, b) and _crosses(b, c):           # crossing back and forth
        cost += 3.0
    return cost


def _hand_pos(notes: tuple[_Note, ...]) -> float:
    """Where the thumb of a relaxed hand would be, given which finger plays which key."""
    return sum(n.x - NATURAL[n.finger] for n in notes) / len(notes)


def _unary(notes: tuple[_Note, ...]) -> float:
    """Cost of the fingers themselves, and of the hand shape a chord asks for."""
    c = 0.0
    for n in notes:
        if n.finger in (4, 5):                      # rule 6: weak fingers
            c += 1.0
        if n.finger == 1 and n.black:               # rule 10: the thumb on a black key
            c += 1.0
    if len(notes) > 1:
        for a, b in combinations(notes, 2):         # spans inside the chord
            span, limits = _span(a, b)
            _, min_comf, _, _, max_comf, max_prac = limits
            if span > max_comf:
                c += 2 * (span - max_comf)
            if span > max_prac:
                c += 10 * (span - max_prac)
            if span < min_comf:
                c += 2 * (min_comf - span)
        for a, b in zip(notes, notes[1:]):          # finger spacing against the relaxed hand
            dev = abs((b.x - a.x) - (NATURAL[b.finger] - NATURAL[a.finger]))
            if dev > 0.25:
                c += _SHAPE_WEIGHT * (dev - 0.25) ** 2
            c += 0.5 * _reach(a, b)
        for n in notes:
            if n.finger == 5 and n.black:
                c += 0.5
    return c


def _horizontal(a: tuple[_Note, ...], b: tuple[_Note, ...], conn: float) -> float:
    """Cost of moving from one step to the next."""
    if len(a) == 1 and len(b) == 1:
        na, nb = a[0], b[0]
        c = _pair(na, nb, conn)
        if not _crosses(na, nb) and na.p != nb.p:
            # a melody keeps its hand position: the same key, the same finger
            drift = abs((nb.x - NATURAL[nb.finger]) - (na.x - NATURAL[na.finger]))
            if drift > 0.5:
                c += _STAY_WEIGHT * (drift - 0.5) * conn
        return c
    # With chords, think in hand positions: the whole hand moves (shift), and each finger
    # moves relative to the hand. A finger the previous step did not use was hovering at
    # its relaxed place.
    ha, hb = _hand_pos(a), _hand_pos(b)
    shift = hb - ha
    before = {n.finger: n.x for n in a}
    rel = 0.0
    for nb in b:
        rel += abs((nb.x - before.get(nb.finger, ha + NATURAL[nb.finger])) - shift)
    total = _RELATIVE * rel / len(b)
    if abs(shift) > 0.5:
        total += _SHIFT_WEIGHT * (abs(shift) - 0.5) * conn
    return total


# ── Search ────────────────────────────────────────────────────────────────────

def _prepare(steps: list[Step], hand: str):
    """Per step: the MIDI notes this hand plays (low → high in hand space) and every way to
    finger them, fingers rising with the keys so no two cross inside a chord."""
    mirror = -1 if hand == "left" else 1
    out = []
    for st in steps:
        notes = sorted(set(st.notes))
        if hand == "left":
            notes = notes[:5][::-1]                   # the bottom five, high → low
        else:
            notes = notes[-5:]                        # the top five
        cands = [tuple(_make(m, f, mirror) for m, f in zip(notes, fs))
                 for fs in combinations((1, 2, 3, 4, 5), len(notes))]
        out.append((notes, cands))
    return out


def finger_hand(steps: list[Step], hand: str = "right") -> list[dict[int, int]]:
    """Fingers for one hand: per step, {midi: finger}.

    A chord with more than five notes keeps the five a hand would take (the top five for
    the right hand, the bottom five for the left); the others get no finger.
    """
    prepared = _prepare(steps, hand)
    n = len(prepared)
    if n == 0:
        return []
    unary = [[_unary(c) for c in cands] for _, cands in prepared]
    conns = [1.0] + [_connection(steps[i].time - steps[i - 1].time, steps[i - 1].hold)
                     for i in range(1, n)]

    # Second-order Viterbi: a state is (fingering of the previous step, of this step)
    best: dict = {(None, c): (unary[0][c], None) for c in range(len(prepared[0][1]))}
    trail = [best]
    for i in range(1, n):
        prev_cands, cur_cands = prepared[i - 1][1], prepared[i][1]
        horiz: dict = {}
        nxt: dict = {}
        for (p, c), (cost, _) in best.items():
            for d in range(len(cur_cands)):
                if (c, d) not in horiz:
                    horiz[(c, d)] = _horizontal(prev_cands[c], cur_cands[d], conns[i])
                total = cost + horiz[(c, d)] + unary[i][d]
                if (p is not None and len(prepared[i - 2][1][p]) == 1
                        and len(prev_cands[c]) == 1 and len(cur_cands[d]) == 1):
                    total += _triple(prepared[i - 2][1][p][0], prev_cands[c][0], cur_cands[d][0],
                                     min(conns[i - 1], conns[i]))
                if (c, d) not in nxt or total < nxt[(c, d)][0]:
                    nxt[(c, d)] = (total, (p, c))
        best = nxt
        trail.append(best)

    state = min(best, key=lambda s: best[s][0])   # walk back from the cheapest end
    chosen = [0] * n
    for i in range(n - 1, -1, -1):
        chosen[i] = state[1]
        state = trail[i][state][1]
    return [{m: nt.finger for m, nt in zip(notes, cands[chosen[i]])}
            for i, (notes, cands) in enumerate(prepared)]


def fingering_cost(steps: list[Step], hand: str, fingers: list) -> float:
    """The cost the search gives one particular fingering (fingers listed low → high per
    step, an int for a single note). For tuning: compare a teacher's fingering with the
    search's."""
    mirror = -1 if hand == "left" else 1
    seq = []
    for st, fs in zip(steps, fingers):
        notes = sorted(st.notes)
        fs = [fs] if isinstance(fs, int) else list(fs)
        if hand == "left":
            notes, fs = notes[::-1], fs[::-1]
        seq.append(tuple(_make(m, f, mirror) for m, f in zip(notes, fs)))
    total = sum(_unary(s) for s in seq)
    for i in range(1, len(seq)):
        conn = _connection(steps[i].time - steps[i - 1].time, steps[i - 1].hold)
        total += _horizontal(seq[i - 1], seq[i], conn)
        if i >= 2 and all(len(seq[j]) == 1 for j in (i - 2, i - 1, i)):
            prev_conn = _connection(steps[i - 1].time - steps[i - 2].time, steps[i - 2].hold)
            total += _triple(seq[i - 2][0], seq[i - 1][0], seq[i][0], min(conn, prev_conn))
    return total
