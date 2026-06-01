"""
demo_score.py — PyLute + PyLay paged viewer

Each UI page = one A4 page of content.  Pages are independently scrollable.
Single-page pieces show as Page 1/1 with scroll.

Run:
    python demo_score.py [optional_file.xml]
"""
import sys, os, threading, queue as _queue_mod
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(_ROOT, "PyLay"))
sys.path.insert(0, os.path.join(_ROOT, "PyLute"))

import pylute
from pylay import (
    App, State, FloatLayout, Label, Button, TextField,
    iOSTheme, FilePicker, ProgressBar,
)
from pylay.core.element import UIElement

_TOOLBAR_H  = 52
_NAV_H      = 36
_STATUS_H   = 20
_PROGRESS_H = 4
_CONTENT_Y  = _TOOLBAR_H + _NAV_H + _STATUS_H + _PROGRESS_H   # 112


def build_ui(app: App, canvas: pylute.ScoreCanvas,
             pager: pylute.ScorePager, initial_path: str = ""):
    root = app.root

    # ── async file picker (zero-size, driven by update()) ────────────────────
    picker = FilePicker(
        title="Open MusicXML",
        filters=["MusicXML | *.xml *.mxl *.musicxml", "All files | *"],
    )
    root.add_child(picker)

    # ── file-path toolbar ────────────────────────────────────────────────────
    toolbar = FloatLayout(anchor="top_left", x=0, y=0,
                          width=1.0, height=_TOOLBAR_H,
                          background_color=iOSTheme.secondary_background)
    path_field = TextField(text=initial_path,
                           anchor="top_left", x=12, y=10,
                           width=0.72, height=32,
                           placeholder="Path to .xml / .mxl …")
    load_btn = Button(text="Load", anchor="top_left", x=0.76, y=10, width=0.10, height=32)
    demo_btn = Button(text="Demo", anchor="top_left", x=0.88, y=10, width=0.10, height=32)
    toolbar.add_child(path_field)
    toolbar.add_child(load_btn)
    toolbar.add_child(demo_btn)

    # ── page-navigation bar ──────────────────────────────────────────────────
    nav_bar = FloatLayout(anchor="top_left", x=0, y=_TOOLBAR_H,
                          width=1.0, height=_NAV_H,
                          background_color=iOSTheme.tertiary_background)
    prev_btn = Button(text="←", anchor="top_left",
                      x=0.02, y=4, width=0.08, height=_NAV_H - 8)
    next_btn = Button(text="→", anchor="top_left",
                      x=0.90, y=4, width=0.08, height=_NAV_H - 8)
    page_lbl = Label(text="—", anchor="top_left", x=0.12, y=0,
                     width=0.76, height=_NAV_H, font_size=13,
                     color=iOSTheme.secondary_label)
    nav_bar.add_child(prev_btn)
    nav_bar.add_child(page_lbl)
    nav_bar.add_child(next_btn)

    # ── status label ─────────────────────────────────────────────────────────
    status = State("")
    status_lbl = Label(text="", anchor="top_left",
                       x=0, y=_TOOLBAR_H + _NAV_H,
                       width=1.0, height=_STATUS_H,
                       font_size=12, color=iOSTheme.secondary_label)
    status.bind(lambda v: setattr(status_lbl, "text", v))

    # ── loading progress bar ──────────────────────────────────────────────────
    load_progress = State(0.0)
    progress_bar = ProgressBar(
        progress=load_progress,
        anchor="top_left",
        x=0, y=_TOOLBAR_H + _NAV_H + _STATUS_H,
        width=1.0, height=_PROGRESS_H,
        visible=False,
    )

    # ── paged score view ─────────────────────────────────────────────────────
    pager.on_page_change = lambda p, n: setattr(
        page_lbl, "text", f"Page {p + 1} / {n}")
    prev_btn.on_click = pager.go_prev
    next_btn.on_click = pager.go_next
    router = pager.build_view(y_offset=_CONTENT_Y, app=app)

    # ── callbacks ────────────────────────────────────────────────────────────
    def _after_load():
        if pager.error:
            status.value = f"✗  {pager.error}"
        elif pager.score:
            s = pager.score
            status.value = (
                f"Loaded  ·  {len(s.staffs)} staff{'s' if len(s.staffs) != 1 else ''}"
                f"  ·  {len(s.staffs[0].bars)} bars"
            )

    # ── threaded loader + progress watcher ───────────────────────────────────
    _load_result_q: _queue_mod.SimpleQueue = _queue_mod.SimpleQueue()

    class _LoadWatcher(UIElement):
        def __init__(self):
            super().__init__(width=0, height=0)
            self._active = False
            self._elapsed = 0.0
            self._done_timer = 0.0

        def start(self, path: str) -> None:
            self._active = True
            self._elapsed = 0.0
            self._done_timer = 0.0
            load_progress.value = 0.0
            progress_bar.visible = True
            def _worker():
                # Only parse XML in the background — never touch pager/pygame here.
                try:
                    from pylute.musicxml import load_musicxml
                    score = load_musicxml(path)
                    _load_result_q.put((score, ""))
                except Exception as exc:
                    _load_result_q.put((None, str(exc)))
            threading.Thread(target=_worker, daemon=True).start()

        def update(self, dt: float) -> None:
            if self._active:
                self._elapsed += dt
                # Ease toward 0.85 over ~2 s while loading
                load_progress.value = 0.85 * (1.0 - 2.0 ** (-self._elapsed * 1.2))

            try:
                score, error = _load_result_q.get_nowait()
                self._active = False
                # Apply result on the main thread — safe for pager/_reset/router.
                if error:
                    pager.score_canvas.score = None
                    pager.score_canvas.error = error
                else:
                    pager.score_canvas.error = ""
                    pager.score_canvas.dirty = True
                    pager.score = score   # triggers _reset() on main thread
                load_progress.value = 1.0
                _after_load()
                self._done_timer = 0.8
            except _queue_mod.Empty:
                pass

            if self._done_timer > 0:
                self._done_timer -= dt
                if self._done_timer <= 0:
                    progress_bar.visible = False
                    load_progress.value = 0.0

            super().update(dt)

    watcher = _LoadWatcher()
    root.add_child(watcher)

    def do_load():
        typed = path_field.text_val.strip()

        def _on_picked(path):
            if not path:
                path = typed        # dialog cancelled — fall back to text field
            if not path:
                return              # nothing to load
            path_field.text_val = path
            watcher.start(path)

        picker.pick(_on_picked)

    def do_demo():
        pager.score = _make_demo_score()
        pager.error = ""
        path_field.text_val = ""
        status.value = f"Demo  ·  {len(pager.score.staffs[0].bars)} bars"

    load_btn.on_click = do_load
    demo_btn.on_click = do_demo

    root.add_child(toolbar)
    root.add_child(nav_bar)
    root.add_child(status_lbl)
    root.add_child(progress_bar)
    root.add_child(router)

    if initial_path:
        pager.load(initial_path)
        _after_load()


def _make_demo_score():
    score = pylute.Score(staffs=2, bars=8,
                            clef_types=["treble", "bass"],
                            key="G", time=(4, 4))

    def add(si, *evs):
        for ev in evs:
            (score.addNote if ev[0] == "n" else score.addRest)(
                **(dict(ntype=ev[1], pitch=ev[2], staff_index=si) if ev[0] == "n"
                   else dict(rtype=ev[1], staff_index=si)))

    add(0,
        ("n","quarter","G4"), ("n","quarter","A4"),
        ("n","quarter","B4"), ("n","quarter","D5"),
        ("n","eighth","G4"),  ("n","eighth","A4"),
        ("n","eighth","B4"),  ("n","eighth","C5"),
        ("n","eighth","D5"),  ("n","eighth","E5"),
        ("n","eighth","D5"),  ("n","eighth","B4"),
        ("n","half","G4"),
        ("n","eighth","B4"),  ("n","eighth","D5"),
        ("n","eighth","G5"),  ("n","eighth","F#5"),
        ("n","sixteenth","G5"), ("n","sixteenth","F#5"),
        ("n","sixteenth","E5"), ("n","sixteenth","D5"),
        ("n","sixteenth","C5"), ("n","sixteenth","B4"),
        ("n","sixteenth","A4"), ("n","sixteenth","G4"),
        ("n","quarter","G4"),   ("n","quarter","D5"),
        ("n","dotted_quarter","D5"), ("n","eighth","E5"),
        ("n","dotted_quarter","F#5"), ("n","eighth","G5"),
        ("n","dotted_half","G5"),     ("n","quarter","F#5"),
        ("n","eighth","G5"), ("n","eighth","F#5"),
        ("n","eighth","E5"), ("r","eighth"),
        ("n","quarter","D5"), ("n","quarter","B4"),
        ("n","dotted_quarter","G4"), ("n","eighth","A4"),
        ("n","half","B4"),
    )
    add(1,
        ("n","whole","G2"),
        ("n","half","D3"),   ("n","half","G3"),
        ("n","quarter","G2"), ("n","quarter","B2"),
        ("n","quarter","D3"), ("n","quarter","G3"),
        ("n","whole","D2"),
        ("n","dotted_half","G2"), ("n","quarter","D3"),
        ("n","whole","G2"),
        ("n","quarter","D3"), ("n","quarter","F#3"),
        ("n","quarter","A3"), ("n","quarter","D4"),
        ("n","dotted_quarter","G2"), ("n","eighth","A2"),
        ("n","half","D3"),
    )
    return score


def main():
    initial = sys.argv[1] if len(sys.argv) > 1 else ""
    app     = App(title="PyLute Viewer", width=1280, height=820, dark_mode=False)
    canvas  = pylute.ScoreCanvas()
    pager   = pylute.ScorePager(score_canvas=canvas)
    build_ui(app, canvas, pager, initial)
    app.run()


if __name__ == "__main__":
    main()
