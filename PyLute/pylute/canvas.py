"""
pylute.canvas — OpenGUI integration layer.

ScoreCanvas
    Draw target for ScrollableCanvas.

ScorePager
    Paged view using OpenGUI's PageRouter.  Each UI page = one A4 page of content.
    Page slots are ScrollableCanvas widgets so each page is independently scrollable
    when its content exceeds the viewport height.
    Pass a shared ScoreCanvas so the same loaded score drives both scroll and paged views.
"""

import math
import os
import pygame
from .score import _MT as _SCORE_MT


# ─────────────────────────────────────────────────────────── ScoreCanvas ────

class ScoreCanvas:
    """Bridges an pylute.Score to OpenGUI's ScrollableCanvas target API."""

    def __init__(self):
        self.score = None
        self.error: str = ""
        self.dirty: bool = False

    def load(self, path: str) -> bool:
        from .musicxml import load_musicxml
        path = path.strip()
        if not path:
            self.error = "No path given."
            return False
        if not os.path.isfile(path):
            self.error = f"File not found: {path}"
            self.score = None
            return False
        try:
            self.score = load_musicxml(path)
            self.error = ""
            self.dirty = True
            return True
        except Exception as exc:
            self.score = None
            self.error = str(exc)
            return False

    def content_height(self, canvas_w: int) -> int:
        if self.score is None:
            return 120
        return self.score.total_content_height(canvas_w)

    def draw(self, surface: pygame.Surface, rect: pygame.Rect):
        safe = rect.clip(surface.get_rect())
        if safe.width < 1 or safe.height < 1:
            return
        if self.score is None:
            self._draw_placeholder(surface, safe)
            return
        sub = surface.subsurface(safe)
        self.score.surface = sub
        for staff in self.score.staffs:
            staff.surface = sub
        if self.score.brace:
            self.score.brace.surface = sub
        sub.fill((255, 255, 255))
        self.score.draw()

    def _draw_placeholder(self, surface: pygame.Surface, rect: pygame.Rect):
        pygame.font.init()
        font = pygame.font.SysFont("Arial", 14)
        if self.error:
            lines = ["Error loading file:", self.error]
            color = (220, 60, 60)
        else:
            lines = ["No score loaded.", "Enter a MusicXML path and press Load."]
            color = (150, 150, 150)
        y = rect.centery - len(lines) * 11
        for line in lines:
            surf = font.render(line, True, color)
            surface.blit(surf, surf.get_rect(centerx=rect.centerx, y=y))
            y += 22


# ──────────────────────────────────────────────────────── paged internals ────

class _ScoreSlice:
    """
    ScrollableCanvas target for one A4 page in the PageRouter.
    Blits its A4-page slice of the shared offscreen.
    """

    def __init__(self, pager: "ScorePager", page_idx: int):
        self.pager    = pager
        self.page_idx = page_idx
        self.dirty    = False   # ScrollableCanvas checks this

    def content_height(self, canvas_w: int) -> int:
        """Height of this page's content.  Computes page bounds eagerly so the
        ScrollableCanvas offscreen is always sized correctly on the first call."""
        score = self.pager.score_canvas.score
        if score is None:
            return 200
        total_h = score.total_content_height(canvas_w)
        # Ensure bounds are up to date for this canvas width before sizing the offscreen
        if (not self.pager._page_bounds
                or self.pager._offscreen_w != canvas_w
                or self.pager.score_canvas.dirty):
            self.pager._page_bounds = self.pager._compute_page_bounds(canvas_w, total_h)
        bounds = self.pager._page_bounds
        if self.page_idx < len(bounds):
            y_start, y_end = bounds[self.page_idx]
            return max(1, y_end - y_start)
        return 200   # page index out of range — empty slot

    def draw(self, surface: pygame.Surface, rect: pygame.Rect):
        """Called by ScrollableCanvas._rebuild; draws into the full offscreen."""
        canvas_w = rect.width

        if self.pager.score_canvas.score is None:
            self.pager.score_canvas._draw_placeholder(surface, surface.get_rect())
            return

        offscreen = self.pager._get_offscreen(canvas_w)
        if offscreen is None:
            surface.fill((255, 255, 255))
            return

        bounds = self.pager._page_bounds
        if self.page_idx >= len(bounds):
            surface.fill((255, 255, 255))
            return

        y_start, y_end = bounds[self.page_idx]
        slice_h = y_end - y_start

        surface.fill((255, 255, 255))
        if slice_h > 0:
            surface.blit(offscreen, (0, 0),
                         pygame.Rect(0, y_start, canvas_w, slice_h))


# ─────────────────────────────────────────────────────────── ScorePager ────

class ScorePager:
    """
    Paged score view built on OpenGUI's PageRouter.

    Each UI page = one A4 page of content.  Page slots are ScrollableCanvas
    widgets so content that exceeds the viewport is scrollable.
    Page breaks snap to system boundaries so no staff is cut in half.

    Quick start
    -----------
    canvas = ScoreCanvas()
    pager  = ScorePager(canvas)
    app.root.add_child(pager.build_view(y_offset=108))
    prev_btn.on_click = pager.go_prev
    next_btn.on_click = pager.go_next
    pager.on_page_change = lambda p, n: ...
    canvas.load("piece.xml")
    """

    MAX_PAGES = 50

    def __init__(self, score_canvas: "ScoreCanvas | None" = None):
        self.score_canvas   = score_canvas if score_canvas is not None else ScoreCanvas()
        self.on_page_change = None

        self._page_idx    = 0
        self._n_pages     = 1
        self._page_bounds = []
        self._router      = None
        self._offscreen   = None
        self._offscreen_w = 0
        self._offscreen_h = 0

    # ── proxy ────────────────────────────────────────────────────────────────

    @property
    def score(self):
        return self.score_canvas.score

    @score.setter
    def score(self, v):
        self.score_canvas.score = v
        self.score_canvas.dirty = True
        self._reset()

    @property
    def error(self):
        return self.score_canvas.error

    @error.setter
    def error(self, v):
        self.score_canvas.error = v

    def load(self, path: str) -> bool:
        ok = self.score_canvas.load(path)
        if ok:
            self._reset()
        return ok

    # ── internal ─────────────────────────────────────────────────────────────

    def _reset(self):
        self._offscreen   = None
        self._page_idx    = 0
        self._n_pages     = 1
        self._page_bounds = []
        if self._router is not None:
            if self._router.active_page_name != "0":
                self._router.navigate("0")
        self._fire()

    def _fire(self):
        if self.on_page_change:
            self.on_page_change(self._page_idx, self._n_pages)

    def _compute_page_bounds(self, canvas_w: int, total_h: int) -> list:
        """
        Group systems into A4-page-height buckets, snapping at system boundaries.
        Returns list of (y_start, y_end) per page.
        """
        score  = self.score_canvas.score
        a4_h   = max(200, int(canvas_w * 297 / 210))

        if score is None:
            return [(0, total_h)]

        sys_tops = score.system_y_tops()
        space    = score._space()
        # Bottom margin: safety for stems/ledger lines below the last staff line.
        # Top margin: safety for notes/ledger lines above the top staff line.
        # sys_tops[j] is the exact Y of the topmost staff line, so any note above
        # the top line (G5, A5, … in treble) renders at Y < sys_tops[j] and would
        # be clipped if the page boundary sits exactly there.  Using _SCORE_MT
        # (= 4) matches the top margin page 1 already has via sys_tops[0] = mt.
        # The two margins sum to sysg (6 spaces) so the cut always lands in the
        # dead zone of the inter-system gap and no content is ever clipped.
        bot_margin = space * 2
        top_margin = space * _SCORE_MT        # == space * 4
        sys_h      = score.system_height() + bot_margin

        if not sys_tops:
            return [(0, total_h)]

        pages    = []
        page_top = 0
        i        = 0
        n        = len(sys_tops)

        while i < n:
            j = i
            while j < n and (sys_tops[j] + sys_h - page_top) <= a4_h:
                j += 1
            if j == i:
                j = i + 1   # force-include at least one system per page

            # Cut top_margin above the first staff line of the next system so
            # pages 2+ have the same breathing room above their first system as
            # page 1 does (page 1 gets it "for free" via meta_h + mt in sys_tops[0]).
            page_bot = (sys_tops[j] - top_margin) if j < n else total_h
            pages.append((page_top, page_bot))
            page_top = page_bot
            i = j

        if pages and pages[-1][1] < total_h:
            pages[-1] = (pages[-1][0], total_h)

        return pages if pages else [(0, total_h)]

    def _get_offscreen(self, canvas_w: int) -> "pygame.Surface | None":
        """Build (or return cached) full-score offscreen surface."""
        score = self.score_canvas.score
        if score is None:
            return None

        total_h = score.total_content_height(canvas_w)
        if total_h < 1:
            return None

        need_rebuild = (
            self._offscreen is None
            or self._offscreen_w != canvas_w
            or self._offscreen_h != total_h
            or self.score_canvas.dirty
        )

        if need_rebuild:
            self._offscreen   = pygame.Surface((canvas_w, total_h))
            self._offscreen_w = canvas_w
            self._offscreen_h = total_h

            score.surface = self._offscreen
            for staff in score.staffs:
                staff.surface = self._offscreen
            if score.brace:
                score.brace.surface = self._offscreen

            self._offscreen.fill((255, 255, 255))
            score.draw()
            self.score_canvas.dirty = False

            # Recompute page layout after every rebuild
            new_bounds = self._compute_page_bounds(canvas_w, total_h)
            n = len(new_bounds)
            if new_bounds != self._page_bounds or n != self._n_pages:
                self._page_bounds = new_bounds
                self._n_pages     = n
                self._page_idx    = min(self._page_idx, n - 1)
                if self._router:
                    name = str(self._page_idx)
                    if self._router.active_page_name != name:
                        self._router.navigate(name)
                self._fire()

        return self._offscreen

    # ── navigation ───────────────────────────────────────────────────────────

    def go_prev(self):
        if self._page_idx > 0:
            self._page_idx -= 1
            if self._router:
                self._router.navigate(str(self._page_idx))
            self._fire()

    def go_next(self):
        if self._page_idx < self._n_pages - 1:
            self._page_idx += 1
            if self._router:
                self._router.navigate(str(self._page_idx))
            self._fire()

    # ── build ─────────────────────────────────────────────────────────────────

    def build_view(self, y_offset: int = 80, app=None):
        """
        Return a PageRouter widget ready to add to app.root.

        Pass app to fix the router height so it never overflows the viewport:
        height=1.0 (full parent) + y=y_offset would extend y_offset pixels past
        the window bottom.  When app is supplied, the router is sized to
        app.height - y_offset and kept correct across window resizes.
        """
        from pylay.layouts.router import PageRouter
        from pylay.widgets.scrollable_canvas import ScrollableCanvas

        pager = self

        def _make(idx: int):
            def builder():
                return ScrollableCanvas(
                    target=_ScoreSlice(pager, idx),
                    anchor="top_left", x=0, y=0,
                    width=1.0, height=1.0,
                    draw_border=False,
                )
            return builder

        pages  = {str(i): _make(i) for i in range(self.MAX_PAGES)}
        router = PageRouter(
            pages=pages,
            initial_page="0",
            anchor="top_left", x=0, y=y_offset,
            width=1.0, height=1.0,
        )
        self._router = router

        if app is not None:
            router.height_spec = app.height - y_offset
            _prev = app.on_resize
            def _on_resize(w, h, _prev=_prev):
                router.height_spec = h - y_offset
                if _prev is not None:
                    _prev(w, h)
            app.on_resize = _on_resize

        return router
