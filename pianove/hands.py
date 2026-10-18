"""Animated hands over the lesson keyboard.

The hands show where each hand should be and which finger plays next, seen from above
(the player's view).

  * Anatomy (pianove.hand_anatomy): bones of fixed length, joints with their real ranges
    and couplings: the end joint follows the middle one, a bent knuckle can hardly spread,
    neighbouring fingers drag each other along, the thumb swings and turns at the wrist.
    So a finger can only reach as far as its joints allow: it bends and spreads a little,
    and never stretches. When a key is out of reach, the whole hand moves or turns.
  * Pose: for each step a solver places the hand (where it is, how it is turned and how
    high it is held) so every playing finger lands on its key the most relaxed way; the
    other fingers hang relaxed beside them, clear of the keys and of each other.
  * Drawing: a flat illustration of that three-dimensional hand, seen from above. Each
    phalanx is a rounded shape of the finger's real width; what lies higher is drawn on
    top, and a finger lying on another casts a soft shadow, so they stay apart like flesh.
    The finger that plays next takes its hand's colour.

Every joint moves on a spring, so changes of position glide and presses dip.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pygame

from pianove import hand_anatomy as A
from pianove.fingering import key_x, is_black

ACCENT = {"right": (0, 122, 255), "left": (255, 149, 0)}

# ── Scale ─────────────────────────────────────────────────────────────────────
# Key space: X in key_x units (white-key widths), Y in white-key widths towards the
# player from the white fingertip line. The hand's own frame is in millimetres (see
# hand_anatomy); a real white key is 23.5 mm wide. Pianove draws its keys much shorter
# than real ones, and on them a full-size hand hides too much, so the hand is drawn a
# little smaller (_SIZE), which keeps every proportion and still spans an octave.
_SIZE = 1.0
K = _SIZE / 23.5                                            # white-key widths per hand millimetre
_KEY_MM = 1.0 / _SIZE                                       # a millimetre of keyboard, in hand millimetres
_BLACK_TOP = 12.0 * _KEY_MM                                 # how much higher a black key's top is
_KEY_TRAVEL = 9.0 * _KEY_MM                                 # how far a key goes down
_PAD = {1: 7.5, 2: 5.5, 3: 5.5, 4: 5.5, 5: 5.0}             # the tip bone above the key it presses
_PERSPECTIVE = 0.0016                                       # how much smaller per mm further down
_REST_LIFT = 3.0                                            # resting fingertips just above the keys
_HZ = 46.0                                                  # knuckles above the white keys, relaxed
_RELAXED = {2: (0.0, 14.0, 46.0), 3: (0.0, 14.0, 46.0), 4: (0.0, 16.0, 48.0),
            5: (0.0, 18.0, 46.0)}                           # abd, MCP, PIP of a finger at rest
_PREFER_PIP = 48.0                                          # the playing curve
_PREFER_MCP = 12.0
_Y_KNUCKLE = A.head(3)[1]                                   # the hand's origin: the middle knuckle

# How each part looks from above: skin radii (mm) along a finger, after the anatomy
_FINGER_RADII = (1.0, 0.94, 0.84, 0.80)                     # × the finger's skin radius
_THUMB_RADII = (14.0, 10.8, 10.0, 9.2)
_TIP_INSET = {1: 2.5}                                       # the skin's end, inside the bone's
# the back of the hand: the metacarpals and the wrist under their skin, blended into one
_PALM_MM = [  # (a, ra, b, rb) in hand millimetres
    ((-12.0, 22.0), 10.0, (-18.5, 82.0), 9.6),
    ((0.0, 22.0), 11.0, (0.0, 80.5), 10.0),
    ((10.0, 20.0), 10.5, (15.6, 72.5), 9.4),
    ((20.0, 16.0), 11.5, (29.8, 63.5), 8.8),
    ((-21.0, 8.0), 11.0, (22.0, 6.0), 11.0),
]


def _mm_to_u(x, y):
    """A point in the hand's frame (mm) → white-key widths from the middle knuckle, +x
    towards the little finger, +y towards the wrist."""
    return x * K, (_Y_KNUCKLE - y) * K


_PALM = [(_mm_to_u(*a), ra * K, _mm_to_u(*b), rb * K) for a, ra, b, rb in _PALM_MM]
_PALM_BLEND = 12.0 * K
_THUMB_BLEND = 34.0 * K
_FINGER_BLEND = 7.0 * K
_CUFF = (0.0, (_Y_KNUCKLE - 20.0) * K)                      # the middle of the sleeve's edge
_CUFF_W = 44.0 * K                                          # half the sleeve's width
_CUFF_SLANT = math.radians(7)
_FOREARM_TURN = 0.5                                          # how much of the hand's turn the forearm follows

# Colours: flat, like an illustration
SKIN_TONES = {                                              # name → colour, lightest first
    "light": (240, 208, 180),
    "medium_light": (221, 188, 155),
    "medium": (191, 146, 106),
    "medium_dark": (141, 98, 64),
    "dark": (92, 62, 44),
}
DEFAULT_SKIN = "medium_light"
_SLEEVE = (104, 113, 127)                                   # a soft slate, light enough for dark mode


def _relaxed_reach():
    """How far in front of the knuckles the middle fingertip lands, relaxed (in key widths)."""
    best, out = 1e9, 0.0
    for fwd in np.arange(20.0, 90.0, 0.5):
        (abd, mcp, pip), err = A.solve_finger(3, (0.0, _Y_KNUCKLE + fwd, _PAD[3] - _HZ))
        c = err * 10 + abs(pip - _PREFER_PIP) + 0.5 * abs(mcp - _PREFER_MCP)
        if c < best:
            best, out = c, fwd
    return out * K


_KNUCKLE_DEPTH = _relaxed_reach()                           # knuckles behind the white fingertips


def sleeve_depth() -> float:
    """Where the sleeve begins on a relaxed hand: white-key widths below the white fingertips."""
    return _KNUCKLE_DEPTH + _CUFF[1]


@dataclass
class KeyboardGeometry:
    """Where the keyboard is on screen."""
    left: float                           # x of the first white key's left edge
    white_w: float
    top: float                            # top of the keys
    key_h: float
    black_h: float
    first_white_x: float                  # key_x() of the first white key
    bottom: float                         # bottom of the hands' area

    @property
    def white_tip_y(self) -> float:
        return self.top + self.black_h + (self.key_h - self.black_h) * 0.50

    @property
    def front(self) -> float:
        """The white keys' front edge, in key widths from the white fingertip line."""
        return (self.top + self.key_h - self.white_tip_y) / self.white_w

    @property
    def black_depth(self) -> float:
        """Where a fingertip sits on a black key, in key widths from the white fingertip line."""
        return -(self.white_tip_y - (self.top + self.black_h * 0.68)) / self.white_w

    def to_px(self, X: float, Y: float) -> tuple[float, float]:
        """Key space (X: key_x units, Y: key widths behind the white fingertip line) → pixels."""
        return (self.left + (X - self.first_white_x + 0.5) * self.white_w,
                self.white_tip_y + Y * self.white_w)


def _key_point(midi: int, black_depth: float, finger: int = 2, front: float = 0.48):
    """A key as a place to play: (X, Y, its top's height in hand mm, nearest Y, farthest Y).
    A finger may play anywhere along that stretch of the key: the short thumb near the
    front, the long fingers further in, between the black keys if need be."""
    if is_black(midi):
        return key_x(midi), black_depth, _BLACK_TOP, black_depth + 0.30, black_depth - 0.40
    return key_x(midi), (0.15 if finger == 1 else 0.0), 0.0, front - 0.10, black_depth * 0.6


# ── Kinematics ────────────────────────────────────────────────────────────────

class Pose:
    """Conversions between key space and one hand's own frame. A hand's placement is
    (hx, hy, th, hz): its middle knuckle in key space, its turn, and its height (mm)."""

    def __init__(self, side: str):
        self.sx = 1.0 if side == "right" else -1.0

    def to_world(self, hx, hy, th, lx, ly):
        lx *= self.sx
        c, s = math.cos(th), math.sin(th)
        return hx + lx * c - ly * s, hy + lx * s + ly * c

    def to_local(self, hx, hy, th, X, Y):
        dx, dy = X - hx, Y - hy
        c, s = math.cos(th), math.sin(th)
        lx, ly = dx * c + dy * s, -dx * s + dy * c
        return lx * self.sx, ly

    def to_mm(self, place, X, Y, top):
        """A point on a key (key space, the key top's height) → the hand frame, mm."""
        hx, hy, th, hz = place
        lx, ly = self.to_local(hx, hy, th, X, Y)
        return lx / K, _Y_KNUCKLE - ly / K, top - hz

    def from_mm(self, place, p):
        """A point of the hand (mm) → key space."""
        hx, hy, th, _ = place
        return self.to_world(hx, hy, th, *_mm_to_u(p[0], p[1]))


def _preferred_tip(f, z):
    """Where finger f's tip lands most comfortably at height z (hand frame, mm)."""
    if f == 1:
        return A.thumb_table().easiest(z)
    abd, _, _ = _RELAXED[f]
    hx, hy, hz = A.head(f)
    ex, ez = A._chain_end(f, _PREFER_PIP)
    h = math.sqrt(max(0.0, ex * ex + ez * ez - (z - hz) ** 2))
    yaw = math.radians(_yaw(f, abd))
    return hx - math.sin(yaw) * h, hy + math.cos(yaw) * h


def _spot(P, place, f, target):
    """The point on a key where finger f plays, in the hand frame (mm): as near to where
    the finger lands most comfortably as that key allows."""
    X, Y, top, near, far = target
    z = top + _PAD[f] - place[3]
    px, py = _preferred_tip(f, z)
    _, Yp = P.from_mm(place, (px, py))
    Y = min(near, max(far, Yp))
    return P.to_mm(place, X, Y, top + _PAD[f])


def _finger_terms(f, p):
    """How badly finger f reaches point p (hand frame): out of reach (heavily), and how far
    from its most relaxed playing shape."""
    if f == 1:
        cost, dist = _thumb_lookup(p)
        return [max(0.0, dist - 1.0) / 0.35, math.sqrt(cost) * 0.9]
    (abd, mcp, pip), err = A.solve_finger(f, p)
    return [err / 0.35, abd / 12.0, (pip - _PREFER_PIP) / 38.0, (mcp - _PREFER_MCP) / 34.0]


def _thumb_lookup(p):
    T = A.thumb_table()
    c, d, _ = T.lookup(p)
    return c, d


def _fit_start(P, targets):
    """The hand laid onto the keys: turned and shifted so the spots where its fingers land
    most comfortably fall as near as possible onto their keys (a rigid least-squares fit)."""
    a, b = [], []
    for f, t in targets.items():
        top = t[2] + _PAD[f] - _HZ
        lx, ly = _mm_to_u(*_preferred_tip(f, top))
        a.append((lx * P.sx, ly))
        b.append((t[0], t[1]))
    a, b = np.array(a), np.array(b)
    ca, cb = a.mean(axis=0), b.mean(axis=0)
    th = 0.0
    if len(a) > 1:
        u, v = a - ca, b - cb
        th = math.atan2(float(np.sum(u[:, 0] * v[:, 1] - u[:, 1] * v[:, 0])), float(np.sum(u * v)))
        th = max(-0.5, min(0.5, th))
    c, s = math.cos(th), math.sin(th)
    hx = cb[0] - (ca[0] * c - ca[1] * s)
    hy = cb[1] - (ca[0] * s + ca[1] * c)
    return np.array([hx, hy, th, _HZ])


_STEPS = np.array([1e-3, 1e-3, 1e-4, 1e-2])                 # finite-difference steps: hx, hy, th, hz


def solve_hand(side: str, targets: dict, prev: tuple | None):
    """Place the hand so each finger in `targets` ({finger: (X, Y, key top)}) reaches its
    key the most relaxed way. Returns (hx, hy, th, hz)."""
    P = Pose(side)
    if not targets:
        return prev

    def residuals(p):
        hx, hy, th, hz = p
        r = []
        for f, t in targets.items():
            r += _finger_terms(f, _spot(P, p, f, t))
        r.append(th / math.radians(11))                        # prefer an upright hand
        r.append((hz - _HZ) / 7.0)                             # … at its usual height
        r.append((hy - _KNUCKLE_DEPTH) / 1.6)                  # … and depth
        if prev is not None:
            r.append((hx - prev[0]) / 6.0)                     # … and not moving needlessly
        return np.array(r)

    def lm(p, iters=24):
        lam, r0 = 1e-2, residuals(p)
        cost = float(r0 @ r0)
        for _ in range(iters):
            J = np.empty((len(r0), 4))
            for k in range(4):
                dp = np.zeros(4)
                dp[k] = _STEPS[k]
                J[:, k] = (residuals(p + dp) - r0) / _STEPS[k]
            A_, g = J.T @ J, J.T @ r0
            improved, before = False, cost
            while lam < 1e6:
                step = np.linalg.solve(A_ + lam * np.diag(np.diag(A_) + 1e-9), -g)
                r1 = residuals(p + step)
                c = float(r1 @ r1)
                if c < cost:
                    p, r0, cost, lam, improved = p + step, r1, c, max(1e-6, lam / 3), True
                    break
                lam *= 4
            if not improved or np.max(np.abs(step / _STEPS)) < 2.0 or cost > before * 0.999:
                break
        return p, cost

    # Starts: where the hand is, and the relaxed hand shifted so its fingers land on the
    # targets on average, held straight or turned either way; the best one wins
    hx0 = sum(t[0] - _REST_TIP_X[f] * P.sx for f, t in targets.items()) / len(targets)
    starts = [_fit_start(P, targets)] + [np.array([hx0, _KNUCKLE_DEPTH, th, _HZ]) for th in (0.0, -0.3, 0.3)]
    if prev is not None and abs(prev[0] - hx0) < 2.0:
        starts.insert(0, np.array(prev, float))
    scored = sorted(starts, key=lambda p0: float(np.sum(residuals(p0) ** 2)))
    best = min((lm(p0, 8) for p0 in scored[:2]), key=lambda pc: pc[1])
    p, _ = lm(best[0])
    hx, hy, th, hz = (float(v) for v in p)
    return hx, hy, max(math.radians(-30), min(math.radians(30), th)), max(22.0, min(66.0, hz))


def _rest_tip_x():
    """Where each relaxed fingertip lies across the hand (key widths from the middle knuckle)."""
    out = {}
    for f, (abd, mcp, pip) in _RELAXED.items():
        out[f] = A.finger_points(f, abd, mcp, pip)[0][-1][0] * K
    out[1] = A.thumb_points(**A.THUMB_REST)[0][-1][0] * K
    return out


_REST_TIP_X = _rest_tip_x()


def _toward(a, b, d):
    """The point d mm from a towards b."""
    v = [y - x for x, y in zip(a, b)]
    n = math.sqrt(sum(c * c for c in v)) or 1.0
    return tuple(x + c * d / n for x, c in zip(a, v))


def _segments(f, joints):
    """A finger's skin as 3D round cones: (points, radii mm)."""
    if f == 1:
        pts, _ = A.thumb_points(*joints)
        # the thenar muscles bulge as they pull the thumb across the palm
        rad, palm, mcp, _ = joints
        bulge = min(1.0, max(0.0, (palm + 0.5 * mcp + 0.3 * (30.0 - rad)) / 70.0))
        radii = [14.5 + 2.5 * bulge, 11.6, *_THUMB_RADII[2:]]
        return [_toward(pts[0], pts[1], 6.0), pts[1], pts[2],
                _toward(pts[3], pts[2], _TIP_INSET[1])], radii
    pts, _ = A.finger_points(f, *joints)
    r = A.FINGERS[f]["skin"]
    return pts[:3] + [_toward(pts[3], pts[2], 2.2)], [r * k for k in _FINGER_RADII]


def _seg_dist(p1, q1, p2, q2):
    """Closest distance between two 3D segments."""
    p1, q1, p2, q2 = (np.asarray(v, float) for v in (p1, q1, p2, q2))
    d1, d2, r = q1 - p1, q2 - p2, p1 - p2
    a, e, f = d1 @ d1, d2 @ d2, d2 @ r
    if a < 1e-9 and e < 1e-9:
        return float(np.linalg.norm(r))
    if a < 1e-9:
        s, t = 0.0, min(1.0, max(0.0, f / e))
    else:
        c = d1 @ r
        if e < 1e-9:
            t, s = 0.0, min(1.0, max(0.0, -c / a))
        else:
            b = d1 @ d2
            den = a * e - b * b
            s = min(1.0, max(0.0, (b * f - c * e) / den)) if den > 1e-9 else 0.0
            t = (b * s + f) / e
            if t < 0:
                t, s = 0.0, min(1.0, max(0.0, -c / a))
            elif t > 1:
                t, s = 1.0, min(1.0, max(0.0, (b - c) / a))
    return float(np.linalg.norm(p1 + d1 * s - p2 - d2 * t))


def _overlap(fa, ja, fb, jb):
    """How deep two fingers' flesh would press into each other (mm; soft tissue gives 1.2)."""
    pa, ra = _segments(fa, ja)
    pb, rb = _segments(fb, jb)
    worst = 0.0
    for i in range(len(pa) - 1):
        for k in range(len(pb) - 1):
            d = _seg_dist(pa[i], pa[i + 1], pb[k], pb[k + 1])
            worst = max(worst, (ra[i] + ra[i + 1] + rb[k] + rb[k + 1]) / 2 * 0.80 - 1.2 - d)
    return worst


def _yaw(f, abd):
    g = A.FINGERS[f]
    return -g["ang"] + g["rest"] + abd


def hand_joints(side: str, place: tuple, targets: dict, black_depth: float = -1.0):
    """Every finger's joints for a placed hand: {finger: (up, down)}, where up touches the
    key (or hovers, for a finger that does not play) and down has pressed it.

    Playing fingers reach their keys as far as their joints allow. The others hang
    relaxed beside them: dragged a little by their playing neighbours (shared tendons),
    never bent further apart than the juncturae let them, clear of the keys and never
    through a neighbour."""
    P = Pose(side)
    hz = place[3]
    out, spots = {}, {}
    for f, t in targets.items():
        p = spots[f] = _spot(P, place, f, t)
        q = (p[0], p[1], p[2] - _KEY_TRAVEL)
        if f == 1:
            up, _ = A.solve_thumb(p)
            down, _ = A.solve_thumb(q, up)
        else:
            up, _ = A.solve_finger(f, p)
            down, _ = A.solve_finger(f, q)
        out[f] = (tuple(up), tuple(down))

    # Fingers that do not play rest lightly on the keys where they land most comfortably,
    # curved like the playing ones
    # along the same arc as the playing ones: as far in or out as those had to reach
    shift = [spots[f][1] - _preferred_tip(f, spots[f][2])[1] for f in (2, 3, 4, 5) if f in spots]
    shift = min(4.0, max(-25.0, sum(shift) / len(shift))) if shift else 0.0
    rest = {}
    for f in range(1, 6):
        z = _PAD[f] + _REST_LIFT - hz
        px, py = _preferred_tip(f, z)
        if f != 1:
            py += shift
            # … and never beyond the black keys' fronts, off the keyboard
            _, Y = P.from_mm(place, (px, py))
            if Y < black_depth - 0.1:
                py -= (black_depth - 0.1 - Y) / K
        if f == 1:
            rest[1] = A.rest_thumb((px, py, z))
        else:
            rest[f], _ = A.solve_finger(f, (px, py, z))
    if 1 not in out:
        out[1] = (rest[1], rest[1])

    playing = [f for f in (2, 3, 4, 5) if f in targets]
    for f in (2, 3, 4, 5):
        if f in targets:
            continue
        abd, mcp, pip = rest[f]
        # dragged along by the playing fingers (shared flexor bellies)
        for g in playing:
            k = A.ENSLAVE[g].get(f, 0.0)
            mcp += k * (out[g][0][1] - rest[g][1])
            pip += k * (out[g][0][2] - rest[g][2])
        # kept between its neighbours
        lo_n = max((g for g in playing if g < f), default=None)
        hi_n = min((g for g in playing if g > f), default=None)
        yaw = _yaw(f, abd)
        if lo_n is not None and hi_n is not None:
            ya, yb = _yaw(lo_n, out[lo_n][0][0]), _yaw(hi_n, out[hi_n][0][0])
            yaw = ya + (yb - ya) * (f - lo_n) / (hi_n - lo_n)
        elif lo_n is not None:
            yaw = min(yaw, _yaw(lo_n, out[lo_n][0][0]) - 5.0 * (f - lo_n))
        elif hi_n is not None:
            yaw = max(yaw, _yaw(hi_n, out[hi_n][0][0]) + 5.0 * (hi_n - f))
        abd = yaw - _yaw(f, 0.0)
        g = A.FINGERS[f]
        mcp = min(g["mcp"][1], max(g["mcp"][0], mcp))
        pip = min(g["pip"][1], max(g["pip"][0], pip))
        lo, hi = A.abd_limits(f, mcp)
        out[f] = ((min(hi, max(lo, abd)), mcp, pip),) * 2

    # the juncturae tendinum: neighbouring knuckles cannot bend too far apart
    for a, b, lim in A.JUNCTURAE:
        ja, jb = out[a][0], out[b][0]
        d = jb[1] - ja[1]
        if abs(d) > lim:
            fix = (abs(d) - lim) * math.copysign(1.0, d)
            if b not in targets:
                jb = (jb[0], jb[1] - fix, jb[2])
                out[b] = (jb, jb)
            elif a not in targets:
                ja = (ja[0], ja[1] + fix, ja[2])
                out[a] = (ja, ja)

    # a resting finger moves aside (or lifts) rather than through a neighbour
    for f in (2, 3, 4, 5):
        if f in targets:
            continue
        abd, mcp, pip = out[f][0]
        for _ in range(10):
            hit = None
            for n in (f - 1, f + 1, 1):
                if n in out and n != f and (n in targets or n == 1) and _overlap(f, (abd, mcp, pip), n, out[n][0]) > 0:
                    hit = n
                    break
            if hit is None:
                break
            lo, hi = A.abd_limits(f, mcp)
            away = -3.0 if hit < f else 3.0                   # towards the little finger, or back
            nabd = min(hi, max(lo, abd + away))
            if abs(nabd - abd) < 0.5:
                mcp -= 5.0                                     # no room to the side: lift it
            abd = nabd
        out[f] = ((abd, mcp, pip),) * 2
    return out


_SOLVED: dict = {}


def solve_cached(side: str, targets: dict, prev, black_depth: float):
    """solve_hand and hand_joints for one set of keys, remembered: a piece repeats its
    hand positions, and upcoming steps are solved ahead of time (see HandsOverlay)."""
    key = (side, tuple(sorted(targets.items())), round(black_depth, 3))
    hit = _SOLVED.get(key)
    if hit is None:
        place = solve_hand(side, targets, prev)
        hit = (place, hand_joints(side, place, targets, black_depth))
        if len(_SOLVED) > 2000:
            _SOLVED.pop(next(iter(_SOLVED)))
        _SOLVED[key] = hit
    return hit


def is_solved(side: str, targets: dict, black_depth: float) -> bool:
    return (side, tuple(sorted(targets.items())), round(black_depth, 3)) in _SOLVED


_QUEUE = None
_PENDING: set = set()


def solve_ahead(side: str, targets: dict, prev, black_depth: float):
    """Have solve_cached work out a hand position on a worker thread, before it is needed."""
    global _QUEUE
    key = (side, tuple(sorted(targets.items())), round(black_depth, 3))
    if key in _SOLVED or key in _PENDING:
        return
    if _QUEUE is None:
        import queue
        import threading
        _QUEUE = queue.Queue()

        def work():
            while True:
                k, args = _QUEUE.get()
                try:
                    solve_cached(*args)
                except Exception:                              # never take the app down
                    pass
                _PENDING.discard(k)

        threading.Thread(target=work, daemon=True, name="hands-solver").start()
    _PENDING.add(key)
    _QUEUE.put((key, (side, dict(targets), prev, black_depth)))


def reach_error(side: str, place: tuple, f: int, point) -> float:
    """How far (mm) finger f's tip stays from a key point for a placed hand."""
    P = Pose(side)
    p = _spot(P, place, f, point)
    if f == 1:
        c, d = _thumb_lookup(p)
        if d > 4.0:
            return d
        return A.solve_thumb(p)[1]
    return A.solve_finger(f, p)[1]


def tip_point(side: str, place: tuple, f: int, joints) -> tuple[float, float]:
    """Where finger f's tip is, in key space."""
    P = Pose(side)
    tip = A.thumb_points(*joints)[0][-1] if f == 1 else A.finger_points(f, *joints)[0][-1]
    return P.from_mm(place, tip)


def _unit(v):
    n = math.sqrt(sum(c * c for c in v)) or 1.0
    return tuple(c / n for c in v)


def _add(p, v, k=1.0):
    return tuple(a + b * k for a, b in zip(p, v))


def _finger_frames(f, joints):
    """A finger's bones as (direction, back of the finger) pairs, and its points."""
    pts, phis = A.finger_points(f, *joints)
    yaw = math.radians(_yaw(f, joints[0]))
    fx, fy = -math.sin(yaw), math.cos(yaw)
    frames = [((fx * math.cos(p), fy * math.cos(p), -math.sin(p)),
               (fx * math.sin(p), fy * math.sin(p), math.cos(p))) for p in phis]
    return pts, frames


def _details(f, joints, proj, px_mm):
    """What makes a finger read as bones and joints rather than a tube that grows: its
    nail, foreshortened as the tip turns down and gone when it points at the key; creases
    over a straight joint. In pixels."""
    out = []
    if f == 1:
        pts, frames = A.thumb_points(*joints)
        bones = [(pts[2], pts[3], frames[2], 9.6)]          # the nail's phalanx
        joint_list = [(pts[2], frames[1], frames[2], joints[3], 10.0, 2)]
        nail_len = 12.0
    else:
        pts, frames = _finger_frames(f, joints)
        r = A.FINGERS[f]["skin"]
        bones = [(pts[2], pts[3], frames[2], r * 0.82)]
        dip = joints[2] * A.DIP_LINK
        joint_list = [(pts[1], frames[0], frames[1], joints[2], r * _FINGER_RADII[1], 3),
                      (pts[2], frames[1], frames[2], dip, r * _FINGER_RADII[2], 2)]
        nail_len = A.FINGERS[f]["p"][2] * 0.62

    def axis(p, v):
        a, b = proj(p), proj(_add(p, v, 5.0))
        d = math.hypot(b[0] - a[0], b[1] - a[1]) or 1.0
        return a, ((b[0] - a[0]) / d, (b[1] - a[1]) / d), d / (5.0 * px_mm)

    for a, b, (y, z), r in bones:
        L = math.dist(a, b)
        seen = (z[2] - 0.04) / 0.30                         # how much the nail faces up
        if seen > 0.02:
            c = _add(_add(a, y, L * 0.64), z, r * 0.80)
            c2, ax, fore = axis(c, y)
            out.append(("nail", c2[0], c2[1], ax[0], ax[1], 0.5 * nail_len * fore * px_mm,
                        r * 0.60 * px_mm, min(1.0, seen)))
    for J, (y0, z0), (y1, z1), ang, r, n in joint_list:
        nb = _unit(_add(z0, z1))
        if nb[2] <= 0.05:
            continue
        top = _add(J, nb, r * 0.92)
        c2, ax, fore = axis(top, _unit(_add(y0, y1)))
        crease = max(0.0, 1.0 - ang / 40.0) * nb[2] * (1.0 if n > 2 else 0.7)
        if crease > 0.03:
            out.append(("joint", c2[0], c2[1], ax[0], ax[1], r * 0.50 * px_mm,
                        1.5 * px_mm * max(0.25, fore), 1, crease))
    return tuple(out)


# ── Drawing: a signed distance field ─────────────────────────────────────────

def _sd_round_cone(px, py, ax, ay, bx, by, r1, r2):
    """Distance to a cone with round ends (radius r1 at a, r2 at b); exact (Inigo Quilez)."""
    bax, bay = bx - ax, by - ay
    l2 = bax * bax + bay * bay
    if l2 < 1e-6:
        return np.hypot(px - ax, py - ay) - max(r1, r2)
    rr = r1 - r2
    a2 = l2 - rr * rr
    il2 = 1.0 / l2
    pax, pay = px - ax, py - ay
    y = pax * bax + pay * bay
    z = y - l2
    qx, qy = pax * l2 - bax * y, pay * l2 - bay * y
    x2 = qx * qx + qy * qy
    y2 = y * y * l2
    z2 = z * z * l2
    k = np.sign(rr) * rr * rr * x2
    d3 = (np.sqrt(np.maximum(x2 * a2 * il2, 0)) + y * rr) * il2 - r1
    d1 = np.sqrt(x2 + z2) * il2 - r2
    d2 = np.sqrt(x2 + y2) * il2 - r1
    return np.where(np.sign(z) * a2 * z2 > k, d1, np.where(np.sign(y) * a2 * y2 < k, d2, d3))


# coverage of a pixel from the distance code (128 − 16 × distance in pixels)
_COVERAGE = np.clip((np.arange(256) - 120) * 16, 0, 255).astype(np.uint8)
_COVERAGE_F = _COVERAGE.astype(np.float32) / 255


def _upscale(data, q):
    """An (h, w, 4) uint8 array, q times larger through pygame's bilinear scaling."""
    h, w = data.shape[:2]
    img = pygame.transform.smoothscale(pygame.image.frombuffer(data.tobytes(), (w, h), "RGBA"),
                                       (w * q, h * q))
    return np.frombuffer(pygame.image.tobytes(img, "RGBA"), np.uint8).reshape(h * q, w * q, 4)


def _draw_details(col, dets, bx, by, lw):
    """Paint a finger's nail and knuckle crease onto its colour (an (h, w, 3) block whose
    top-left pixel sits at bx, by), at full resolution, in the finger's own colour."""
    h, w = col.shape[:2]
    for det in dets:
        kind, cx, cy, ax, ay = det[:5]
        nx, ny = -ay, ax
        if kind == "nail":
            hl, hw, seen = det[5:8]
            if hl < 0.7 or seen < 0.03:
                continue
            reach = max(hl, hw) + 2.0
        else:
            half, step, n, crease = det[5:9]
            if crease < 0.03:
                continue
            reach = half + 3.0
        j0, j1 = max(0, int(cx - bx - reach)), min(w, int(cx - bx + reach) + 1)
        i0, i1 = max(0, int(cy - by - reach)), min(h, int(cy - by + reach) + 1)
        if j1 <= j0 or i1 <= i0:
            continue
        px = np.arange(j0, j1, dtype=np.float32)[None, :] + np.float32(bx + 0.5 - cx)
        py = np.arange(i0, i1, dtype=np.float32)[:, None] + np.float32(by + 0.5 - cy)
        u = px * ax + py * ay                                 # along the finger, + to the tip
        v = px * nx + py * ny                                 # across it
        blk = col[i0:i1, j0:j1]
        if kind == "nail":
            # a nail: rounded at its free edge, squarer at the cuticle, foreshortened as the
            # tip turns down; a lighter rim of free edge at the tip
            p = np.where(u > 0, 2.4, 4.0)
            r = (np.abs(u / hl) ** p + np.abs(v / hw) ** p) ** (1.0 / p)
            sd = (r - 1.0) * min(hl, hw)
            cov = np.clip(0.5 - sd, 0.0, 1.0) * seen
            tipband = np.clip((u - hl * 0.62) * 1.5, 0.0, 1.0)
            nail = blk * 0.70 + np.float32(255 * 0.30)
            free = blk * 0.45 + np.float32(255 * 0.55)
            target = nail + (free - nail) * tipband[..., None]
            blk += (target - blk) * (cov * 0.9)[..., None]
        else:
            # one crease across a straight knuckle, bowed like the skin over it
            taper = np.clip(1.0 - (v / half) ** 2, 0.0, 1.0)
            bow = u + 0.25 * (v * v) / max(half, 1.0)
            line = np.clip(lw - np.abs(bow), 0.0, 1.0) * taper
            blk *= (1.0 - 0.16 * crease * line)[..., None]
    return col


def _phalanx_fields(PX, PY, chain, radii, tones, zs):
    """Per pixel, which phalanx of a finger shows and so its tone, and how high the finger
    is there (mm): each joint's fold is a line across the finger, bowed a little towards
    the tip like the knuckle under the skin, anti-aliased to one pixel."""
    n = len(chain) - 1
    dirs = []
    for a, b in zip(chain, chain[1:]):
        dx, dy = b[0] - a[0], b[1] - a[1]
        L = math.hypot(dx, dy)
        dirs.append((dx / L, dy / L, L) if L > 0.5 else None)

    def seg_height(i):
        (ax, ay), (bx, by) = chain[i], chain[i + 1]
        ex, ey = bx - ax, by - ay
        l2 = ex * ex + ey * ey
        if l2 < 0.25:
            return np.float32((zs[i] + zs[i + 1]) / 2)
        t = np.clip(((PX - ax) * ex + (PY - ay) * ey) * np.float32(1.0 / l2), 0.0, 1.0)
        return zs[i] + (zs[i + 1] - zs[i]) * t

    tone = np.full(np.broadcast(PX, PY).shape, tones[0], np.float32)
    height = seg_height(0) + np.zeros_like(tone)
    for j in range(1, n):
        d0 = dirs[j - 1] or dirs[j]
        d1 = dirs[j] or dirs[j - 1]
        if d0 is None:
            continue
        nx, ny = d0[0] + d1[0], d0[1] + d1[1]
        L = math.hypot(nx, ny)
        nx, ny = (nx / L, ny / L) if L > 0.2 else (d0[0], d0[1])
        Jx, Jy = chain[j]
        rx, ry = PX - Jx, PY - Jy
        across = rx * -ny + ry * nx
        s = rx * nx + ry * ny + across * across * np.float32(0.35 / max(radii[j], 1.0))
        m = np.clip(0.5 + s, 0.0, 1.0)
        tone += (tones[j] - tone) * m
        height += (seg_height(j) - height) * m
    return tone, height


def _smin(a, b, k):
    h = np.maximum(k - np.abs(a - b), 0.0) / k
    return np.minimum(a, b) - h * h * k * 0.25


@dataclass
class HandPose:
    """Everything needed to draw one hand, in pixels."""
    side: str
    u: float
    origin: tuple            # the knuckle line's middle
    theta: float
    fingers: dict            # finger → (joint points px, base … tip; radii px; a tone per
    #                          phalanx; each point's height, mm)
    press: dict
    glow: dict
    alpha: float
    bottom: float            # the canvas ends here
    skin: tuple = SKIN_TONES[DEFAULT_SKIN]
    order: tuple = (2, 3, 4, 5)   # the fingers, highest (drawn on top) first
    details: dict | None = None   # finger → nail, creases, knuckles (see _details), px


class HandRenderer:
    """Draws a hand from a pose. Keeps the last image while the pose holds still."""

    _Q = 4                                                  # the coarse grid: every fourth pixel

    def __init__(self):
        self._last: dict = {}
        self._palm_cache: dict = {}
        self._sleeve_cache: dict = {}

    def render(self, pose: HandPose, may_draw: bool = True):
        """(image, its corner), or None when invisible.

        The image depends only on the hand's shape in its own frame: moving the whole hand
        reuses it, so only a change of finger, turn, press or glow draws again. With
        may_draw False, a changed hand keeps its last image for this frame (still moving
        with the hand)."""
        if pose.alpha <= 0.01:
            return None
        ox, oy = int(round(pose.origin[0])), int(round(pose.origin[1]))
        rel = {f: (tuple((x - ox, y - oy) for x, y in pts), *rest)
               for f, (pts, *rest) in pose.fingers.items()}
        key = self._key(pose)
        hit = self._last.get(pose.side)
        if hit and (hit[0] == key or not may_draw):
            out = hit[1]
        else:
            local = HandPose(side=pose.side, u=pose.u, origin=(pose.origin[0] - ox, pose.origin[1] - oy),
                             theta=pose.theta, fingers=rel, press=pose.press, glow=pose.glow,
                             alpha=pose.alpha, bottom=pose.bottom - oy,
                             skin=pose.skin, order=pose.order,
                             details={f: tuple((d[0], d[1] - ox, d[2] - oy, *d[3:]) for d in ds)
                                      for f, ds in (pose.details or {}).items()})
            out = self._render(local)
            self._last[pose.side] = (key, out)
        if out is None:
            return None
        return out[0], (out[1][0] + ox, out[1][1] + oy)

    @staticmethod
    def _key(pose: HandPose):
        """The hand's shape in its own frame, in half pixels: what its image depends on."""
        ox, oy = int(round(pose.origin[0])), int(round(pose.origin[1]))
        q = 2.0
        return (pose.side, pose.skin, pose.order, round(pose.u, 2), round(pose.theta * 250),
                round(pose.alpha * 40), round(pose.bottom - oy),
                round((pose.origin[0] - ox) * q), round((pose.origin[1] - oy) * q),
                tuple((f, tuple((round((x - ox) * q), round((y - oy) * q)) for x, y in pts),
                       tuple(round(r * q) for r in radii), tuple(round(t * 100) for t in tones),
                       tuple(round(z) for z in zs),
                       round(pose.press.get(f, 0) * 10), round(pose.glow.get(f, 0) * 10))
                      for f, (pts, radii, tones, zs) in sorted(pose.fingers.items())),
                tuple((f, tuple((d[0], round((d[1] - ox) * q), round((d[2] - oy) * q),
                                 *(round(v * 20) for v in d[3:])) for d in ds))
                      for f, ds in sorted((pose.details or {}).items())))

    def is_current(self, pose: HandPose) -> bool:
        """Would render() reuse the last image as it is?"""
        hit = self._last.get(pose.side)
        return bool(hit) and hit[0] == self._key(pose)

    def _palm(self, pose: HandPose, world):
        """The back of the hand's distance field on the coarse grid. It depends only on how
        the hand is turned, so it is kept until the hand turns."""
        u, q = pose.u, self._Q
        key = (pose.side, round(u, 2), round(pose.theta * 500),
               round(pose.origin[0] * 4), round(pose.origin[1] * 4))
        hit = self._palm_cache.get(pose.side)
        if hit and hit[0] == key:
            return hit[1]
        cones = [(world(*a), ra * u, world(*b), rb * u) for a, ra, b, rb in _PALM]
        m = (_PALM_BLEND + 0.6) * u
        px0 = int(math.floor((min(min(a[0] - ra, b[0] - rb) for a, ra, b, rb in cones) - m) / q)) * q
        py0 = int(math.floor((min(min(a[1] - ra, b[1] - rb) for a, ra, b, rb in cones) - m) / q)) * q
        px1 = max(max(a[0] + ra, b[0] + rb) for a, ra, b, rb in cones) + m
        py1 = max(max(a[1] + ra, b[1] + rb) for a, ra, b, rb in cones) + m
        pw, ph = int((px1 - px0) / q) + 1, int((py1 - py0) / q) + 1
        X = np.broadcast_to((np.arange(pw, dtype=np.float32)[None, :] + 0.5) * q + px0, (ph, pw))
        Y = np.broadcast_to((np.arange(ph, dtype=np.float32)[:, None] + 0.5) * q + py0, (ph, pw))
        d = None
        for a, ra, b, rb in cones:
            di = _sd_round_cone(X, Y, a[0], a[1], b[0], b[1], ra, rb)
            d = di if d is None else _smin(d, di, _PALM_BLEND * u)
        out = (px0, py0, d)
        self._palm_cache[pose.side] = (key, out)
        return out

    def _sleeve(self, pose: HandPose, x0: int, y0: int, W: int, H: int):
        """The sleeve, drawn once per turn of the hand (it does not depend on the fingers):
        a flat rounded band from the cuff down past the bottom of the canvas."""
        u = pose.u
        key = (pose.side, round(u, 2), round(pose.theta * 250), round(pose.origin[0] * 2),
               round(pose.origin[1] * 2), x0, y0, W, H)
        hit = self._sleeve_cache.get(pose.side)
        if hit and hit[0] == key:
            return hit[1]
        sx = 1.0 if pose.side == "right" else -1.0
        c, s = math.cos(pose.theta), math.sin(pose.theta)
        ox, oy = pose.origin
        # the cuff sits at the wrist, but the forearm turns only part of the way with the
        # hand: the rest is the wrist bending
        cx = ox + (_CUFF[0] * sx * c - _CUFF[1] * s) * u
        cy = oy + (_CUFF[0] * sx * s + _CUFF[1] * c) * u
        c, s = math.cos(pose.theta * _FOREARM_TURN), math.sin(pose.theta * _FOREARM_TURN)
        X = np.arange(W, dtype=np.float32)[None, :] + (x0 + 0.5 - cx)
        Y = np.arange(H, dtype=np.float32)[:, None] + (y0 + 0.5 - cy)
        qx = (X * c + Y * s) * (sx / u)                     # the forearm's frame, at the cuff
        qy = (-X * s + Y * c) / u
        cs, sn = math.cos(_CUFF_SLANT), math.sin(_CUFF_SLANT)
        qx, qy = qx * cs + qy * sn, -qx * sn + qy * cs     # the cuff's own frame
        r = 0.18
        dx = np.abs(qx) - (_CUFF_W - r)
        dy = np.abs(qy - 5.0) - (5.0 - r)
        d = (np.hypot(np.maximum(dx, 0), np.maximum(dy, 0)) + np.minimum(np.maximum(dx, dy), 0) - r) * u
        img = np.empty((H, W, 4), np.uint8)
        img[..., :3] = _SLEEVE
        img[..., 3] = (np.clip(0.5 - d, 0.0, 1.0) * 255).astype(np.uint8)
        out = pygame.image.frombuffer(img.tobytes(), (W, H), "RGBA")
        self._sleeve_cache[pose.side] = (key, out)
        return out

    def _render(self, pose: HandPose):
        u, q = pose.u, self._Q
        sx = 1.0 if pose.side == "right" else -1.0
        c, s = math.cos(pose.theta), math.sin(pose.theta)
        ox, oy = pose.origin

        def world(lx, ly):
            lx *= sx
            return ox + (lx * c - ly * s) * u, oy + (lx * s + ly * c) * u

        limbs = pose.fingers                                  # finger → (points, radii, tones), px

        # the box to draw in: the hand down to its cuff, the sleeve down to the canvas edge;
        # its corner sits on the coarse grid so the cached palm lines up with it
        pts = []
        for a, ra, b, rb in _PALM:
            for (lx, ly), r in ((a, ra), (b, rb)):
                wx, wy = world(lx, ly)
                pts += [(wx - r * u, wy - r * u), (wx + r * u, wy + r * u)]
        for chain, radii, *_ in limbs.values():
            for (px_, py_), r in zip(chain, radii):
                pts += [(px_ - r, py_ - r), (px_ + r, py_ + r)]
        cuff = [world(_CUFF[0] + dx, _CUFF[1] + 0.4) for dx in (-_CUFF_W - 0.1, _CUFF_W + 0.1)]
        pts += cuff
        pad = u * 0.25 + 6
        x0 = int(math.floor((min(p[0] for p in pts) - pad) / q)) * q
        y0 = int(math.floor((min(p[1] for p in pts) - pad) / q)) * q
        x1 = max(p[0] for p in pts) + pad
        y1 = pose.bottom + 2
        w3, h3 = int((x1 - x0) / q) + 2, int((y1 - y0) / q) + 2
        W, H = w3 * q, h3 * q

        # The shape is worked out on every fourth pixel and interpolated; the edge stays
        # exact (see the distance code below).
        X = np.broadcast_to((np.arange(w3, dtype=np.float32)[None, :] + 0.5) * q + x0, (h3, w3))
        Y = np.broadcast_to((np.arange(h3, dtype=np.float32)[:, None] + 0.5) * q + y0, (h3, w3))

        # the back of the hand, from the cache
        d_palm = np.full((h3, w3), 1e4, np.float32)
        px0, py0, P = self._palm(pose, world)
        ix, iy = (px0 - x0) // q, (py0 - y0) // q
        tx0, ty0 = max(0, ix), max(0, iy)
        tx1, ty1 = min(w3, ix + P.shape[1]), min(h3, iy + P.shape[0])
        if tx1 > tx0 and ty1 > ty0:
            d_palm[ty0:ty1, tx0:tx1] = P[ty0 - iy:ty1 - iy, tx0 - ix:tx1 - ix]

        # fingers: each phalanx a rounded cone, computed only near its finger
        d_part, box_part = {}, {}
        for f, (chain, radii, *_) in limbs.items():
            m = 3 + 2 * q
            fx0 = max(0, int((min(p[0] - r for p, r in zip(chain, radii)) - m - x0) / q))
            fx1 = min(w3, int((max(p[0] + r for p, r in zip(chain, radii)) + m - x0) / q) + 2)
            fy0 = max(0, int((min(p[1] - r for p, r in zip(chain, radii)) - m - y0) / q))
            fy1 = min(h3, int((max(p[1] + r for p, r in zip(chain, radii)) + m - y0) / q) + 2)
            d = np.full((h3, w3), 1e4, np.float32)
            if fx1 > fx0 and fy1 > fy0:
                sl = (slice(fy0, fy1), slice(fx0, fx1))
                for a, b, ra, rb in zip(chain, chain[1:], radii, radii[1:]):
                    np.minimum(d[sl], _sd_round_cone(X[sl], Y[sl], a[0], a[1], b[0], b[1], ra, rb),
                               out=d[sl])
                box_part[f] = (fy0, fy1, fx0, fx1)
            d_part[f] = d
        d_thumb = d_part.get(1, np.full((h3, w3), 1e4, np.float32))
        d_fing = np.full((h3, w3), 1e4, np.float32)
        for f in (2, 3, 4, 5):
            if f in d_part:
                d_fing = np.minimum(d_fing, d_part[f])
        # one silhouette: the thumb blends softly into the palm, the fingers with their webs
        dist = _smin(_smin(d_palm, d_thumb, _THUMB_BLEND * u), d_fing, _FINGER_BLEND * u)

        # Layers, top to bottom: the fingers (highest first), the palm, the thumb. Only the
        # outlines come from the coarse grid (as exact distances); everything inside is
        # worked out per pixel from the bones: each phalanx's tone with a crisp fold line at
        # its joint, the coloured fill, and a thin contact shadow wherever a part lies
        # clearly higher than the one beneath (not where neighbours merely touch).
        acc = np.array(ACCENT[pose.side], np.float32)
        skin = np.array(pose.skin, np.float32)
        tinted = acc * 0.82 + 255 * 0.18
        # only where fingers are is there anything but plain skin: work in that box
        boxes = [b for b in box_part.values() if b is not None]
        uy0 = min(b[0] for b in boxes) * q if boxes else 0
        uy1 = max(b[1] for b in boxes) * q if boxes else 0
        ux0 = min(b[2] for b in boxes) * q if boxes else 0
        ux1 = max(b[3] for b in boxes) * q if boxes else 0
        rgb = np.empty((uy1 - uy0, ux1 - ux0, 3), np.float32)
        rgb[:] = skin                                         # the palm and the webs: plain skin
        clear = np.ones((uy1 - uy0, ux1 - ux0), np.float32)   # how much still shows through
        band = float(min(7.0, max(2.5, 0.10 * u)))            # the contact shadow's width
        near = np.clip(1.0 - ((128.0 - np.arange(256)) / 16.0) / band, 0.0, 1.0)
        shadow = (1.0 - 0.22 * near * near).astype(np.float32)  # distance code → shade
        lw = max(0.7, u / 50.0)                               # a crease's width
        drawn = []                                            # parts above: (y, x, code, height)
        for part in (*pose.order, 1):                         # the palm lies under the fingers
            if box_part.get(part) is None:
                continue
            by0, by1, bx0, bx1 = box_part[part]
            data = np.zeros((by1 - by0, bx1 - bx0, 4), np.uint8)
            data[..., 0] = np.clip(128.0 - d_part[part][by0:by1, bx0:bx1] * 16.0, 0, 255)
            code = np.ascontiguousarray(_upscale(data, q)[..., 0])
            hf, wf = code.shape
            fy0, fx0 = by0 * q, bx0 * q
            fsl = (slice(fy0 - uy0, fy0 - uy0 + hf), slice(fx0 - ux0, fx0 - ux0 + wf))
            PX = np.arange(wf, dtype=np.float32)[None, :] + np.float32(x0 + fx0 + 0.5)
            PY = np.arange(hf, dtype=np.float32)[:, None] + np.float32(y0 + fy0 + 0.5)
            chain, radii, tones, zs = limbs[part]
            tone, height = _phalanx_fields(PX, PY, chain, radii, tones, zs)
            over = np.zeros((hf, wf), np.uint8)
            for gy0, gx0, gcode, gh in drawn:
                oy0, oy1 = max(fy0, gy0), min(fy0 + hf, gy0 + gcode.shape[0])
                ox0, ox1 = max(fx0, gx0), min(fx0 + wf, gx0 + gcode.shape[1])
                if oy1 <= oy0 or ox1 <= ox0:
                    continue
                a = (slice(oy0 - fy0, oy1 - fy0), slice(ox0 - fx0, ox1 - fx0))
                b = (slice(oy0 - gy0, oy1 - gy0), slice(ox0 - gx0, ox1 - gx0))
                if float(gh[b].max()) < float(height[a].min()) + 2.0:
                    continue                                  # nowhere clearly higher
                lift = np.clip((gh[b] - height[a] - 2.0) / 4.0, 0.0, 1.0)   # how clearly higher
                np.maximum(over[a], (gcode[b] * lift).astype(np.uint8), out=over[a])
            shade = (tone * shadow.take(over))[..., None]
            g = pose.glow.get(part, 0.0)
            if g > 0.01:
                # the finger that plays next takes its hand's colour, filling it from the
                # tip like a liquid rising (never a faded, greyish mix); a press fills more
                b0, t0 = chain[0], chain[-1]
                vx, vy = t0[0] - b0[0], t0[1] - b0[1]
                l2 = vx * vx + vy * vy or 1.0
                along = ((PX - b0[0]) * vx + (PY - b0[1]) * vy) * np.float32(1.0 / l2)
                reach_f = ((0.40 if part == 1 else 0.58) + 0.14 * pose.press.get(part, 0.0)) * g
                fill = np.clip((along - (1.0 - reach_f)) * np.float32(l2 ** 0.5) + 0.5, 0.0, 1.0)
                col = (skin + (tinted - skin) * fill[..., None]) * shade
            else:
                col = skin * shade
            if pose.details and pose.details.get(part):
                col = _draw_details(col, pose.details[part], x0 + fx0, y0 + fy0, lw)
            c = _COVERAGE_F.take(code) * clear[fsl]
            rgb[fsl] += (col - skin) * c[..., None]
            clear[fsl] -= c
            drawn.append((fy0, fx0, code, height))

        # the outline: the hand's distance up to full resolution, its edge exact
        data = np.zeros((h3, w3, 4), np.uint8)
        data[..., 0] = np.clip(128.0 - dist * 16.0, 0, 255)
        alpha = _COVERAGE.take(_upscale(data, q)[..., 0])
        img = np.empty((H, W, 4), np.uint8)
        np.clip(rgb, 0, 255, out=rgb)
        img[..., :3] = np.asarray(pose.skin, np.uint8)
        img[uy0:uy1, ux0:ux1, :3] = rgb
        img[..., 3] = alpha
        out = pygame.image.frombuffer(img.tobytes(), (W, H), "RGBA")
        # the sleeve over the wrist
        out.blit(self._sleeve(pose, x0, y0, W, H), (0, 0))
        if pose.alpha < 0.999:
            out.set_alpha(int(255 * pose.alpha))
        if pygame.display.get_surface() is not None:
            out = out.convert_alpha()        # the screen's own pixel format blits much faster
        return out, (x0, y0)


# ── Animation ─────────────────────────────────────────────────────────────────

def _spring(value=0.0, response=0.3, damping=0.85):
    from pylay.core.physics import Spring
    return Spring(value=value, response=response, damping_fraction=damping)


def _rest_joints(f):
    return tuple(A.THUMB_REST[k] for k in ("rad", "palm", "mcp", "ip")) if f == 1 else _RELAXED[f]


class _AnimatedHand:
    """One hand's springs: where the hand is, how it is turned and held, and every joint of
    every finger. The joints move, never the lengths, so the fingers keep their size."""

    def __init__(self, side: str):
        self.side = side
        self.P = Pose(side)
        self.hx = _spring(0.0, 0.30, 0.86)
        self.hy = _spring(_KNUCKLE_DEPTH, 0.30, 0.90)
        self.th = _spring(0.0, 0.34, 0.90)
        self.hz = _spring(_HZ, 0.30, 0.90)
        self.j = {f: [_spring(v, 0.16, 0.86) for v in _rest_joints(f)] for f in range(1, 6)}
        self.dj = {f: [_spring(0.0, 0.16, 0.86) for _ in _rest_joints(f)] for f in range(1, 6)}
        self.press = {f: _spring(0.0, 0.07, 0.95) for f in range(1, 6)}
        self.glow = {f: _spring(0.0, 0.14, 1.0) for f in range(1, 6)}
        self.alpha = _spring(0.0, 0.30, 1.0)
        self.lift = 0.0
        self.placed = False
        self.held: dict[int, int] = {}                      # finger → key it is still holding
        self.focus: dict[int, int] = {}                     # finger → key of the step it aims at
        self.focus_step = -1
        self.front = 0.48
        self._solved_for = None

    def _springs(self):
        yield from (self.hx, self.hy, self.th, self.hz)
        for f in range(1, 6):
            yield from self.j[f]
            yield from self.dj[f]

    def place(self, target=False):
        sp = (self.hx, self.hy, self.th, self.hz)
        return tuple(s.target if target else s.value for s in sp)

    def aim(self, fingers: dict[int, int], glowing: bool, active: frozenset, step: int,
            black_depth: float, urgent: bool = False):
        """Point the hand at the keys of one step (finger → MIDI).

        A hand cannot leave keys it is still holding: while they are down it stays, and the
        next fingers reach towards their keys as far as their joints allow. Only when the
        next note is due (urgent) does it let go and leap."""
        if step != self.focus_step:
            for f, m in self.focus.items():                 # fingers that just played keep their key
                self.held[f] = m
            self.focus, self.focus_step = dict(fingers), step
        for f in list(self.held):
            if self.held[f] not in active:
                del self.held[f]

        want = {f: _key_point(m, black_depth, f, self.front) for f, m in fingers.items()}
        key = (tuple(sorted(want.items())), tuple(sorted(self.held.items())),
               round(black_depth, 2), urgent)
        if want and key != self._solved_for:
            self._solved_for = key
            prev = self.place(target=True) if self.placed else None
            held = {f: _key_point(m, black_depth, f, self.front)
                    for f, m in self.held.items() if f not in want}
            place, joints = solve_cached(self.side, want, prev, black_depth)
            if held:
                both = {**held, **want}
                if all(self._reaches(f, place, p) for f, p in held.items()):
                    joints = hand_joints(self.side, place, both, black_depth)   # keep holding them
                else:
                    place2 = solve_hand(self.side, both, prev)
                    if all(self._reaches(f, place2, p) for f, p in both.items()):
                        place, joints = place2, hand_joints(self.side, place2, both, black_depth)
                    elif prev is not None and not urgent:
                        place = prev                        # wait for the keys to be let go
                        both = {f: p for f, p in both.items() if self._reaches(f, place, p)}
                        joints = hand_joints(self.side, place, both, black_depth)
            for sp, v in zip((self.hx, self.hy, self.th, self.hz), place):
                sp.target = v
            for f, (up, down) in joints.items():
                for k, (u_, d_) in enumerate(zip(up, down)):
                    self.j[f][k].target = u_
                    self.dj[f][k].target = d_ - u_
            if not self.placed:
                self.snap()

        for f in range(1, 6):
            down = self.held.get(f, fingers.get(f))
            self.press[f].target = 1.0 if down is not None and down in active else 0.0
            g = 1.0 if (glowing and f in fingers) else 0.0
            self.glow[f].target = g
            if g == 0.0:
                self.glow[f].snap_to(0.0)                   # the colour leaves with its note, at once

    def _reaches(self, f, place, point) -> bool:
        return reach_error(self.side, place, f, point) < 3.5

    def joints(self, f: int):
        """Finger f's joints now: where it aims, pressed as far as its key is down; while
        the hand travels, the fingers it is not pressing with lift and curl a little."""
        p = self.press[f].value
        v = [s.value + p * d.value for s, d in zip(self.j[f], self.dj[f])]
        if f != 1:
            free = 1.0 - p
            v[1] -= 10.0 * self.lift * free
            v[2] += 8.0 * self.lift * free
        return tuple(v)

    def tip(self, f: int) -> tuple[float, float]:
        """Where fingertip f is now, in key space."""
        return tip_point(self.side, self.place(), f, self.joints(f))

    def tip_x(self, f: int) -> float:
        return self.tip(f)[0]

    def save(self) -> dict:
        return {"h": self.place(), "j": {f: [s.value for s in self.j[f]] for f in range(1, 6)}}

    def restore(self, st: dict):
        """Start where a previous page left this hand: it glides on from there."""
        for sp, v in zip((self.hx, self.hy, self.th, self.hz), st["h"]):
            sp.snap_to(v)
        for f in range(1, 6):
            for sp, v in zip(self.j[f], st["j"][f]):
                sp.snap_to(v)
        self.alpha.snap_to(1.0)
        self.placed = True

    def snap(self):
        self.placed = True
        for sp in self._springs():
            sp.snap_to(sp.target)

    def update(self, dt: float):
        before = (self.hx.value, self.hy.value)
        for sp in (*self._springs(), self.alpha, *self.press.values(), *self.glow.values()):
            sp.update(dt)
        speed = math.hypot(self.hx.value - before[0], self.hy.value - before[1]) / max(dt, 1e-3)
        self.lift += (min(1.0, speed / 9.0) - self.lift) * min(1.0, dt * 10)

    def pose(self, kb: KeyboardGeometry, skin: tuple) -> HandPose:
        place = self.place()
        px_mm = K * kb.white_w
        fingers, height, details = {}, {}, {}

        def proj(p):
            return kb.to_px(*self.P.from_mm(place, p))

        for f in range(1, 6):
            joints = self.joints(f)
            pts, radii = _segments(f, joints)
            # seen from above, what lies lower is a little further away, so a little smaller
            radii = [r * (1.0 + _PERSPECTIVE * (p[2] + place[3] - _HZ)) for p, r in zip(pts, radii)]
            tones = []
            for a, b in zip(pts, pts[1:]):
                d = math.dist(a, b) or 1.0
                k = 0.07 if f == 1 else 0.12                           # the thumb lies on its side
                tones.append(1.0 - k * max(0.0, (a[2] - b[2]) / d))     # pointing down: darker
            if f == 1:
                tones[0] = tones[1] = 1.0                              # the thumb grows out of the
                #                                                        palm: no fold until its tip
            if f != 1:
                r = radii[-1] * (1.0 + 0.05 * self.press[f].value)     # the pad flattens on its key
                radii = radii[:-1] + [r]
            fingers[f] = (tuple(proj(p) for p in pts), tuple(r * px_mm for r in radii), tuple(tones),
                          tuple(p[2] for p in pts))
            details[f] = _details(f, joints, proj, px_mm)
            height[f] = sum(p[2] for p in pts[1:]) / (len(pts) - 1)
        # what lies higher is drawn on top; the thumb lies under the hand
        order = tuple(sorted((2, 3, 4, 5), key=lambda f: -height[f]))
        hx, hy, th, _ = place
        return HandPose(side=self.side, u=kb.white_w, origin=kb.to_px(hx, hy), theta=th,
                        fingers=fingers, order=order, details=details,
                        press={f: self.press[f].value for f in range(1, 6)},
                        glow={f: self.glow[f].value for f in range(1, 6)},
                        alpha=self.alpha.value, bottom=kb.bottom, skin=skin)


# Where the hands were when their page closed, so the next page (the next practice
# section) continues from there instead of snapping
_last_pose: dict = {}

# In timed play, how soon before its next note a hand may let go of held keys and leap
_LEAP_TIME = 0.15


class HandsOverlay:
    """Both hands, following a fingering plan through a piece.

    plan: per step, {"right": {midi: finger}, "left": {midi: finger}}
    memory: a key (e.g. the song) under which the hands remember where they are
    skin: one of SKIN_TONES
    """

    def __init__(self, plan: list[dict], memory=None, skin: str = DEFAULT_SKIN):
        self.plan = plan
        self.skin = SKIN_TONES.get(skin, SKIN_TONES[DEFAULT_SKIN])
        self.hands = {s: _AnimatedHand(s) for s in ("right", "left")}
        self._renderer = HandRenderer()
        self._memory = memory
        self._black_depth = -1.0
        self._waited: dict = {}
        self._presolved = None
        used = {s for st in plan for s, fm in st.items() if fm}
        if used:
            A.prepare()                                     # the thumb's table, in the background
        for s, h in self.hands.items():
            h.alpha.target = 1.0 if s in used else 0.0
        saved = _last_pose.get(memory) if memory is not None else None
        if saved:
            for s, h in self.hands.items():
                if s in saved and s in used:
                    h.restore(saved[s])

    def _fingers(self, step: int, side: str) -> dict[int, int]:
        if 0 <= step < len(self.plan):
            return {f: m for m, f in self.plan[step].get(side, {}).items()}
        return {}

    def update(self, dt: float, step: int, active: frozenset, lead: float = 0.0,
               step_time: float = 0.0):
        """step: the step the player is on. In timed play, lead is how far through that step
        we are (0..1) and step_time how long it lasts (seconds): late in a step the hands
        already move towards the next one."""
        if self._memory is not None:
            _last_pose[self._memory] = {s: h.save() for s, h in self.hands.items() if h.placed}
        timed = step_time > 0
        remaining = (1.0 - lead) * step_time if timed else float("inf")
        for side, hand in self.hands.items():
            fingers = self._fingers(step, side)
            target, glowing = step, bool(fingers)
            if not fingers or (timed and lead > 0.7):
                # prepare: move towards the next step this hand plays in
                for j in range(step + 1, min(len(self.plan), step + 64)):
                    if self._fingers(j, side):
                        if not fingers or j == step + 1:
                            target, glowing = j, False
                        break
            if target != step:
                fingers = self._fingers(target, side)
            urgent = timed and (target == step or (target == step + 1 and remaining < _LEAP_TIME))
            hand.aim(fingers, glowing, active, target, self._black_depth, urgent)
            hand.update(dt)
        self._presolve(step)

    def _presolve(self, step: int):
        """Have the next hand positions solved in the background, before they are needed."""
        if step == self._presolved:
            return
        self._presolved = step
        for j in range(step + 1, min(len(self.plan), step + 8)):
            for side, hand in self.hands.items():
                fingers = self._fingers(j, side)
                if fingers and hand.placed:
                    want = {f: _key_point(m, self._black_depth, f, hand.front) for f, m in fingers.items()}
                    solve_ahead(side, want, hand.place(target=True), self._black_depth)

    def colour_of(self, midi: int, step: int):
        """The colour of the hand that plays this key in this step, if any."""
        if 0 <= step < len(self.plan):
            for side in ("right", "left"):
                if midi in self.plan[step].get(side, {}):
                    return ACCENT[side]
        return None

    def keys_needed(self, step: int, ahead: int = 6) -> set[int]:
        out = set()
        for j in range(max(0, step), min(len(self.plan), step + ahead)):
            for fm in self.plan[j].values():
                out.update(fm)
        return out

    def draw(self, surface: pygame.Surface, kb: KeyboardGeometry, alpha: float = 1.0):
        if alpha <= 0.01:
            return
        self._black_depth = kb.black_depth
        for h in self.hands.values():
            h.front = kb.front
        poses = []
        for side in ("left", "right"):
            hand = self.hands[side]
            if hand.alpha.value <= 0.01 or not hand.placed:
                continue
            pose = hand.pose(kb, self.skin)
            pose.alpha *= alpha
            poses.append(pose)
        # at most one hand is drawn anew per frame (the one that has waited longer); the
        # other keeps its last image for that frame, moving with the hand
        stale = [p for p in poses if not self._renderer.is_current(p)]
        allowed = None
        if stale:
            stale.sort(key=lambda p: self._waited.get(p.side, 0), reverse=True)
            allowed = stale[0].side
            for p in stale:
                self._waited[p.side] = 0 if p.side == allowed else self._waited.get(p.side, 0) + 1
        rendered = [self._renderer.render(pose, may_draw=(pose.side == allowed or
                                                           pose.side not in self._renderer._last))
                    for pose in poses]
        for out in rendered:
            if out:
                surface.blit(*out)

