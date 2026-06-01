"""
Song score viewer page — displays a MusicXML file using PyLute's ScorePager.
Navigated to from the Songs tab when the user taps "View Score".
Does NOT share state with the lesson StaffView; completely independent.
"""
import threading
import queue as _queue_mod

import pygame
from pylay import FloatLayout, VStack, Label, Button, State, iOSTheme, ColorPalette
from pylay.widgets.pygame_canvas import PygameCanvas
from pylay.core.element import UIElement
import pylute

import pianove.context as ctx
from pianove.i18n import t

_TOOLBAR_H  = 52
_NAV_H      = 36
_STATUS_H   = 20
_CONTENT_Y  = _TOOLBAR_H + _NAV_H + _STATUS_H


def _nav_back():
    ctx.score_song_id = None
    ctx.router.navigate("home", "left")


def build():
    from pianove.song_store import get_song

    song = get_song(ctx.score_song_id) if ctx.score_song_id else None
    title    = song["title"]    if song else "Score"
    filepath = song["filepath"] if song else ""

    win_h    = ctx.ui.height if ctx.ui else 768
    win_w    = ctx.ui.width  if ctx.ui else 1024

    canvas = pylute.ScoreCanvas()
    pager  = pylute.ScorePager(score_canvas=canvas)

    root = FloatLayout(width=1.0, height=1.0, background_color=iOSTheme.background)

    # ── Toolbar (back + title) ────────────────────────────────────────────
    toolbar = FloatLayout(
        anchor="top_left", x=0, y=0,
        width=1.0, height=_TOOLBAR_H,
        background_color=iOSTheme.secondary_background,
    )
    toolbar.add_child(Button(
        text=t("back"),
        on_click=_nav_back,
        anchor="left", x=12, y=0,
        width=72, height=34, font_size=14,
        background_color=iOSTheme.fill,
        text_color=iOSTheme.label,
        border_radius=8,
    ))
    toolbar.add_child(Label(
        text=title,
        font_size=16, bold=True,
        color=iOSTheme.label,
        anchor="center", x=0, y=0,
    ))
    root.add_child(toolbar)

    # ── Page navigation bar ───────────────────────────────────────────────
    page_lbl = Label(
        text="—", font_size=13,
        color=iOSTheme.secondary_label,
        anchor="top_left", x=0, y=_TOOLBAR_H,
        width=1.0, height=_NAV_H,
    )
    nav_bar = FloatLayout(
        anchor="top_left", x=0, y=_TOOLBAR_H,
        width=1.0, height=_NAV_H,
        background_color=iOSTheme.tertiary_background,
    )
    prev_btn = Button(
        text="←", anchor="left", x=12, y=4,
        width=56, height=_NAV_H - 8, font_size=15,
        background_color=iOSTheme.fill,
        text_color=iOSTheme.label,
        border_radius=8,
    )
    next_btn = Button(
        text="→", anchor="right", x=-12, y=4,
        width=56, height=_NAV_H - 8, font_size=15,
        background_color=iOSTheme.fill,
        text_color=iOSTheme.label,
        border_radius=8,
    )
    page_state = State("—")
    page_label = Label(
        text=page_state, font_size=13,
        color=iOSTheme.secondary_label,
        anchor="center", x=0, y=0,
        width=0.5, height=_NAV_H,
    )
    pager.on_page_change = lambda p, n: setattr(page_state, "value",
                                                 f"Page {p + 1} / {n}")
    prev_btn.on_click = pager.go_prev
    next_btn.on_click = pager.go_next
    nav_bar.add_child(prev_btn)
    nav_bar.add_child(page_label)
    nav_bar.add_child(next_btn)
    root.add_child(nav_bar)

    # ── Status label ──────────────────────────────────────────────────────
    status_state = State(t("score_loading") if filepath else t("score_no_file"))
    status_lbl = Label(
        text=status_state,
        font_size=12,
        color=iOSTheme.secondary_label,
        anchor="top_left", x=16, y=_TOOLBAR_H + _NAV_H,
        width=1.0, height=_STATUS_H,
    )
    root.add_child(status_lbl)

    # ── Score view (pager) ────────────────────────────────────────────────
    score_h    = max(200, win_h - _CONTENT_Y)
    score_view = pager.build_view(y_offset=_CONTENT_Y)
    score_view.height_spec = score_h
    root.add_child(score_view)

    # ── Async loader ──────────────────────────────────────────────────────
    _q: _queue_mod.SimpleQueue = _queue_mod.SimpleQueue()

    class _Loader(UIElement):
        def __init__(self):
            super().__init__(width=0, height=0)
            self._started = False

        def update(self, dt: float):
            if not self._started and filepath:
                self._started = True
                def _worker():
                    try:
                        from pylute.musicxml import load_musicxml
                        score = load_musicxml(filepath)
                        _q.put((score, ""))
                    except Exception as exc:
                        _q.put((None, str(exc)))
                threading.Thread(target=_worker, daemon=True).start()

            try:
                score, err = _q.get_nowait()
                if err:
                    status_state.value = f"✗  {err}"
                    pager.score_canvas.error = err
                else:
                    pager.score = score
                    n_bars = (len(score.staffs[0].bars)
                              if score and score.staffs else 0)
                    status_state.value = t("score_loaded_info",
                                           n=n_bars)
            except _queue_mod.Empty:
                pass

            super().update(dt)

    root.add_child(_Loader())
    return root
