"""A hand's anatomy and how it can move, in millimetres (an adult right hand, about 189 mm
long). Bones have fixed lengths and every joint its own range, so a finger can only reach
as far as its joints allow: it bends, spreads a little, and never stretches.

Frame: x towards the little finger (ulnar), y towards the fingertips (distal), z up from
the back of the hand (dorsal). The left hand is its mirror image.

  * Fingers: metacarpal, then three phalanges. The knuckle (MCP) bends and spreads; the
    collateral ligaments tighten as it bends, so a bent finger can hardly spread. The
    middle joint (PIP) bends; the end joint (DIP) follows it at about two thirds (the
    oblique retinacular ligament). Neighbouring fingers share flexor bellies and the
    juncturae tendinum, so a finger that moves drags its neighbours a little.
  * Thumb: a saddle joint at the wrist (CMC) that swings it out (radial abduction) and
    down in front of the palm (palmar abduction), turning it as it goes (conjunct
    rotation), then two hinges (MCP, IP).
"""
from __future__ import annotations

import math

import numpy as np

D = math.pi / 180

# ── anatomy (after a standard adult hand) ──
FINGERS = {
    2: dict(base=(-11.0, 17.0, 0.0), ang=-7.0, mc=68.0, p=(40.0, 23.0, 17.0), skin=9.3, rest=0.0,
            mcp=(-25.0, 90.0), pip=(0.0, 110.0), dip=(-5.0, 80.0), abd=(-12.0, 20.0)),
    3: dict(base=(0.0, 18.5, 0.0), ang=0.0, mc=64.5, p=(45.0, 27.0, 19.0), skin=9.6, rest=0.0,
            mcp=(-20.0, 90.0), pip=(0.0, 110.0), dip=(-5.0, 80.0), abd=(-15.0, 15.0)),
    4: dict(base=(10.0, 17.0, 0.0), ang=6.0, mc=58.0, p=(42.0, 26.0, 19.0), skin=9.0, rest=-1.0,
            mcp=(-20.0, 95.0), pip=(0.0, 110.0), dip=(-5.0, 85.0), abd=(-15.0, 12.0)),
    5: dict(base=(19.0, 14.0, 0.0), ang=13.0, mc=53.0, p=(33.0, 19.0, 17.0), skin=8.0, rest=-3.0,
            mcp=(-25.0, 95.0), pip=(0.0, 115.0), dip=(-5.0, 90.0), abd=(-30.0, 8.0)),
}
THUMB = dict(base=(-23.0, 11.0, -5.0), mc=46.0, p=(32.0, 24.0), skin=10.8,
             rad=(0.0, 60.0), palm=(0.0, 75.0), mcp=(-10.0, 60.0), ip=(-20.0, 80.0))
DIP_LINK = 2.0 / 3.0

# how much a finger's flexion drags each neighbour (rows: the moving finger)
ENSLAVE = {2: {3: 0.16, 4: 0.05, 5: 0.02}, 3: {2: 0.20, 4: 0.30, 5: 0.10},
           4: {2: 0.07, 3: 0.36, 5: 0.42}, 5: {2: 0.03, 3: 0.13, 4: 0.48}}
# juncturae tendinum: the knuckles of these neighbours cannot bend further apart than this
JUNCTURAE = ((3, 4, 50.0), (4, 5, 45.0))


def _rz(a):
    c, s = math.cos(a * D), math.sin(a * D)
    return np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])


def _rx(a):
    c, s = math.cos(a * D), math.sin(a * D)
    return np.array([[1.0, 0.0, 0.0], [0.0, c, -s], [0.0, s, c]])


def _ry(a):
    c, s = math.cos(a * D), math.sin(a * D)
    return np.array([[c, 0.0, s], [0.0, 1.0, 0.0], [-s, 0.0, c]])


def _flex(a):
    """Flexion turns a segment palmward (−z)."""
    return _rx(-a)


def head(f: int):
    """The knuckle (metacarpal head) of finger f."""
    g = FINGERS[f]
    a = -g["ang"] * D
    return (g["base"][0] - math.sin(a) * g["mc"], g["base"][1] + math.cos(a) * g["mc"], g["base"][2])


def abd_limits(f: int, mcp: float):
    """Side-to-side range of a finger: the collateral ligaments tighten as the knuckle bends."""
    g = FINGERS[f]
    k = 1.0 - 0.85 * min(1.0, max(0.0, mcp / 90.0))
    return g["abd"][0] * k, g["abd"][1] * k


def finger_points(f: int, abd: float, mcp: float, pip: float, dip: float | None = None):
    """Knuckle, PIP, DIP and tip of finger f, and how steeply each phalanx points down."""
    g = FINGERS[f]
    if dip is None:
        dip = DIP_LINK * max(0.0, pip)
    yaw = (-g["ang"] + g["rest"] + abd) * D
    sy, cy = math.sin(yaw), math.cos(yaw)
    hx, hy, hz = head(f)
    pts = [(hx, hy, hz)]
    phis = []
    phi = 0.0
    x, y, z = hx, hy, hz
    for L, a in zip(g["p"], (mcp, pip, dip)):
        phi += a * D
        phis.append(phi)
        c, s = math.cos(phi), math.sin(phi)
        x, y, z = x - sy * c * L, y + cy * c * L, z - s * L
        pts.append((x, y, z))
    return pts, phis


def _chain_end(f: int, pip: float):
    """Where the tip is, from the knuckle, in the finger's own plane (forward, up), with the
    knuckle straight."""
    g = FINGERS[f]
    dip = min(g["dip"][1], DIP_LINK * pip)
    a1, a2 = pip * D, (pip + dip) * D
    p0, p1, p2 = g["p"]
    return (p0 + p1 * math.cos(a1) + p2 * math.cos(a2),
            -(p1 * math.sin(a1) + p2 * math.sin(a2)))


_SPANS: dict = {}


def _pip_for(f: int, rho: float) -> float:
    """The PIP angle at which finger f's tip is rho from its knuckle (the span shrinks as
    the finger curls), from a table, between the joint's limits."""
    if f not in _SPANS:
        lo, hi = FINGERS[f]["pip"]
        pips = [lo + (hi - lo) * i / 460 for i in range(461)]
        _SPANS[f] = (pips, [math.hypot(*_chain_end(f, a)) for a in pips])
    pips, spans = _SPANS[f]
    if rho >= spans[0]:
        return pips[0]                                      # as straight as it goes
    if rho <= spans[-1]:
        return pips[-1]
    lo, hi = 0, len(spans) - 1                              # spans fall as the index grows
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if spans[mid] > rho:
            lo = mid
        else:
            hi = mid
    t = (spans[lo] - rho) / (spans[lo] - spans[hi])
    return pips[lo] + (pips[hi] - pips[lo]) * t


def solve_finger(f: int, target):
    """Joint angles that bring finger f's tip to `target` (hand frame, mm), as near as its
    joints allow. Returns ((abd, mcp, pip), how far the tip stays from the target)."""
    g = FINGERS[f]
    hx, hy, hz = head(f)
    vx, vy, vz = target[0] - hx, target[1] - hy, target[2] - hz
    yaw = math.atan2(-vx, vy) / D
    abd = yaw + g["ang"] - g["rest"]
    h = math.hypot(vx, vy)
    rho = math.hypot(h, vz)
    pip = _pip_for(f, rho)
    ex, ez = _chain_end(f, pip)
    mcp = (math.atan2(ez, ex) - math.atan2(vz, h)) / D
    mcp = min(g["mcp"][1], max(g["mcp"][0], mcp))
    alo, ahi = abd_limits(f, mcp)
    abd = min(ahi, max(alo, abd))
    tip = finger_points(f, abd, mcp, pip)[0][-1]
    err = math.dist(tip, target)
    return (abd, mcp, pip), err


# ── thumb ──
THUMB_REST = dict(rad=10.0, palm=15.0, mcp=8.0, ip=10.0)    # metacarpal angled down, the
#                                                               thumb lying along its key, as on a piano


def thumb_points(rad: float, palm: float, mcp: float, ip: float):
    """Base, MCP, IP and tip of the thumb, and each bone's frame: (direction, back)."""
    psi = -(38.0 + 0.62 * palm + 0.15 * max(0.0, 30.0 - rad)) * D   # conjunct rotation
    a, p = (7.0 + rad) * D, palm * D
    ca, sa, cp, sp = math.cos(a), math.sin(a), math.cos(p), math.sin(p)

    def rz(v):
        return (ca * v[0] - sa * v[1], sa * v[0] + ca * v[1], v[2])

    y = rz((0.0, cp, -sp))                                  # the metacarpal's direction …
    z = rz((math.sin(psi), sp * math.cos(psi), cp * math.cos(psi)))   # … and its back
    base = THUMB["base"]
    pts, frames = [base], []
    x0 = base
    for L, bend in ((THUMB["mc"], mcp), (THUMB["p"][0], ip), (THUMB["p"][1], None)):
        x0 = (x0[0] + y[0] * L, x0[1] + y[1] * L, x0[2] + y[2] * L)
        pts.append(x0)
        frames.append((y, z))
        if bend is not None:                                # the next joint flexes palmward
            c, s_ = math.cos(bend * D), math.sin(bend * D)
            y, z = (tuple(c * u - s_ * w for u, w in zip(y, z)),
                    tuple(s_ * u + c * w for u, w in zip(y, z)))
    return pts, frames


def _thumb_tips(rad, palm, mcp, ip):
    """thumb_points' tip for arrays of joint angles (vectorised)."""
    n = rad.shape[0]

    def rz(a):
        c, s = np.cos(a * D), np.sin(a * D)
        R = np.zeros((n, 3, 3))
        R[:, 0, 0], R[:, 0, 1], R[:, 1, 0], R[:, 1, 1], R[:, 2, 2] = c, -s, s, c, 1
        return R

    def fx(a):
        c, s = np.cos(-a * D), np.sin(-a * D)
        R = np.zeros((n, 3, 3))
        R[:, 0, 0], R[:, 1, 1], R[:, 1, 2], R[:, 2, 1], R[:, 2, 2] = 1, c, -s, s, c
        return R

    def ry(a):
        c, s = np.cos(a * D), np.sin(a * D)
        R = np.zeros((n, 3, 3))
        R[:, 0, 0], R[:, 0, 2], R[:, 1, 1], R[:, 2, 0], R[:, 2, 2] = c, s, 1, -s, c
        return R

    psi = -(38.0 + 0.62 * palm + 0.15 * np.maximum(0.0, 30.0 - rad))
    R0 = rz(7.0 + rad) @ fx(palm) @ ry(psi)
    R1 = R0 @ fx(mcp)
    R2 = R1 @ fx(ip)
    y = lambda R, L: R[:, :, 1] * L                         # noqa: E731
    return np.array(THUMB["base"]) + y(R0, THUMB["mc"]) + y(R1, THUMB["p"][0]) + y(R2, THUMB["p"][1])


def thumb_comfort(rad, palm, mcp, ip):
    r = THUMB_REST
    return (((rad - r["rad"]) / 28.0) ** 2 + ((palm - r["palm"]) / 30.0) ** 2
            + ((mcp - r["mcp"]) / 30.0) ** 2 + ((ip - r["ip"]) / 35.0) ** 2)


class _ThumbTable:
    """Where the thumb's tip can go, sampled once over all its joint angles: for each small
    cube of space, the most comfortable way to get there, and how far away the nearest
    reachable cube is."""
    CELL = 3.0
    LO = np.array([-150.0, -40.0, -120.0])
    HI = np.array([60.0, 140.0, 30.0])

    def __init__(self):
        g = np.meshgrid(np.arange(0.0, 60.1, 4.0), np.arange(0.0, 75.1, 5.0),
                        np.arange(-10.0, 60.1, 5.0), np.arange(-20.0, 80.1, 5.0), indexing="ij")
        rad, palm, mcp, ip = (a.ravel() for a in g)
        tips = _thumb_tips(rad, palm, mcp, ip)
        cost = thumb_comfort(rad, palm, mcp, ip)
        self.shape = tuple(int(v) for v in np.ceil((self.HI - self.LO) / self.CELL))
        idx = np.floor((tips - self.LO) / self.CELL).astype(int)
        ok = np.all((idx >= 0) & (idx < np.array(self.shape)), axis=1)
        idx, cost_ok, which = idx[ok], cost[ok], np.nonzero(ok)[0]
        cell = np.ravel_multi_index(idx.T, self.shape)
        order = np.lexsort((cost_ok, cell))
        cell_s = cell[order]
        first = np.r_[True, cell_s[1:] != cell_s[:-1]]
        best_cells = cell_s[first]
        best = which[order][first]
        size = int(np.prod(self.shape))
        self.cost = np.full(size, 4.0)
        self.cost[best_cells] = cost[best]
        self.joints = np.zeros((size, 4))
        self.joints[best_cells] = np.stack([rad[best], palm[best], mcp[best], ip[best]], axis=1)
        filled = np.zeros(size, bool)
        filled[best_cells] = True
        # how far to the nearest reachable cube (a chamfer distance in mm, up to 45 mm;
        # lookups add the rest), and which cube that is
        dist = np.where(filled, 0.0, 1e9).reshape(self.shape)
        src = np.where(filled, np.arange(size), -1).reshape(self.shape)

        def cut(d, n):
            return (slice(d, n), slice(0, n - d)) if d >= 0 else (slice(0, n + d), slice(-d, n))

        steps = [(dx, dy, dz) for dx in (-1, 0, 1) for dy in (-1, 0, 1) for dz in (-1, 0, 1)
                 if (dx, dy, dz) != (0, 0, 0)]
        for _ in range(15):
            changed = False
            for o in steps:
                w = self.CELL * math.sqrt(sum(v * v for v in o))
                to, fr = zip(*(cut(d, n) for d, n in zip(o, self.shape)))
                cand = dist[fr] + w
                better = cand < dist[to]
                if better.any():
                    changed = True
                    np.copyto(dist[to], cand, where=better)
                    np.copyto(src[to], src[fr], where=better)
            if not changed:
                break
        self.dist = dist.ravel()
        # an unreachable cube borrows the joints and comfort of its nearest reachable one
        has = src.ravel() >= 0
        self.joints[has] = self.joints[src.ravel()[has]]
        self.cost[has] = self.cost[src.ravel()[has]]

    def easiest(self, z):
        """Where the thumb's tip rests most comfortably at height z: (x, y), mm."""
        if not hasattr(self, "_easy"):
            cost = np.where(self.dist == 0, self.cost, np.inf).reshape(self.shape)
            self._easy = []
            for kz in range(self.shape[2]):
                sl = cost[:, :, kz]
                if np.isfinite(sl).any():
                    i, j = np.unravel_index(np.argmin(sl), sl.shape)
                    self._easy.append((self.LO[0] + (i + 0.5) * self.CELL, self.LO[1] + (j + 0.5) * self.CELL))
                else:
                    self._easy.append(None)
        kz = int(min(self.shape[2] - 1, max(0, (z - self.LO[2]) / self.CELL)))
        for dk in range(self.shape[2]):
            for k in (kz - dk, kz + dk):
                if 0 <= k < self.shape[2] and self._easy[k] is not None:
                    return self._easy[k]
        return (-50.0, 60.0)

    def lookup(self, p):
        """(comfort, distance out of reach in mm, joints) at point p, interpolated."""
        if not hasattr(self, "_flat"):
            self._flat = (self.cost.tolist(), self.dist.tolist())
        costs, dists = self._flat
        nx, ny, nz = self.shape
        idx, frac, outside = [], [], 0.0
        for v, lo, n in zip(p, self.LO, self.shape):
            f = (v - lo) / self.CELL - 0.5
            c = min(n - 1.001, max(0.0, f))
            outside += (f - c) ** 2
            i = int(c)
            idx.append(i)
            frac.append(c - i)
        (i, j, k), (tx, ty, tz) = idx, frac
        cost = dist = 0.0
        for di, wx in ((0, 1 - tx), (1, tx)):
            for dj, wy in ((0, 1 - ty), (1, ty)):
                base = ((i + di) * ny + (j + dj)) * nz + k
                for dk, wz in ((0, 1 - tz), (1, tz)):
                    w = wx * wy * wz
                    cost += w * costs[base + dk]
                    dist += w * dists[base + dk]
        dist += math.sqrt(outside) * self.CELL                  # beyond the table
        near = ((i + round(tx)) * ny + (j + round(ty))) * nz + k + round(tz)
        return cost, dist, self.joints[near]


_TABLE = None
_TABLE_LOCK = __import__("threading").Lock()


def thumb_table() -> _ThumbTable:
    global _TABLE
    if _TABLE is None:
        with _TABLE_LOCK:
            if _TABLE is None:
                _TABLE = _ThumbTable()
    return _TABLE


def prepare():
    """Build the thumb's table in the background, before the first hand needs it."""
    if _TABLE is None:
        __import__("threading").Thread(target=thumb_table, daemon=True).start()


def solve_thumb(target, start=None):
    """Thumb joint angles (rad, palm, mcp, ip) that bring its tip to `target`, as near as
    its joints allow, the most comfortable way. Returns (joints, distance left in mm)."""
    lim = [THUMB["rad"], THUMB["palm"], THUMB["mcp"], THUMB["ip"]]
    if start is None:
        start = thumb_table().lookup(target)[2]
    p = np.array(start, float)
    T = np.asarray(target, float)

    def clampv(v):
        return np.array([min(hi, max(lo, x)) for x, (lo, hi) in zip(v, lim)])

    def res(v):
        tip = np.array(thumb_points(*v)[0][-1])
        r = THUMB_REST
        prior = np.array([(v[0] - r["rad"]) / 28.0, (v[1] - r["palm"]) / 30.0,
                          (v[2] - r["mcp"]) / 30.0, (v[3] - r["ip"]) / 35.0]) * 0.15
        return np.concatenate([(tip - T) / 0.5, prior])

    p = clampv(p)
    lam, r0 = 1e-2, res(p)
    cost = float(r0 @ r0)
    for _ in range(25):
        J = np.empty((len(r0), 4))
        for k in range(4):
            dp = np.zeros(4)
            dp[k] = 1e-3
            J[:, k] = (res(p + dp) - r0) / 1e-3
        A, g = J.T @ J, J.T @ r0
        improved = False
        while lam < 1e7:
            q = clampv(p + np.linalg.solve(A + lam * np.diag(np.diag(A) + 1e-9), -g))
            r1 = res(q)
            c = float(r1 @ r1)
            if c < cost:
                step = np.max(np.abs(q - p))
                p, r0, cost, lam, improved = q, r1, c, max(1e-6, lam / 3), True
                break
            lam *= 4
        if not improved or step < 1e-3:
            break
    tip = thumb_points(*p)[0][-1]
    return tuple(float(v) for v in p), math.dist(tip, target)


_REST_THUMB: dict = {}


def rest_thumb(target):
    """solve_thumb, remembered for the few places a resting thumb goes."""
    key = tuple(round(v) for v in target)
    if key not in _REST_THUMB:
        _REST_THUMB[key] = solve_thumb(key)[0]
    return _REST_THUMB[key]
