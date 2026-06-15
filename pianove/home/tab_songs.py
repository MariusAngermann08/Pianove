import threading
import queue as _queue_mod

import pygame
import pianove.context as ctx
from pylay import (
    FloatLayout, VStack, Label, Button, SegmentedControl,
    State, EmojiIcon, EmptyState, iOSTheme, ColorPalette, FilePicker, ProgressBar, UIElement,
)
from pylay.widgets.icon import Icon
from pianove.i18n import t
from pianove.components import ORANGE, GREEN, RED

_filter_state = State(0)
_prev_filter_listener = None

_importing_state = State(False)
_import_progress = State(0.0)
_import_result_q: _queue_mod.SimpleQueue = _queue_mod.SimpleQueue()

_import_error_state = State("")

_HEADER_H   = 58
_PROGRESS_H = 4
_CARD_H     = 82
_CARD_GAP   = 10

_DIFF_COLORS = {
    "beginner":     GREEN,
    "intermediate": ORANGE,
    "advanced":     RED,
}

_prev_import_listener = None


def _diff_index(diff: str) -> int:
    return {"beginner": 1, "intermediate": 2, "advanced": 3}.get(diff, 0)


def _open_song(song_id: str):
    ctx.current_song_id = song_id
    ctx.router.navigate("song_setup", "right")


def _view_score(song_id: str):
    ctx.score_song_id = song_id
    ctx.router.navigate("song_score", "right")


def _delete_song(song_id: str):
    from pianove.song_store import delete_song
    delete_song(song_id)
    if ctx.inner_router:
        ctx.inner_router.reload_current_page()


def _song_card(song: dict) -> FloatLayout:
    song_id  = song["id"]
    title    = song.get("title", "Untitled")
    composer = song.get("composer", "")
    diff     = song.get("difficulty", "beginner")
    n_bars   = song.get("n_bars", 0)

    diff_color = _DIFF_COLORS.get(diff, iOSTheme.secondary_label)

    card = FloatLayout(
        width=1.0, height=_CARD_H,
        background_color=iOSTheme.secondary_background,
        border_radius=14,
    )

    card.add_child(Icon(
        "music_note", size=28, color=iOSTheme.secondary_label,
        anchor="left", x=16, y=0,
    ))

    card.add_child(Label(
        text=title, font_size=15, bold=True, color=iOSTheme.label,
        anchor="left", x=56, y=-10,
    ))
    sub = f"{composer}  ·  {t('song_bars', n=n_bars)}" if composer else t("song_bars", n=n_bars)
    card.add_child(Label(
        text=sub, font_size=12, color=iOSTheme.secondary_label,
        anchor="left", x=56, y=12,
    ))

    card.add_child(Label(
        text=t(f"diff_{diff}"),
        font_size=11, color=diff_color,
        anchor="right", x=-208, y=0,
    ))

    card.add_child(Button(
        icon_fn=Icon.as_icon_fn("delete", base_size=16),
        on_click=lambda _id=song_id: _delete_song(_id),
        anchor="right", x=-168, y=0,
        width=32, height=32,
        background_color=iOSTheme.fill,
        text_color=RED,
        border_radius=8,
    ))

    card.add_child(Button(
        text=t("song_view_score"),
        on_click=lambda _id=song_id: _view_score(_id),
        anchor="right", x=-88, y=0,
        width=72, height=34, font_size=13,
        background_color=iOSTheme.fill,
        text_color=iOSTheme.label,
        border_radius=10,
    ))

    card.add_child(Button(
        text=t("song_start"),
        on_click=lambda _id=song_id: _open_song(_id),
        anchor="right", x=-8, y=0,
        width=72, height=34, font_size=13,
        background_color=ColorPalette.BLUE,
        text_color=pygame.Color(255, 255, 255),
        border_radius=10,
    ))

    return card


def build():
    global _prev_filter_listener, _prev_import_listener

    from pianove.song_store import list_songs, import_song

    # ── detach stale listeners ────────────────────────────────────────────────
    if _prev_filter_listener is not None:
        try:
            _filter_state._listeners.remove(_prev_filter_listener)
        except ValueError:
            pass

    if _prev_import_listener is not None:
        try:
            _importing_state._listeners.remove(_prev_import_listener)
        except ValueError:
            pass

    songs  = list_songs()
    list_h = max(100, ctx.ui.height - _HEADER_H - _PROGRESS_H) if ctx.ui else 600

    root = FloatLayout(width=1.0, height=1.0, background_color=iOSTheme.background)

    # ── Fixed header ──────────────────────────────────────────────────────────
    header = FloatLayout(
        anchor="top_left", x=0, y=0,
        width=1.0, height=_HEADER_H,
        background_color=iOSTheme.background,
    )

    header.add_child(SegmentedControl(
        segments=[
            t("filter_all"), t("filter_beginner"),
            t("filter_intermediate"), t("filter_advanced"),
        ],
        selected_index=_filter_state,
        on_change=lambda i: setattr(_filter_state, "value", i),
        anchor="center", x=-22, y=0,
        width=0.80, height=34,
    ))

    # ── FilePicker ────────────────────────────────────────────────────────────
    picker = FilePicker(
        title=t("song_import_title"),
        filters=["MusicXML | *.xml *.musicxml *.mxl", "All files | *"],
    )

    def _on_file(path: str):
        if not path:
            return
        _import_error_state.value = ""
        _import_progress.value    = 0.0
        _importing_state.value    = True

        def _worker():
            try:
                import_song(path)
                _import_result_q.put({"error": ""})
            except Exception as exc:
                _import_result_q.put({"error": str(exc)})

        threading.Thread(target=_worker, daemon=True).start()

    def _do_import():
        picker.pick(_on_file)

    header.add_child(Button(
        icon_fn=Icon.as_icon_fn("add", base_size=20),
        on_click=_do_import,
        anchor="right", x=-8, y=0,
        width=36, height=36,
        background_color=ColorPalette.BLUE,
        text_color=pygame.Color(255, 255, 255),
        border_radius=18,
    ))

    root.add_child(header)
    root.add_child(picker)

    # ── Import progress bar ───────────────────────────────────────────────────
    prog_bar = ProgressBar(
        progress=_import_progress,
        anchor="top_left", x=0, y=_HEADER_H,
        width=1.0, height=_PROGRESS_H,
        visible=_importing_state.value,
    )
    root.add_child(prog_bar)

    def _on_importing(importing: bool):
        prog_bar.visible = importing

    _importing_state.bind(_on_importing)
    _prev_import_listener = _on_importing

    # ── Import-result watcher (zero-size, runs every frame) ───────────────────
    class _ImportWatcher(UIElement):
        def __init__(self):
            super().__init__(width=0, height=0)
            self._elapsed = 0.0

        def update(self, dt: float):
            if _importing_state.value:
                self._elapsed += dt
                _import_progress.value = 0.9 * (1.0 - 2.0 ** (-self._elapsed * 1.5))
            else:
                self._elapsed = 0.0

            try:
                result = _import_result_q.get_nowait()
                err = result.get("error", "")
                _import_progress.value  = 1.0
                _importing_state.value  = False
                if err:
                    _import_error_state.value = err
                else:
                    _import_error_state.value = ""
                    if ctx.inner_router:
                        ctx.inner_router.reload_current_page()
            except _queue_mod.Empty:
                pass

            super().update(dt)

    root.add_child(_ImportWatcher())

    # ── Scrollable song list ──────────────────────────────────────────────────
    scroll = VStack(
        spacing=_CARD_GAP, padding=12,
        anchor="top_left", x=0, y=_HEADER_H + _PROGRESS_H,
        width=1.0, height=list_h,
        background_color=iOSTheme.background,
    )

    scroll.add_child(Label(
        text=_import_error_state,
        font_size=12, color=RED,
        width=1.0, height=18,
    ))

    filter_idx = _filter_state.value
    visible = [
        s for s in songs
        if filter_idx == 0 or _diff_index(s.get("difficulty", "beginner")) == filter_idx
    ]

    if visible:
        for song in visible:
            scroll.add_child(_song_card(song))
    else:
        scroll.add_child(EmptyState(
            icon="🎵",
            title=t("songs_empty" if songs else "songs_coming_soon"),
            subtitle=t("songs_import_hint") if not songs else "",
            height=max(200, list_h - 60),
        ))

    root.add_child(scroll)

    def _apply_filter(_):
        if ctx.inner_router:
            ctx.inner_router.navigate("songs")

    _filter_state.bind(_apply_filter)
    _prev_filter_listener = _apply_filter

    return root
