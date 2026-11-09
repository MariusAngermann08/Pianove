"""The lesson editor (Creator Mode).

A lesson is shown the way a teacher plans one: chapters of screens, and pieces to play.
A screen has a kind, and only shows what that kind needs:

- explain:  text, and keys highlighted or named (tap them on the preview)
- listen:   a phrase Pianove plays (written once, with rhythm and fingers) that the
            learner then plays back, optionally shown on a staff
- find:     keys the learner has to find (tap them on the preview)
- hand:     where the fingers rest (tap keys on the preview)

The preview is the lesson player's own drawing, and it is where keys are picked. Music
is entered by playing it (MIDI, microphone, the keys on screen), by typing or tapping on
the score, or by recording against a metronome. Texts are written in the app's language;
the Translation page holds the others. Rarely needed settings sit under "More options".
"""
from __future__ import annotations

import copy
import time

import pygame
from pylay import FloatLayout, Label, SegmentedControl, Stepper, Switch, PygameCanvas, FilePicker, iOSTheme, ColorPalette
from pylay.core.element import UIElement
from pylay.core import _dirty
from pylay.widgets.icon import Icon

import pianove.context as ctx
from pianove.i18n import t, language_state
from pianove import creator_store as cs
from pianove import exercise_format as ef
from pianove import phrase as ph
from pianove.creator_notes import parse_chord, note_name
from pianove.creator_ui import (px, is_narrow, tn, left, font, text_w, button, Flow, DragScroll, TextBox,
                                KeyPicker, heading, field_label, hint, spacer, Ticker, Toast, WHITE, RED,
                                GREEN, is_touch_layout, _sound)

_ORANGE = pygame.Color(255, 159, 10)
_TIMES = [[2, 4], [3, 4], [4, 4], [6, 8]]
_ICONS = {"explain": "lightbulb", "listen": "hearing", "find": "touch_app", "hand": "front_hand",
          "piece": "music_note", "chapter": "menu_book", "lesson": "info", "translate": "translate"}
_LABEL_MODES = [None, "C", "white", "hand"]
_ED: "_Editor | None" = None


def _loc_get(obj: dict, key: str, lang: str) -> str:
    v = obj.get(key)
    if isinstance(v, dict):
        return str(v.get(lang) or "")
    return str(v or "") if lang == "en" else ""


def _loc_set(obj: dict, key: str, lang: str, text: str):
    v = obj.get(key)
    if not isinstance(v, dict):
        v = {"en": v} if isinstance(v, str) and v else {}
    v[lang] = text
    obj[key] = v


def _clear(container):
    for c in list(container.children):
        c.parent = None
    container.children.clear()


def _tl(key: str, lang: str, **kw) -> str:
    """A text in a given language (a new screen gets its title in every language)."""
    from pianove.i18n import _load
    text = _load(lang).get(key) or _load("en").get(key, key)
    return text.format(**kw) if kw else text


def _guess_key(play) -> int:
    from pianove.pages.lesson import _guess_key as guess
    return guess([list(play)])


def _compile(beat: dict):
    """The player's fields from a listen screen's phrase (and whether the learner plays
    it back afterwards)."""
    ph.compile_beat(beat, key_fn=_guess_key)
    if ph.kind_of(beat) == "listen":
        if beat.get("repeat", True) and beat.get("play"):
            beat["try"] = "play"
        elif beat.get("try") == "play":
            beat.pop("try")


# ── the editor's state ────────────────────────────────────────────────────────────────

class _Editor:
    def __init__(self, lesson_id: str):
        self.id = lesson_id
        self.draft = cs.load_draft(lesson_id)
        self.sel: tuple = ("lesson",)
        self.lang = language_state.value if language_state.value in cs.LOCALES else "en"
        self.dirty = False
        self.problems = cs.validate(self.draft)
        self.preview_dirty = True
        self.preview_autoplay = True
        self.show_outline = False
        self.more = False
        self.tap_mode = "mark"          # explain screens: a tap highlights or names a key
        self.hand_side = "right"        # hand screens: the hand a tap puts a finger of
        self.import_hand = 0
        self.confirm: str | None = None
        self.confirm_t = 0.0
        self.entry_picker = KeyPicker(lambda m: None)
        self.models: dict = {}
        self.recorder = None
        self.page: dict = {}
        self._live: set = set()

    # ── the draft ──
    @property
    def steps(self) -> list:
        return self.draft["steps"]

    def step(self, i: int) -> dict:
        return self.steps[i]

    def beat(self, i: int, j: int) -> dict:
        return self.steps[i]["beats"][j]

    def cur_beat(self) -> dict | None:
        return self.beat(self.sel[1], self.sel[2]) if self.sel[0] == "beat" else None

    def cur_piece(self) -> dict | None:
        if self.sel[0] == "step" and self.step(self.sel[1]).get("type") == "exercise":
            return self.step(self.sel[1])
        return None

    def title(self) -> str:
        s = self.draft["strings"]
        return s.get(self.lang, {}).get("title") or s.get("en", {}).get("title") or self.id

    def changed(self, structure: bool = False, autoplay: bool = False):
        self.dirty = True
        self.problems = cs.validate(self.draft)
        self.preview_dirty = True
        self.preview_autoplay = autoplay
        _sync_bar()
        if structure:
            rebuild()
        _dirty.mark()

    def save(self) -> bool:
        try:
            cs.save_draft(self.draft)
        except OSError as e:
            _toast(t("ed_save_failed", error=str(e)), RED)
            return False
        self.dirty = False
        _sync_bar()
        return True

    # ── checks: the ones to fix now, and translations (on the Translation page) ──
    def is_translation(self, problem) -> bool:
        _, code, args = problem
        return code.startswith("missing_") and str(args.get("lang", "")).lower() != self.lang

    def main_problems(self) -> list:
        return [p for p in self.problems if not self.is_translation(p)]

    def missing_translations(self) -> int:
        return sum(1 for p in self.problems if self.is_translation(p))

    def problems_at(self, sel: tuple) -> list:
        out = []
        for p in self.main_problems():
            where = p[0]
            if sel == ("lesson",) and where[0] == "lesson":
                out.append(p)
            elif sel[0] == "step" and where[0] in ("step", "bar") and where[1] == sel[1]:
                out.append(p)
            elif sel[0] == "beat" and where == sel:
                out.append(p)
        return out

    # ── selection ──
    def select(self, sel: tuple):
        self.stop_recording(keep=True)
        self.sel = sel
        self.confirm = None
        self.more = False
        self.preview_dirty = True
        self.preview_autoplay = True
        self.show_outline = False
        rebuild(scroll_top=True)

    def order(self) -> list[tuple]:
        out = [("lesson",)]
        for i, s in enumerate(self.steps):
            out.append(("step", i))
            if s.get("type") == "scene":
                out.extend(("beat", i, j) for j in range(len(s.get("beats", []))))
        return out

    def step_by(self, delta: int):
        o = self.order()
        k = o.index(self.sel) if self.sel in o else 0
        self.select(o[max(0, min(len(o) - 1, k + delta))])

    def where_text(self, where: tuple) -> str:
        if where[0] == "lesson":
            return t("ed_where_lesson")
        if where[0] == "step":
            return t("ed_where_step", n=where[1] + 1)
        if where[0] == "beat":
            return t("ed_where_beat", n=where[1] + 1, m=where[2] + 1)
        return t("ed_where_bar", n=where[1] + 1, m=where[2] + 1)

    # ── music ──
    def score_model(self, music: dict, beat: dict | None = None):
        """The editing of a piece, or of a screen's phrase (which then updates what the
        player reads)."""
        from pianove.score_editor import ScoreModel
        m = self.models.get(id(music))
        if m is None or m.step is not music:
            def changed(beat=beat):
                if beat is not None:
                    _compile(beat)
                self.changed()
            m = self.models[id(music)] = ScoreModel(music, on_change=changed)
        return m

    def current_model(self):
        b = self.cur_beat()
        if b is not None and ph.kind_of(b) == "listen":
            return self.score_model(ph.ensure_music(b), b)
        piece = self.cur_piece()
        return self.score_model(piece) if piece is not None else None

    def start_recording(self):
        from pianove.score_editor import Recorder
        model = self.current_model()
        if model is None:
            return
        self.recorder = Recorder(model)
        self.recorder.start()
        rebuild()

    def stop_recording(self, keep: bool = True):
        rec, self.recorder = self.recorder, None
        if rec is not None and rec.active:
            if rec.stop(keep=keep):
                _toast(t("ed_recorded"), GREEN)
            rebuild()

    # ── the lesson's structure ──
    def _insert_at_end_of_chapters(self) -> int:
        """Where a new chapter goes: before the pieces at the end of the lesson."""
        at = len(self.steps)
        while at > 0 and self.steps[at - 1].get("type") == "exercise":
            at -= 1
        return at if at > 0 else len(self.steps)

    def add_chapter(self):
        n = sum(1 for s in self.steps if s.get("type") == "scene") + 1
        at = self._insert_at_end_of_chapters()
        self.steps.insert(at, {"type": "scene",
                               "title": {lang: _tl("ed_new_chapter_title", lang, n=n) for lang in cs.LOCALES},
                               "beats": []})
        self.changed()
        self.select(("new", at))

    def add_piece(self):
        self.steps.append({"type": "exercise", "time": [4, 4], "tempo": ef.DEFAULT_TEMPO,
                           "bars": [[]], "types": [[]]})
        self.changed()
        self.select(("step", len(self.steps) - 1))

    def new_screen(self, kind: str) -> dict:
        title = {lang: _tl(f"ed_kind_{kind}", lang) for lang in cs.LOCALES}
        beat = {"kind": kind, "title": title, "say": {lang: "" for lang in cs.LOCALES}}
        if kind == "listen":
            beat.update(repeat=True, music={"time": [4, 4], "tempo": 76, "bars": [[]], "types": [[]]},
                        try_say={lang: "" for lang in cs.LOCALES})
        elif kind == "find":
            beat.update({"try": [], "try_say": {lang: "" for lang in cs.LOCALES}})
        elif kind == "hand":
            beat.update(hand={"right": {"C4": 1, "D4": 2, "E4": 3, "F4": 4, "G4": 5}}, numbers=True)
        return beat

    def add_screen(self, i: int, kind: str):
        beats = self.step(i).setdefault("beats", [])
        beats.append(self.new_screen(kind))
        self.changed()
        self.select(("beat", i, len(beats) - 1))

    def set_kind(self, kind: str):
        b = self.cur_beat()
        if b is None or ph.kind_of(b) == kind:
            return
        b["kind"] = kind
        if kind == "listen":
            ph.ensure_music(b)
            b.setdefault("repeat", b.get("try") == "play" or not b.get("play"))
            _compile(b)
        elif kind == "find" and not isinstance(b.get("try"), list):
            b["try"] = []
        elif kind == "hand" and not b.get("hand"):
            b["hand"] = {"right": {"C4": 1, "D4": 2, "E4": 3, "F4": 4, "G4": 5}}
            b["numbers"] = True
        self.changed(structure=True, autoplay=True)

    def move(self, delta: int):
        if self.sel[0] == "step":
            i = self.sel[1]
            k = i + delta
            if 0 <= k < len(self.steps):
                self.steps[i], self.steps[k] = self.steps[k], self.steps[i]
                self.sel = ("step", k)
        elif self.sel[0] == "beat":
            _, i, j = self.sel
            beats = self.step(i)["beats"]
            k = j + delta
            if 0 <= k < len(beats):
                beats[j], beats[k] = beats[k], beats[j]
                self.sel = ("beat", i, k)
            elif k < 0 and i > 0 and self.step(i - 1).get("type") == "scene":
                self.step(i - 1)["beats"].append(beats.pop(j))     # into the chapter before
                self.sel = ("beat", i - 1, len(self.step(i - 1)["beats"]) - 1)
            elif k >= len(beats) and i + 1 < len(self.steps) and self.step(i + 1).get("type") == "scene":
                self.step(i + 1)["beats"].insert(0, beats.pop(j))  # into the chapter after
                self.sel = ("beat", i + 1, 0)
        self.changed(structure=True)

    def duplicate(self):
        if self.sel[0] == "step":
            i = self.sel[1]
            self.steps.insert(i + 1, copy.deepcopy(self.steps[i]))
            self.sel = ("step", i + 1)
        elif self.sel[0] == "beat":
            _, i, j = self.sel
            beats = self.step(i)["beats"]
            beats.insert(j + 1, copy.deepcopy(beats[j]))
            self.sel = ("beat", i, j + 1)
        self.changed(structure=True)

    def delete(self):
        key = repr(self.sel)
        if self.confirm != key or time.monotonic() - self.confirm_t > 4.0:
            self.confirm, self.confirm_t = key, time.monotonic()
            rebuild()
            return
        self.confirm = None
        if self.sel[0] == "step":
            i = self.sel[1]
            del self.steps[i]
            self.sel = ("step", min(i, len(self.steps) - 1)) if self.steps else ("lesson",)
        elif self.sel[0] == "beat":
            _, i, j = self.sel
            beats = self.step(i)["beats"]
            del beats[j]
            self.sel = ("beat", i, min(j, len(beats) - 1)) if beats else ("step", i)
        self.changed(structure=True)

    # ── taps on the preview's keyboard ──
    def preview_tap(self, m: int):
        b = self.cur_beat()
        if b is None:
            return
        kind = ph.kind_of(b)
        name = note_name(m)
        same = lambda x: (parse_chord(x) or [None])[0] == m
        if kind == "listen":
            if self.recorder is not None and self.recorder.active:
                self.recorder.key_down(m)
            else:
                self.current_model().key_note(m)
            return
        if kind == "find":
            b.setdefault("try", []).append(name)
        elif kind == "hand":
            hand = b.setdefault("hand", {})
            fm = hand.setdefault(self.hand_side, {})
            key = next((k for k in fm if same(k)), None)
            f = int(fm.pop(key)) + 1 if key else 1                # 1 → 2 → … → 5 → none
            if f <= 5:
                fm[name] = f
            hand[self.hand_side] = dict(sorted(fm.items(), key=lambda kv: (parse_chord(kv[0]) or [0])[0]))
            if not hand[self.hand_side]:
                hand.pop(self.hand_side)
            if not hand:
                b.pop("hand", None)
        else:                                                      # explain: highlight / name
            field = "mark" if self.tap_mode == "mark" else "labels"
            cur = b.get(field)
            cur = list(cur) if isinstance(cur, list) else []
            hit = [x for x in cur if same(x)]
            b[field] = [x for x in cur if x not in hit] if hit else cur + [name]
            if not b[field]:
                b.pop(field)
        self.changed()
        _sync_screen_notes()

    def preview_release(self, m: int):
        if self.recorder is not None and self.recorder.active:
            self.recorder.key_up(m)


# ── the outline: chapters, screens and pieces ─────────────────────────────────────────

class _Row(UIElement):
    """An entry of the outline. style: "top" (lesson, translation), "chapter", "screen",
    "piece"."""

    def __init__(self, sel: tuple, text_fn, icon: str, style: str, badge_fn=None):
        h = {"top": 38, "chapter": 40, "screen": 36, "piece": 42}[style]
        super().__init__(width=1.0, height=px(h))
        self.sel, self.text_fn, self.style, self.badge_fn = sel, text_fn, style, badge_fn
        self._icon = Icon.as_icon_fn(icon, base_size=18)
        self._pressed = False

    def on_event(self, event) -> bool:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.rect.collidepoint(event.pos):
            self._pressed = True
            return True
        if event.type == pygame.MOUSEMOTION and self._pressed and not self.rect.collidepoint(event.pos):
            self._pressed = False
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1 and self._pressed:
            self._pressed = False
            if self.rect.collidepoint(event.pos) and _ED:
                _ED.select(self.sel)
            return True
        return False

    def render(self, surface):
        ed = _ED
        if ed is None:
            return
        r = self.rect
        selected = ed.sel == self.sel
        indent = px(14) if self.style == "screen" else 0
        box = r.move(indent, 0)
        box.width -= indent
        if selected:
            pygame.draw.rect(surface, ColorPalette.BLUE, box, border_radius=px(9))
        elif self.style in ("screen", "piece"):
            pygame.draw.rect(surface, iOSTheme.fill if self._pressed else iOSTheme.tertiary_background,
                             box, border_radius=px(9))
        elif self._pressed:
            pygame.draw.rect(surface, iOSTheme.fill, box, border_radius=px(9))
        fg = WHITE if selected else iOSTheme.label
        sub = WHITE if selected else (ColorPalette.BLUE if self.style != "top" else iOSTheme.secondary_label)
        x = box.left + px(10)
        self._icon(surface, x + px(9), box.centery, scale_of(), sub)
        x += px(26)
        right = box.right - px(10)
        badge = self.badge_fn() if self.badge_fn else 0
        if badge:
            f = font(11, bold=True)
            ts = f.render(str(badge), True, WHITE)
            bw = max(ts.get_width() + px(10), px(20))
            br = pygame.Rect(right - bw, box.centery - px(10), bw, px(20))
            pygame.draw.rect(surface, WHITE if selected else _ORANGE, br, border_radius=px(10))
            if selected:
                ts = f.render(str(badge), True, ColorPalette.BLUE)
            surface.blit(ts, ts.get_rect(center=br.center))
            right = br.left - px(6)
        f = font(13 if self.style in ("chapter", "piece") else 12, bold=self.style in ("chapter", "piece"))
        text = self.text_fn()
        while text and f.size(text)[0] > right - x:
            text = text[:-2] + "…" if len(text) > 2 else ""
        ts = f.render(text, True, fg)
        surface.blit(ts, (x, box.centery - ts.get_height() // 2))


def scale_of() -> float:
    import pylay.core.scale as sc
    return sc.UI_SCALE


def _fill_outline(box):
    ed = _ED
    _clear(box)
    box.add_child(_Row(("lesson",), lambda: t("ed_lesson_details"), _ICONS["lesson"], "top",
                       badge_fn=lambda: len(ed.problems_at(("lesson",)))))
    box.add_child(_Row(("translate",), lambda: t("ed_translation"), _ICONS["translate"], "top",
                       badge_fn=ed.missing_translations))
    box.add_child(spacer(6))
    for i, s in enumerate(ed.steps):
        if s.get("type") == "scene":
            box.add_child(_Row(("step", i), lambda i=i: _loc_get(ed.step(i), "title", ed.lang) or t("ed_untitled"),
                               _ICONS["chapter"], "chapter", badge_fn=lambda i=i: len(ed.problems_at(("step", i)))))
            for j, b in enumerate(s.get("beats", [])):
                box.add_child(_Row(("beat", i, j),
                                   lambda i=i, j=j: f"{j + 1}. " + (_loc_get(ed.beat(i, j), "title", ed.lang)
                                                                    or t("ed_untitled")),
                                   _ICONS[ph.kind_of(b)], "screen",
                                   badge_fn=lambda i=i, j=j: len(ed.problems_at(("beat", i, j)))))
            add = Flow(gap=6)
            b = button("+ " + t("ed_add_screen"), lambda i=i: ed.select(("new", i)), size=12, height=30)
            add.add_child(FloatLayout(width=px(14), height=px(30), border_radius=0))
            add.add_child(b)
            box.add_child(add)
            box.add_child(spacer(4))
        elif s.get("type") == "exercise":
            box.add_child(_Row(("step", i), lambda i=i: _piece_summary(ed.step(i)), _ICONS["piece"], "piece",
                               badge_fn=lambda i=i: len(ed.problems_at(("step", i)))))
            box.add_child(spacer(4))
        else:
            box.add_child(_Row(("step", i), lambda kind=s.get("type"): str(kind), "info", "piece"))
    box.add_child(spacer(6))
    row = Flow(gap=8)
    row.add_child(button("+ " + t("ed_add_chapter"), ed.add_chapter, size=12, height=32))
    row.add_child(button("+ " + t("ed_add_piece"), ed.add_piece, size=12, height=32))
    box.add_child(row)


def _piece_summary(s: dict) -> str:
    tm = ef.time_of(s)
    n = max((len(b) for b, _ in ef.parts(s)), default=0)
    return tn("ed_piece_summary", n, time=f"{tm[0]}/{tm[1]}")


# ── pieces of the inspector ───────────────────────────────────────────────────────────

def _text_field(label: str, get, set_, lines: int = 1, placeholder: str = ""):
    box = TextBox(get(), placeholder=placeholder, min_lines=lines,
                  on_change=lambda v: (set_(v), _ED.changed()))
    return [field_label(label), box]


def _seg(segments, index, on_change, height=32):
    return SegmentedControl(segments=segments, selected_index=max(0, index),
                            on_change=on_change, width=1.0, height=px(height))


def _switch_row(label: str, value: bool, on_change):
    row = Flow(gap=10)
    row.add_child(Switch(value=value, on_change=on_change, width=px(51), height=px(31)))
    row.add_child(Label(text=label, font_size=13, color=iOSTheme.label, height=px(31)))
    return row


def _more_toggle(box):
    ed = _ED

    def flip():
        ed.more = not ed.more
        rebuild()
    row = Flow()
    row.add_child(button(("⌃ " + t("ed_fewer_options")) if ed.more else ("⌄ " + t("ed_more_options")), flip))
    box.add_child(row)


def _actions(box, what: str):
    ed = _ED
    box.add_child(heading(t("ed_" + what)))
    row = Flow()
    row.add_child(button("↑ " + t("ed_move_up"), lambda: ed.move(-1)))
    row.add_child(button("↓ " + t("ed_move_down"), lambda: ed.move(1)))
    row.add_child(button(t("ed_duplicate"), ed.duplicate))
    confirming = ed.confirm == repr(ed.sel)
    row.add_child(button(t("ed_delete_confirm") if confirming else t("ed_delete"), ed.delete,
                         kind="danger" if confirming else "plain"))
    box.add_child(row)


class _ProblemRow(UIElement):
    def __init__(self, where, text):
        super().__init__(width=1.0, height=px(30))
        self.where, self.text = where, text
        self._pressed = False

    def on_event(self, event) -> bool:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.rect.collidepoint(event.pos):
            self._pressed = True
            return True
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1 and self._pressed:
            self._pressed = False
            if self.rect.collidepoint(event.pos) and _ED:
                w = self.where
                target = ("step", w[1]) if w[0] == "bar" else w
                if target != _ED.sel:
                    _ED.select(target)
            return True
        return False

    def render(self, surface):
        r = self.rect
        pygame.draw.rect(surface, iOSTheme.secondary_background, r, border_radius=px(7))
        pygame.draw.circle(surface, _ORANGE, (r.left + px(12), r.centery), px(4))
        f = font(12)
        text = self.text
        while text and f.size(text)[0] > r.width - px(32):
            text = text[:-2] + "…"
        ts = f.render(text, True, iOSTheme.label)
        surface.blit(ts, (r.left + px(24), r.centery - ts.get_height() // 2))


def _problems(box, problems, with_place: bool = False):
    ed = _ED
    for where, code, args in problems[:30]:
        text = t("ed_problem_" + code, **args)
        if with_place:
            text = f"{ed.where_text(where)}:  {text}"
        box.add_child(_ProblemRow(where, text))


class _Card(UIElement):
    """A big choice: an icon, a name and a line on what it does."""

    def __init__(self, icon: str, title: str, text: str, on_click, width: int):
        self.title, self.text, self.on_click = title, text, on_click
        self._icon = Icon.as_icon_fn(icon, base_size=26)
        f = font(12)
        words, lines, line = text.split(), [], ""
        room = width - px(76)
        for w in words:
            test = f"{line} {w}".strip()
            if f.size(test)[0] > room and line:
                lines.append(line)
                line = w
            else:
                line = test
        if line:
            lines.append(line)
        self.lines = lines
        super().__init__(width=1.0, height=px(30) + len(lines) * f.get_linesize() + px(14))
        self._pressed = False

    def on_event(self, event) -> bool:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.rect.collidepoint(event.pos):
            self._pressed = True
            return True
        if event.type == pygame.MOUSEMOTION and self._pressed and not self.rect.collidepoint(event.pos):
            self._pressed = False
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1 and self._pressed:
            self._pressed = False
            if self.rect.collidepoint(event.pos):
                self.on_click()
            return True
        return False

    def render(self, surface):
        r = self.rect
        pygame.draw.rect(surface, iOSTheme.fill if self._pressed else iOSTheme.secondary_background, r,
                         border_radius=px(12))
        self._icon(surface, r.left + px(30), r.top + px(28), scale_of(), ColorPalette.BLUE)
        f_t, f = font(14, bold=True), font(12)
        surface.blit(f_t.render(self.title, True, iOSTheme.label), (r.left + px(60), r.top + px(10)))
        y = r.top + px(32)
        for line in self.lines:
            surface.blit(f.render(line, True, iOSTheme.secondary_label), (r.left + px(60), y))
            y += f.get_linesize()


# ── the inspector's pages ─────────────────────────────────────────────────────────────

def _fill_lesson(box):
    ed = _ED
    d, w = ed.draft, ed.page["inner_w"]
    s = d["strings"].setdefault(ed.lang, {})
    meta = d["meta"]
    box.add_child(heading(t("ed_lesson_details")))

    def set_title(v):
        s["title"] = v
        _sync_bar()
    for el in _text_field(t("ed_field_title"), lambda: s.get("title", ""), set_title):
        box.add_child(el)
    for el in _text_field(t("ed_field_description"), lambda: s.get("description", ""),
                          lambda v: s.__setitem__("description", v), lines=3,
                          placeholder=t("ed_description_ph")):
        box.add_child(el)
    box.add_child(field_label(t("ed_field_difficulty")))
    diffs = list(cs.DIFFICULTIES)
    box.add_child(_seg([t(f"ed_diff_{x}") for x in diffs],
                       diffs.index(meta.get("difficulty")) if meta.get("difficulty") in diffs else 0,
                       lambda i: (meta.__setitem__("difficulty", diffs[i]), ed.changed())))
    box.add_child(field_label(t("ed_field_minutes")))
    mins = list(range(1, 61))
    cur = int(meta.get("estimated_minutes", 5) or 5)
    box.add_child(left(Stepper(options=mins, value=cur if cur in mins else 5,
                               fmt_fn=lambda v: t("ed_minutes", n=v),
                               on_change=lambda v: (meta.__setitem__("estimated_minutes", int(v)), ed.changed()),
                               width=px(200), height=px(34))))
    _more_toggle(box)
    if ed.more:
        for el in _text_field(t("ed_field_author"), lambda: meta.get("author", ""),
                              lambda v: meta.__setitem__("author", v)):
            box.add_child(el)
        for el in _text_field(t("ed_field_tags"), lambda: ", ".join(meta.get("tags", [])),
                              lambda v: meta.__setitem__("tags", [x.strip() for x in v.split(",") if x.strip()]),
                              placeholder=t("ed_tags_ph")):
            box.add_child(el)
        box.add_child(hint(t("ed_id_hint", id=ed.id), w))
        if meta.get("based_on"):
            box.add_child(hint(t("ed_based_on", id=meta["based_on"]), w))

    box.add_child(spacer(4))
    box.add_child(heading(t("ed_check")))
    main = ed.main_problems()
    if not main:
        box.add_child(Label(text="✓ " + t("ed_no_problems"), font_size=13, bold=True, color=GREEN))
    else:
        box.add_child(hint(tn("ed_problems_hint", len(main)), w))
        _problems(box, main, with_place=True)
    if ed.missing_translations():
        box.add_child(hint(tn("ed_translations_missing", ed.missing_translations()), w))


def _fill_translate(box):
    """Every text of the lesson in every language, side by side (stacked on a phone)."""
    ed = _ED
    d, w = ed.draft, ed.page["inner_w"]
    langs = list(cs.LOCALES)
    box.add_child(heading(t("ed_translation")))
    box.add_child(hint(t("ed_translation_hint", lang=ed.lang.upper()), w))
    n_missing = ed.missing_translations()
    box.add_child(Label(text=(tn("ed_translations_missing", n_missing) if n_missing
                              else "✓ " + t("ed_translations_done")),
                        font_size=13, bold=True, color=_ORANGE if n_missing else GREEN))

    def item(label: str, get, set_, lines: int = 1):
        box.add_child(spacer(4))
        box.add_child(field_label(label))
        wide = not ed.page["narrow"]
        row = Flow(gap=8)
        values = {lang: get(lang) for lang in langs}
        filled = any(v.strip() for v in values.values())
        fw = (w - px(8)) // len(langs) if wide else w
        for lang in langs:
            col = FloatLayout(width=fw, height=px(18), border_radius=0)
            col.add_child(Label(text=lang.upper(), font_size=11, bold=True, color=iOSTheme.secondary_label,
                                anchor="bottom_left", x=0, y=0))
            if not wide:
                row.add_child(col)
            tb = TextBox(values[lang], min_lines=lines, width=fw,
                         on_change=lambda v, lang=lang: (set_(lang, v), ed.changed()))
            tb.error = filled and not values[lang].strip()
            if wide:
                stack = Flow(gap=0, line_gap=2, width=fw)
                stack.add_child(col)
                stack.add_child(tb)
                row.add_child(stack)
            else:
                row.add_child(tb)
        box.add_child(row)

    strings = d["strings"]
    item(t("ed_field_title"), lambda lang: strings.get(lang, {}).get("title", ""),
         lambda lang, v: strings.setdefault(lang, {}).__setitem__("title", v))
    item(t("ed_field_description"), lambda lang: strings.get(lang, {}).get("description", ""),
         lambda lang, v: strings.setdefault(lang, {}).__setitem__("description", v), lines=2)
    for i, s in enumerate(ed.steps):
        if s.get("type") != "scene":
            continue
        item(t("ed_where_chapter", n=i + 1), lambda lang, s=s: _loc_get(s, "title", lang),
             lambda lang, v, s=s: _loc_set(s, "title", lang, v))
        for j, b in enumerate(s.get("beats", [])):
            where = t("ed_where_beat", n=i + 1, m=j + 1)
            item(f"{where} · {t('ed_field_beat_title')}", lambda lang, b=b: _loc_get(b, "title", lang),
                 lambda lang, v, b=b: _loc_set(b, "title", lang, v))
            item(f"{where} · {t('ed_field_say')}", lambda lang, b=b: _loc_get(b, "say", lang),
                 lambda lang, v, b=b: _loc_set(b, "say", lang, v), lines=2)
            if b.get("try"):
                item(f"{where} · {t('ed_field_try_say')}", lambda lang, b=b: _loc_get(b, "try_say", lang),
                     lambda lang, v, b=b: _loc_set(b, "try_say", lang, v))


def _fill_chapter(box, i: int):
    ed = _ED
    s = ed.step(i)
    w = ed.page["inner_w"]
    box.add_child(heading(t("ed_chapter_n", n=i + 1)))
    _problems(box, ed.problems_at(("step", i)))
    for el in _text_field(t("ed_field_chapter_title"), lambda: _loc_get(s, "title", ed.lang),
                          lambda v: _loc_set(s, "title", ed.lang, v)):
        box.add_child(el)
    box.add_child(hint(tn("ed_chapter_hint", len(s.get("beats", []))), w))
    box.add_child(spacer(4))
    box.add_child(heading(t("ed_add_screen")))
    _kind_cards(box, i)
    box.add_child(spacer(6))
    _actions(box, "chapter_actions")


def _kind_cards(box, i: int):
    ed = _ED
    for kind in ph.KINDS:
        box.add_child(_Card(_ICONS[kind], t(f"ed_kind_{kind}"), t(f"ed_kind_{kind}_desc"),
                            lambda kind=kind: ed.add_screen(i, kind), ed.page["inner_w"]))


def _fill_new(box, i: int):
    ed = _ED
    box.add_child(heading(t("ed_new_screen_in", chapter=_loc_get(ed.step(i), "title", ed.lang) or t("ed_untitled"))))
    box.add_child(hint(t("ed_new_screen_hint"), ed.page["inner_w"]))
    _kind_cards(box, i)


def _fill_screen(box, i: int, j: int):
    ed = _ED
    s = ed.step(i)
    b = ed.beat(i, j)
    w = ed.page["inner_w"]
    lang = ed.lang
    kind = ph.kind_of(b)
    box.add_child(heading(t("ed_screen_n", kind=t(f"ed_kind_{kind}"), n=j + 1, total=len(s["beats"]))))
    _problems(box, ed.problems_at(("beat", i, j)))
    _add_preview(box, kind)

    # what a tap on the preview's keys does
    if kind == "explain":
        modes = ["mark", "labels"]
        box.add_child(_seg([t("ed_tap_mark"), t("ed_tap_name")], modes.index(ed.tap_mode),
                           lambda k: (setattr(ed, "tap_mode", modes[k]), rebuild())))
    elif kind == "hand":
        sides = ["right", "left"]
        box.add_child(_seg([t("ed_staff_right"), t("ed_staff_left")], sides.index(ed.hand_side),
                           lambda k: (setattr(ed, "hand_side", sides[k]), rebuild())))
    box.add_child(hint(t(f"ed_tap_hint_{kind}" + ("_" + ed.tap_mode if kind == "explain" else "")), w))
    if kind == "find":
        notes = list(b.get("try") or [])
        box.add_child(Label(text="   ".join(notes) if notes else t("ed_no_notes"), font_size=14,
                            bold=bool(notes), color=iOSTheme.label if notes else iOSTheme.secondary_label))
    if kind in ("explain", "find", "hand"):
        row = Flow()

        def undo_last():
            if kind == "find" and b.get("try"):
                b["try"].pop()
            ed.changed(structure=True)

        def clear_all():
            if kind == "explain":
                b.pop("mark" if ed.tap_mode == "mark" else "labels", None)
            elif kind == "find":
                b["try"] = []
            elif kind == "hand":
                (b.get("hand") or {}).pop(ed.hand_side, None)
                if not b.get("hand"):
                    b.pop("hand", None)
            ed.changed(structure=True)
        if kind == "find":
            row.add_child(button(t("ed_undo_note"), undo_last))
        row.add_child(button(t("ed_clear"), clear_all))
        box.add_child(row)

    for el in _text_field(t("ed_field_beat_title"), lambda: _loc_get(b, "title", lang),
                          lambda v: (_loc_set(b, "title", lang, v), _dirty.mark())):
        box.add_child(el)
    for el in _text_field(t("ed_field_say"), lambda: _loc_get(b, "say", lang),
                          lambda v: _loc_set(b, "say", lang, v), lines=3, placeholder=t("ed_say_ph")):
        box.add_child(el)

    if kind == "listen":
        b.setdefault("repeat", b.get("try") == "play" or not b.get("play"))
        model = ed.score_model(ph.ensure_music(b), b)
        box.add_child(spacer(4))
        box.add_child(heading(t("ed_phrase")))
        box.add_child(hint(t("ed_phrase_hint"), w))
        _score_block(box, model, piece=False)

        def set_repeat(v):
            b["repeat"] = bool(v)
            _compile(b)
            ed.changed(structure=True)
        box.add_child(spacer(4))
        box.add_child(_switch_row(t("ed_repeat"), bool(b.get("repeat")), set_repeat))
        if b.get("repeat"):
            for el in _text_field(t("ed_field_try_say"), lambda: _loc_get(b, "try_say", lang),
                                  lambda v: _loc_set(b, "try_say", lang, v), placeholder=t("ed_try_say_ph")):
                box.add_child(el)

        def set_staff(v):
            if v:
                b["staff"] = {"clef": "treble", "notes": []}
                b.pop("staff_own", None)
            else:
                b.pop("staff", None)
            _compile(b)
            ed.changed(structure=True)
        box.add_child(_switch_row(t("ed_show_staff"), bool(b.get("staff")), set_staff))
        st = b.get("staff")
        if st:
            unders = [None, "names", "count"]
            u = st.get("under") or ("names" if st.get("names") else None)

            def set_under(k):
                st.pop("names", None)
                if unders[k]:
                    st["under"] = unders[k]
                else:
                    st.pop("under", None)
                _compile(b)
                ed.changed()
            box.add_child(field_label(t("ed_field_under")))
            box.add_child(_seg([t("ed_none"), t("ed_under_names"), t("ed_under_count")],
                               unders.index(u) if u in unders else 0, set_under))
            if b.get("staff_own"):
                box.add_child(hint(t("ed_staff_own"), w))
                row = Flow()
                row.add_child(button(t("ed_staff_use_phrase"),
                                     lambda: (b.pop("staff_own", None), _compile(b), ed.changed(structure=True))))
                box.add_child(row)
    elif kind == "find":
        for el in _text_field(t("ed_field_try_say"), lambda: _loc_get(b, "try_say", lang),
                              lambda v: _loc_set(b, "try_say", lang, v), placeholder=t("ed_try_say_ph")):
            box.add_child(el)
    elif kind == "hand":
        box.add_child(_switch_row(t("ed_numbers"), bool(b.get("numbers")),
                                  lambda v: (b.__setitem__("numbers", True) if v else b.pop("numbers", None),
                                             ed.changed())))

    box.add_child(spacer(4))
    _more_toggle(box)
    if ed.more:
        box.add_child(field_label(t("ed_field_kind")))
        box.add_child(_seg([t(f"ed_kind_{k}") for k in ph.KINDS], list(ph.KINDS).index(kind),
                           lambda k: ed.set_kind(ph.KINDS[k])))
        if kind != "listen":
            labels = b.get("labels")
            lmode = _LABEL_MODES.index(labels) if labels in _LABEL_MODES else 0

            def set_labels(k):
                m = _LABEL_MODES[k]
                if m is None:
                    if not isinstance(b.get("labels"), list):
                        b.pop("labels", None)
                else:
                    b["labels"] = m
                ed.changed()
            box.add_child(field_label(t("ed_field_labels")))
            box.add_child(_seg([t("ed_labels_chosen"), t("ed_labels_c"), t("ed_labels_white"),
                                t("ed_labels_hand")], lmode, set_labels))
        else:
            accents = [0, 2, 3, 4]
            acc = int(b.get("accent", 0) or 0)
            box.add_child(field_label(t("ed_field_accent")))
            box.add_child(_seg([t("ed_none"), "2", "3", "4"], accents.index(acc) if acc in accents else 0,
                               lambda k: (b.__setitem__("accent", accents[k]) if accents[k]
                                          else b.pop("accent", None), ed.changed())))
            _score_more(box, ed.score_model(ph.ensure_music(b), b), piece=False)
    box.add_child(spacer(6))
    _actions(box, "screen_actions")


def _fill_piece(box, i: int):
    ed = _ED
    s = ed.step(i)
    w = ed.page["inner_w"]
    model = ed.score_model(s)
    box.add_child(heading(t("ed_piece_n", n=i + 1)))
    _problems(box, ed.problems_at(("step", i)))
    box.add_child(hint(t("ed_piece_hint"), w))
    _score_block(box, model, piece=True)
    box.add_child(spacer(4))
    _more_toggle(box)
    if ed.more:
        _score_more(box, model, piece=True)
    box.add_child(spacer(6))
    _actions(box, "piece_actions")


# ── the score editor block (a screen's phrase or a piece) ─────────────────────────────

def _score_block(box, model, piece: bool):
    from pianove.score_editor import ScoreCanvas, GlyphButton, TextToggle, VALUES
    ed = _ED
    w = ed.page["inner_w"]
    touch = is_touch_layout()
    music = model.step
    rec = ed.recorder if ed.recorder is not None and ed.recorder.model is model else None

    # recording, tempo
    row = Flow(gap=8)
    if rec is not None and rec.active:
        row.add_child(TextToggle(lambda: (t("ed_counting", n=rec.count_text()) if rec.count_text()
                                          else "■ " + t("ed_stop")),
                                 lambda: ed.stop_recording(keep=True), active_fn=lambda: True,
                                 alt_text="■ " + t("ed_counting", n="4")))
        row.add_child(button(t("ed_cancel"), lambda: ed.stop_recording(keep=False), height=40))
    else:
        row.add_child(button("● " + t("ed_record"), ed.start_recording, kind="danger", height=40))
    tempos = sorted(set(list(range(40, 209, 4)) + [ef.tempo_of(music)]))
    row.add_child(Stepper(options=tempos, value=ef.tempo_of(music), fmt_fn=lambda v: f"{v} BPM",
                          on_change=lambda v: (music.__setitem__("tempo", int(v)), model._commit()),
                          width=px(180), height=px(40)))
    box.add_child(row)
    if rec is not None and rec.active:
        box.add_child(hint(t("ed_recording_hint_metronome"), w, color=RED))

    # the palette
    pal = Flow(gap=6)
    for v in VALUES:
        pal.add_child(GlyphButton(v, lambda v=v: model.set_value(v), active_fn=lambda v=v: model.value == v))
    pal.add_child(GlyphButton("dot", model.toggle_dot, active_fn=lambda: model.dot))
    pal.add_child(TextToggle(lambda: "3", model.toggle_triplet, active_fn=lambda: model.triplet))
    pal.add_child(GlyphButton("rest", model.rest))

    def tied():
        cur = model.selected()
        notes = ef.notes_of(cur) if cur is not None else []
        return bool(notes) and all(tie for _, tie in notes)
    pal.add_child(TextToggle(lambda: t("ed_tie"), model.tie, active_fn=tied))
    pal.add_child(TextToggle(lambda: t("ed_chord"), lambda: setattr(model, "chord", not model.chord),
                             active_fn=lambda: model.chord))
    box.add_child(pal)
    if model.n_staves == 2:
        srow = Flow(gap=6)
        for k, key in enumerate(("ed_staff_right", "ed_staff_left")):
            srow.add_child(TextToggle(lambda key=key: t(key), lambda k=k: model.set_staff(k),
                                      active_fn=lambda k=k: model.staff == k))
        box.add_child(srow)

    def key():
        from pianove.pages.lesson import _guess_key as guess
        return guess([b for st in range(model.n_staves) for b in ef.music(music, st)[0]])

    i = ed.sel[1]

    def bad_bars():
        return {where[2] for where, _, _ in ed.problems if where[0] == "bar" and where[1] == i} if piece else set()
    canvas = ScoreCanvas(model, key_fn=key, problems_fn=bad_bars, height=px(140),
                         min_space=max(13, px(13)), touch=touch)
    erow = Flow(gap=6)
    erow.add_child(button("↑", lambda: model.transpose(1), min_w=44, height=40))
    erow.add_child(button("↓", lambda: model.transpose(-1), min_w=44, height=40))
    erow.add_child(button(t("ed_oct_up"), lambda: model.transpose(12), height=40))
    erow.add_child(button(t("ed_oct_down"), lambda: model.transpose(-12), height=40))
    erow.add_child(button(t("ed_delete_note"), model.delete, height=40))
    erow.add_child(button(t("ed_undo"), model.undo, height=40))
    erow.add_child(button(t("ed_redo"), model.redo, height=40))
    erow.add_child(TextToggle(lambda: ("■ " + t("ed_stop_play")) if canvas.is_playing else ("▶ " + t("ed_play")),
                              canvas.toggle_play, active_fn=lambda: canvas.is_playing,
                              alt_text="■ " + t("ed_stop_play")))
    box.add_child(erow)
    box.add_child(canvas)
    ed.page["score"] = canvas

    # fingers
    frow = Flow(gap=6)
    frow.add_child(Label(text=t("ed_fingers"), font_size=13, bold=True, color=iOSTheme.label, height=px(40)))
    for f in range(1, 6):
        frow.add_child(TextToggle(lambda f=f: str(f), lambda f=f: model.set_finger(f)))
    frow.add_child(button(t("ed_suggest_fingers"), model.suggest_fingering, height=40))
    frow.add_child(button(t("ed_clear"), model.clear_fingers, height=40))
    box.add_child(frow)
    box.add_child(hint(t("ed_score_hint_touch") if touch else t("ed_score_hint"), w))

    if piece:                                    # a piece has no preview: keys to enter notes
        picker = ed.entry_picker

        def decor(m):
            cur = model.selected()
            on = cur is not None and m in [parse_chord(p)[0] for p in ef.pitches_of(cur) if parse_chord(p)]
            return (ColorPalette.BLUE if on else None, None)

        def down(m):
            if ed.recorder is not None and ed.recorder.active and ed.recorder.model is model:
                ed.recorder.key_down(m)
            else:
                model.key_note(m)
        picker.on_key = down
        picker.on_key_up = lambda m: ed.preview_release(m)
        picker.decorate = decor
        whites = max(14, min(29, int(w / px(30))))
        picker.octaves = max(2, min(4, whites // 7))
        if getattr(picker, "fitted_for", None) is not (music, model.staff):
            picker.fitted_for = (music, model.staff)
            notes = [m for bar in ef.music(music, model.staff)[0] for p in bar for m in (parse_chord(p) or [])]
            bass = model.staff == 1 or music.get("clef") == "bass"
            picker.fit(notes or ([43, 55] if bass else [60, 72]))
        box.add_child(PygameCanvas(target=picker, draw_border=False, width=1.0, height=px(110)))
        krow = Flow()
        krow.add_child(button("‹ " + t("ed_lower"), lambda: picker.shift(-1)))
        krow.add_child(button(t("ed_higher") + " ›", lambda: picker.shift(1)))
        box.add_child(krow)
    if not touch:
        box.add_child(hint(t("ed_score_keys"), w))


def _score_more(box, model, piece: bool):
    """The rarely needed settings of a phrase or piece."""
    ed = _ED
    music = model.step
    box.add_child(field_label(t("ed_field_time")))
    tm = ef.time_of(music)
    times = [list(x) for x in _TIMES]
    if tm not in times:
        times.append(list(tm))
    box.add_child(_seg([f"{a}/{b}" for a, b in times], times.index(tm), lambda k: model.set_time(times[k])))
    box.add_child(field_label(t("ed_field_hands")))
    box.add_child(_seg([t("ed_hands_one"), t("ed_hands_both")], model.n_staves - 1,
                       lambda k: (model.set_hands(k == 1), rebuild())))
    if model.n_staves == 1:
        clefs = ["treble", "bass"]

        def set_clef(k):
            music["clef"] = clefs[k]
            model._commit()
        box.add_child(field_label(t("ed_field_clef")))
        box.add_child(_seg([t("ed_clef_treble"), t("ed_clef_bass")],
                           clefs.index(music.get("clef", "treble")) if music.get("clef", "treble") in clefs else 0,
                           set_clef))
    brow = Flow()
    brow.add_child(button("+ " + t("ed_add_bar"), model.add_bar))
    brow.add_child(button(t("ed_delete_bar"), model.delete_bar))
    if piece:
        brow.add_child(button(t("ed_import_xml"), _import_xml))

    def clear_bars():
        if ed.confirm != "bars":
            ed.confirm, ed.confirm_t = "bars", time.monotonic()
            rebuild()
            return
        ed.confirm = None
        model.clear()
        rebuild()
    confirming = ed.confirm == "bars"
    brow.add_child(button(t("ed_clear_bars_confirm") if confirming else t("ed_clear_bars"),
                          clear_bars, kind="danger" if confirming else "plain"))
    box.add_child(brow)
    if piece:
        box.add_child(field_label(t("ed_import_hand")))
        box.add_child(_seg([t("ed_hand_right"), t("ed_hand_left"), t("ed_hands_both")], ed.import_hand,
                           lambda k: setattr(ed, "import_hand", k)))


# ── the preview ───────────────────────────────────────────────────────────────────────

class _QuietPanel:
    """What the preview's scene sees of the keyboard: the keys held (to light them), but
    no key presses of its own; the editor takes those."""

    def __init__(self):
        self.active_notes: set = set()
        self.mic = None
        self.input_mode = "midi"

    def update(self, dt, rect):
        pass

    def take_note_ons(self):
        return []

    def expect(self, notes):
        pass


class _Preview:
    """The selected screen drawn by the lesson player's own scene code. A tap on its keys
    edits the screen (see _Editor.preview_tap)."""

    def __init__(self):
        self.scene = None
        self.wait = 0.0
        self.error = ""
        self.sel = None
        self.quiet = _QuietPanel()
        self._down = None

    def stop(self):
        if self.scene is not None:
            try:
                self.scene._stop_sounds()
            except Exception:
                pass

    def _build(self, ed, autoplay: bool):
        self.stop()
        self.scene, self.error = None, ""
        try:
            if ed.sel[0] == "beat":
                _, i, j = ed.sel
                raw = {"title": ed.step(i).get("title"), "beats": [copy.deepcopy(ed.beat(i, j))]}
                from pianove.pages.theory import Scene
                self.scene = Scene(raw)
                self.scene._panel = self.quiet
                if not autoplay and self.scene.phase == "demo":
                    self.scene.phase = "show"          # edited: not played again by itself
        except Exception:
            self.scene, self.error = None, t("ed_preview_error")
        self.sel = ed.sel

    def update(self, dt, rect):
        ed = _ED
        if ed is None:
            return
        if ed.preview_dirty or self.sel != ed.sel:
            self.wait += dt
            if self.wait > 0.25 or self.sel != ed.sel:
                autoplay = ed.preview_autoplay or self.sel != ed.sel
                ed.preview_dirty = False
                self.wait = 0.0
                self._build(ed, autoplay)
                _dirty.mark()
        recording = ed.recorder is not None and ed.recorder.active
        if self.scene is not None and not recording:
            try:
                self.scene.update(dt, rect)
            except Exception:
                self.scene, self.error = None, t("ed_preview_error")

    def draw(self, surface, rect):
        surface.fill(iOSTheme.background, rect)
        if self.scene is not None:
            try:
                self.scene.draw(surface, rect)
                return
            except Exception:
                self.scene, self.error = None, t("ed_preview_error")
        ts = font(13).render(self.error or t("ed_preview_empty"), True, iOSTheme.secondary_label)
        surface.blit(ts, ts.get_rect(center=rect.center))

    def handle_event(self, event, rect) -> bool:
        ed = _ED
        if self.scene is None or ed is None:
            return False
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and rect.collidepoint(event.pos):
            m = self.scene._key_at(event.pos)
            if m is None:
                return False
            self._down = m
            _sound(m, True)
            ed.preview_tap(m)
            return True
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1 and self._down is not None:
            m, self._down = self._down, None
            _sound(m, False)
            ed.preview_release(m)
            return True
        return False


_PREVIEW = _Preview()


def _add_preview(box, kind: str):
    ed = _ED
    h = px(280) if not ed.page["narrow"] else max(px(220), min(px(320), int(ed.page["inner_w"] * 0.42)))
    frame = FloatLayout(width=1.0, height=h, background_color=iOSTheme.background, border_radius=px(12))
    frame.add_child(PygameCanvas(target=_PREVIEW, draw_border=False, width=1.0, height=1.0))
    box.add_child(frame)
    row = Flow()
    row.add_child(button("▶ " + t("ed_play_screen"), lambda: _PREVIEW.scene.replay() if _PREVIEW.scene else None))
    box.add_child(row)


def _sync_screen_notes():
    _dirty.mark()


# ── importing a piece from MusicXML ───────────────────────────────────────────────────

def _import_xml():
    ed = _ED
    picker = ed.page.get("file_picker")
    if picker is None or ed.sel[0] != "step":
        return
    i = ed.sel[1]

    def got(path):
        if not path or _ED is not ed:
            return
        try:
            ex = cs.exercise_from_musicxml(path, ["right", "left", "both"][ed.import_hand])
        except Exception as e:
            _toast(t("ed_import_failed", error=str(e)[:80]), RED)
            return
        if not ex["bars"]:
            _toast(t("ed_import_empty"), RED)
            return
        s = ed.step(i)
        if ed.import_hand == 1:
            s["clef"] = "bass"
        ed.score_model(s).replace_all(ex["time"], ex["bars"], ex["types"], lh=ex.get("lh"))
        rebuild()
        _toast(t("ed_imported_bars", n=len(ex["bars"])), GREEN)
    picker.pick(got)


# ── the page ──────────────────────────────────────────────────────────────────────────

def _toast(text: str, color=None):
    toast = _ED.page.get("toast") if _ED else None
    if toast:
        toast.show(text, color=color)


def _sync_bar():
    ed = _ED
    if ed is None:
        return
    p = ed.page
    if "title" in p:
        text, f, room = ed.title(), font(15, bold=True), p.get("title_max", 10_000)
        while len(text) > 1 and f.size(text)[0] > room:
            text = text[:-2] + "…"
        p["title"].text = text
        p["title"]._text_surf_cache.clear()
        p["title"].request_layout()
    save = p.get("save")
    if save is not None:
        save.text = t("ed_save") if ed.dirty else "✓ " + t("ed_saved")
        save.background_color = ColorPalette.BLUE if ed.dirty else iOSTheme.fill
        save.text_color = WHITE if ed.dirty else iOSTheme.label
        save._cache_key = None
    _dirty.mark()


def rebuild(scroll_top: bool = False):
    """Refill the outline and the inspector from the draft."""
    ed = _ED
    if ed is None or "inspector" not in ed.page:
        return
    p = ed.page
    if "score" in p:
        p.pop("score").stop()
    if TextBox._focused is not None:
        TextBox._focused.focus(False)
    _fill_outline(p["outline"])
    box = p["inspector"]
    keep = box.scroll_target
    _clear(box)
    sel = ed.sel
    try:
        if sel[0] == "beat":
            _fill_screen(box, sel[1], sel[2])
        elif sel[0] == "new":
            _fill_new(box, sel[1])
        elif sel[0] == "translate":
            _fill_translate(box)
        elif sel[0] == "step":
            kind = ed.step(sel[1]).get("type")
            if kind == "exercise":
                _fill_piece(box, sel[1])
            elif kind == "scene":
                _fill_chapter(box, sel[1])
            else:
                box.add_child(hint(t("ed_unknown_step"), p["inner_w"]))
                _actions(box, "piece_actions")
        else:
            _fill_lesson(box)
    except (IndexError, KeyError):
        ed.sel = ("lesson",)
        _clear(box)
        _fill_lesson(box)
    box.add_child(spacer(24))
    if p["narrow"]:
        p["outline"].visible = ed.show_outline
        box.visible = not ed.show_outline
        p["where"].text = _where_short(ed)
        p["where"]._text_surf_cache.clear()
    p["root"].layout()
    box.scroll_target = box.scroll_offset = 0.0 if scroll_top else min(keep, box.scroll_max)
    p["root"].request_layout()
    _sync_bar()
    _dirty.mark()


def _where_short(ed) -> str:
    sel = ed.sel
    if sel[0] == "lesson":
        return t("ed_lesson_details")
    if sel[0] == "translate":
        return t("ed_translation")
    if sel[0] == "new":
        return t("ed_add_screen")
    if sel[0] == "step":
        return t("ed_where_step", n=sel[1] + 1)
    return t("ed_where_beat", n=sel[1] + 1, m=sel[2] + 1)


def _back():
    ed = _ED
    _PREVIEW.stop()
    if ed is not None:
        ed.stop_recording(keep=True)
        if ed.dirty:
            ed.save()
    _leave()
    ctx.router.navigate("home", "left")


def _leave():
    global _ED
    from pianove.creator_ui import restore_scale
    _ED = None
    if TextBox._focused is not None:
        TextBox._focused.focus(False)
    restore_scale()


def _test():
    ed = _ED
    if ed is None:
        return
    ed.stop_recording(keep=True)
    if not ed.save():
        return
    _PREVIEW.stop()
    sel = ed.sel
    start = sel[1] if sel[0] in ("step", "beat", "new") else 0
    ctx.current_lesson_id = ed.id
    ctx.current_course_id = None
    ctx.current_song_id = None
    ctx.practice_mode = False
    ctx.lesson_step_idx = start
    ctx.lesson_beat_idx = sel[2] if sel[0] == "beat" else 0
    ctx.lesson_current_idx = 0
    ctx.lesson_section_idx = 0
    ctx.lesson_phase = "practice"
    ctx.lesson_completed = False
    ctx.lesson_test_return = "lesson_editor"
    from pianove.creator_ui import restore_scale
    restore_scale()                          # the lesson player at the app's own scale
    ctx.router.navigate("lesson", "right")


def _tick(dt: float):
    ed = _ED
    if ed is None:
        return
    p = ed.page
    if "toast" in p:
        p["toast"].tick()
    if ed.confirm and time.monotonic() - ed.confirm_t > 4.0 and ed.confirm != "bars":
        ed.confirm = None
        rebuild()
    from pianove.state import midi_panel
    try:
        midi_panel.update(dt, pygame.Rect(0, 0, 1, 1))
    except Exception:
        pass
    ons = midi_panel.take_note_ons()
    live = set(midi_panel.active_notes)
    ups, ed._live = ed._live - live, live
    rec = ed.recorder
    if rec is not None and rec.active:
        for m in ons:
            rec.key_down(m)
        for m in ups:
            rec.key_up(m)
        rec.tick()
    elif rec is not None:
        rec.tick()                             # the last metronome click lets go
    elif ons:
        b = ed.cur_beat()
        model = ed.current_model()
        if model is not None:                  # playing writes notes at the cursor
            for m in ons:
                model.key_note(m)
        elif b is not None and ph.kind_of(b) in ("find", "explain", "hand"):
            for m in ons:
                ed.preview_tap(m)
    _PREVIEW.quiet.active_notes = live
    if live != ed.entry_picker.live:
        ed.entry_picker.live = live
        _dirty.mark()


def build():
    global _ED
    lesson_id = getattr(ctx, "editor_lesson_id", None)
    if _ED is None or _ED.id != lesson_id:
        try:
            _ED = _Editor(lesson_id)
        except KeyError:
            _ED = None
            ctx.router.navigate("home", "left")
            return FloatLayout(width=1.0, height=1.0, background_color=iOSTheme.background)
    ed = _ED
    ed.page = {}
    ed.recorder = None
    ed.preview_dirty = True
    ed.preview_autoplay = True
    _PREVIEW.sel = None

    from pianove.creator_ui import apply_page_scale
    apply_page_scale()                       # bigger on a phone or tablet
    W = ctx.ui.width if ctx.ui else 1024
    H = ctx.ui.height if ctx.ui else 768
    narrow = is_narrow(W, H)
    pad = px(16)
    bar_h = px(56)
    outline_w = px(270)

    root = FloatLayout(width=1.0, height=1.0, background_color=iOSTheme.background, border_radius=0)
    ed.page.update(root=root, narrow=narrow)
    root.add_child(Ticker(_tick))
    fp = FilePicker(title=t("ed_import_xml_title"),
                    filters=["MusicXML | *.xml *.musicxml *.mxl", "All files | *"])
    root.add_child(fp)
    ed.page["file_picker"] = fp

    # top bar
    bar = FloatLayout(anchor="top_left", x=0, y=0, width=1.0, height=bar_h,
                      background_color=iOSTheme.secondary_background, border_radius=0)
    back = button("‹ " + t("back"), _back, height=36)
    back.anchor, back.x_spec, back.y_spec = "left", px(10), 0
    bar.add_child(back)
    right = Flow(gap=8, align="right", anchor="right", x=-px(10), y=0, width=px(320), height=px(36))
    right.add_child(button(("▶ " + t("ed_test")) if not narrow else "▶", _test, kind="good", height=36))
    save_w = max(text_w(t("ed_save"), 13), text_w("✓ " + t("ed_saved"), 13)) + px(26)
    save = button(t("ed_save"), lambda: (ed.save() and _toast(t("ed_saved_toast"), GREEN)),
                  kind="primary", height=36, min_w=save_w / scale_of())
    right.add_child(save)
    ed.page["save"] = save
    bar.add_child(right)
    title_x = back.width_spec + px(22)
    right_used = sum(int(c.width_spec) for c in right.children) + px(8) * (len(right.children) - 1)
    ed.page["title_max"] = W - title_x - right_used - px(30)
    title = Label(text=ed.title(), font_size=15, bold=True, color=iOSTheme.label,
                  anchor="left", x=title_x, y=0)
    bar.add_child(title)
    ed.page["title"] = title
    root.add_child(bar)
    root.add_child(FloatLayout(anchor="top_left", x=0, y=bar_h, width=1.0, height=1,
                               background_color=pygame.Color(120, 120, 128, 60), border_radius=0))

    body_y = bar_h + 1
    toast_h = px(26)
    if narrow:
        nav_h = px(48)
        nav = FloatLayout(anchor="top_left", x=0, y=body_y, width=1.0, height=nav_h,
                          background_color=iOSTheme.background, border_radius=0)
        nrow = Flow(gap=8, anchor="left", x=px(10), y=0, width=W - px(20), height=px(34))
        nrow.add_child(button(t("ed_outline"), _toggle_outline, height=34,
                              kind="primary" if ed.show_outline else "plain"))
        nrow.add_child(button("‹", lambda: ed.step_by(-1), height=34, min_w=40))
        nrow.add_child(button("›", lambda: ed.step_by(1), height=34, min_w=40))
        nav.add_child(nrow)
        root.add_child(nav)
        where = Label(text="", font_size=12, bold=True, color=iOSTheme.secondary_label,
                      anchor="top_left", x=pad, y=body_y + nav_h)
        root.add_child(where)
        ed.page["where"] = where
        top = body_y + nav_h + px(20)
        content_h = H - top - toast_h
        outline = DragScroll(spacing=px(4), padding=px(10), anchor="top_left", x=0, y=top,
                             width=1.0, height=content_h, background_color=iOSTheme.background,
                             border_radius=0)
        inspector = DragScroll(spacing=px(8), padding=pad, anchor="top_left", x=0, y=top,
                               width=1.0, height=content_h, background_color=iOSTheme.background,
                               border_radius=0)
        ed.page["inner_w"] = W - 2 * pad
    else:
        content_h = H - body_y - toast_h
        outline = DragScroll(spacing=px(4), padding=px(10), anchor="top_left", x=0, y=body_y,
                             width=outline_w, height=content_h,
                             background_color=iOSTheme.secondary_background, border_radius=0)
        root.add_child(FloatLayout(anchor="top_left", x=outline_w, y=body_y, width=1, height=content_h,
                                   background_color=pygame.Color(120, 120, 128, 60), border_radius=0))
        insp_w = W - outline_w - 1
        iw = min(insp_w, px(820))
        inspector = DragScroll(spacing=px(8), padding=pad, anchor="top_left",
                               x=outline_w + 1 + (insp_w - iw) // 2, y=body_y,
                               width=iw, height=content_h, background_color=iOSTheme.background,
                               border_radius=0)
        ed.page["inner_w"] = iw - 2 * pad
    root.add_child(outline)
    root.add_child(inspector)
    ed.page["outline"] = outline
    ed.page["inspector"] = inspector

    tbar = FloatLayout(anchor="bottom_left", x=0, y=0, width=1.0, height=toast_h,
                       background_color=iOSTheme.background, border_radius=0)
    tl = Label(text="", font_size=12, color=iOSTheme.secondary_label, anchor="left", x=pad, y=0)
    tbar.add_child(tl)
    root.add_child(tbar)
    ed.page["toast"] = Toast(tl)

    rebuild()
    return root


def _toggle_outline():
    ed = _ED
    if ed:
        ed.show_outline = not ed.show_outline
        ctx.router.reload_current_page()      # the Steps button shows whether it is open


def open_lesson(lesson_id: str):
    """Open the editor on a lesson (from the Creator tab)."""
    global _ED
    _ED = None
    ctx.editor_lesson_id = lesson_id
    ctx.router.navigate("lesson_editor", "right")
