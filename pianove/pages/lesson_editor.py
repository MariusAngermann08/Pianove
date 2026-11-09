"""The lesson editor (Creator Mode): edit a lesson's details, its scenes and their beats,
and its exercises, with a live preview drawn by the same code the lesson player uses.

Notes are entered by playing them: on a MIDI keyboard, through the microphone, or by
tapping the keyboard on screen. Keys struck together become a chord.

On a wide window the outline of the lesson sits on the left and the selected part on the
right; on a narrow one (a phone held upright) the outline opens over the page instead.
"""
from __future__ import annotations

import copy
import time

import pygame
from pylay import FloatLayout, Label, SegmentedControl, Stepper, Switch, PygameCanvas, FilePicker, iOSTheme, ColorPalette
from pylay.core.element import UIElement
from pylay.core import _dirty

import pianove.context as ctx
from pianove.i18n import t, language_state
from pianove import creator_store as cs
from pianove.creator_notes import (parse_chord, chord_name, note_name, group_chords,
                                   split_bars, split_words)
from pianove.creator_ui import (px, unpx, is_narrow, tn, left, font, text_w, button, Flow, DragScroll, TextBox, KeyPicker,
                                heading, field_label, hint, spacer, Ticker, Toast,
                                WHITE, RED, GREEN)

_ORANGE = pygame.Color(255, 159, 10)
_LABEL_MODES = [None, "list", "C", "white", "hand"]
_TIMES = [[2, 4], [3, 4], [4, 4], [6, 8]]
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


# ── the editor's state ────────────────────────────────────────────────────────────────

class _Editor:
    def __init__(self, lesson_id: str):
        self.id = lesson_id
        self.draft = cs.load_draft(lesson_id)
        self.sel: tuple = ("lesson",)
        self.lang = language_state.value if language_state.value in cs.LOCALES else "en"
        self.dirty = False
        self.problems = cs.validate(self.draft)
        self.rec: dict | None = None         # {"target", "events": [(t, midi)]} while recording
        self.preview_dirty = True
        self.show_outline = False
        self.picker_mode = "mark"
        self.import_hand = 0
        self.confirm: str | None = None      # a delete button waiting for its second tap
        self.confirm_t = 0.0
        self.picker = KeyPicker(self._picker_key, self._picker_decor)
        self.page: dict = {}

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

    def title(self, lang: str | None = None) -> str:
        lang = lang or (language_state.value if language_state.value in cs.LOCALES else "en")
        s = self.draft["strings"]
        return (s.get(lang, {}).get("title") or s.get("en", {}).get("title") or self.id)

    def changed(self, structure: bool = False):
        self.dirty = True
        self.problems = cs.validate(self.draft)
        self.preview_dirty = True
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

    # ── selection ──
    def select(self, sel: tuple):
        if self.rec:
            self.stop_record()
        self.sel = sel
        self.confirm = None
        self.preview_dirty = True
        self.show_outline = False
        b = self.cur_beat()
        if b is not None:
            names = list(b.get("play", [])) + list(b.get("mark", []))
            for fm in (b.get("hand") or {}).values():
                names += list(fm or {})
            notes = [m for p in names for m in (parse_chord(p) or [])]
            if notes:
                self.picker.fit(notes)
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

    def problems_at(self, sel: tuple) -> int:
        n = 0
        for where, _, _ in self.problems:
            if sel == ("lesson",) and where[0] == "lesson":
                n += 1
            elif sel[0] == "step" and where[0] in ("step", "bar") and where[1] == sel[1]:
                n += 1
            elif sel[0] == "beat" and where == sel:
                n += 1
        return n

    # ── recording notes ──
    def start_record(self, target: str):
        from pianove.state import midi_panel
        midi_panel.take_note_ons()
        self.rec = {"target": target, "events": []}
        rebuild()

    def rec_names(self) -> list[str]:
        return [chord_name(c) for c in group_chords(self.rec["events"])] if self.rec else []

    def rec_undo(self):
        if self.rec and self.rec["events"]:
            groups = group_chords(self.rec["events"])
            n = len(groups[-1])
            self.rec["events"] = self.rec["events"][:-n]
            _sync_rec()

    def cancel_record(self):
        self.rec = None
        rebuild()

    def stop_record(self):
        rec, self.rec = self.rec, None
        if not rec or not rec["events"]:
            rebuild()
            return
        chords = group_chords(rec["events"])
        names = [chord_name(c) for c in chords]
        target = rec["target"]
        if target == "bars":
            st = self.step(self.sel[1])
            per = (st.get("time") or [4, 4])[0]
            st.setdefault("bars", []).extend(split_bars([note_name(max(c)) for c in chords], per))
        else:
            b = self.cur_beat()
            if b is None:
                rebuild()
                return
            if target == "play":
                old = b.get("play", [])
                b["play"] = names
                if len(old) != len(names):
                    b.pop("fingers", None)
                    b.pop("velocities", None)
            elif target == "try":
                b["try"] = names
            elif target == "staff":
                b.setdefault("staff", {"clef": "treble"})["notes"] = names
        self.changed(structure=True)

    def _picker_key(self, m: int):
        if self.rec:
            self.rec["events"].append((time.monotonic(), m))
            _sync_rec()
            return
        b = self.cur_beat()
        if b is None:
            return
        name = note_name(m)
        mode = self.picker_mode
        if mode == "mark":
            marks = list(b.get("mark", []))
            hit = [x for x in marks if (parse_chord(x) or [None])[0] == m]
            b["mark"] = [x for x in marks if x not in hit] if hit else marks + [name]
            if not b["mark"]:
                b.pop("mark")
        elif mode == "labels":
            labels = b.get("labels")
            labels = list(labels) if isinstance(labels, list) else []
            hit = [x for x in labels if (parse_chord(x) or [None])[0] == m]
            b["labels"] = [x for x in labels if x not in hit] if hit else labels + [name]
            if not b["labels"]:
                b.pop("labels")
        else:
            side = "right" if mode == "right" else "left"
            hand = b.setdefault("hand", {})
            fm = hand.setdefault(side, {})
            key = next((k for k in fm if (parse_chord(k) or [None])[0] == m), None)
            f = int(fm.pop(key)) + 1 if key else 1      # 1 → 2 → … → 5 → no finger
            if f <= 5:
                fm[name] = f
            hand[side] = dict(sorted(fm.items(), key=lambda kv: (parse_chord(kv[0]) or [0])[0]))
            if not hand.get(side):
                hand.pop(side, None)
            if not hand:
                b.pop("hand", None)
        self.changed()
        _sync_rows()

    def _picker_decor(self, m: int):
        if self.rec:
            names = [x for c in group_chords(self.rec["events"]) for x in c]
            return (ColorPalette.BLUE if m in names else None, None)
        b = self.cur_beat()
        if b is None:
            return (None, None)
        for side, col in (("right", pygame.Color(10, 132, 255)), ("left", pygame.Color(255, 159, 10))):
            for k, f in ((b.get("hand") or {}).get(side) or {}).items():
                if (parse_chord(k) or [None])[0] == m:
                    return (col, str(f))
        marked = any((parse_chord(x) or [None])[0] == m for x in b.get("mark", []))
        labels = b.get("labels")
        named = isinstance(labels, list) and any((parse_chord(x) or [None])[0] == m for x in labels)
        if marked:
            return (pygame.Color(94, 92, 230), note_name(m)[:-1] if named else None)
        if named:
            return (None, note_name(m)[:-1])
        return (None, None)

    # ── the lesson's structure ──
    def add_scene(self):
        n = sum(1 for s in self.steps if s.get("type") == "scene") + 1
        scene = {"type": "scene",
                 "title": {lang: _tl("ed_new_scene_title", lang, n=n) for lang in cs.LOCALES},
                 "beats": [_new_beat(1)]}
        at = len(self.steps) - 1 if self.steps and self.steps[-1].get("type") == "exercise" else len(self.steps)
        self.steps.insert(at, scene)
        self.sel = ("beat", at, 0)
        self.changed(structure=True)

    def add_exercise(self):
        self.steps.append({"type": "exercise", "time": [4, 4], "bars": [["C4", "D4", "E4", "F4"]]})
        self.sel = ("step", len(self.steps) - 1)
        self.changed(structure=True)

    def add_beat(self, i: int, after: int | None = None):
        beats = self.step(i).setdefault("beats", [])
        at = len(beats) if after is None else after + 1
        beats.insert(at, _new_beat(len(beats) + 1))
        self.sel = ("beat", i, at)
        self.changed(structure=True)

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


def _new_beat(n: int) -> dict:
    return {"title": {lang: _tl("ed_new_beat_title", lang, n=n) for lang in cs.LOCALES},
            "say": {lang: "" for lang in cs.LOCALES},
            "tempo": 76}


def _tl(key: str, lang: str, **kw) -> str:
    """A text in a given language (a new beat gets its title in every language at once)."""
    from pianove.i18n import _load
    text = _load(lang).get(key) or _load("en").get(key, key)
    return text.format(**kw) if kw else text


# ── the outline (list of the lesson's parts) ──────────────────────────────────────────

class _Row(UIElement):
    def __init__(self, sel: tuple, text_fn, depth: int = 0, tag: str = ""):
        super().__init__(width=1.0, height=px(40 if depth == 0 else 34))
        self.sel, self.text_fn, self.depth, self.tag = sel, text_fn, depth, tag
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
        if selected:
            pygame.draw.rect(surface, ColorPalette.BLUE, r, border_radius=px(8))
        elif self._pressed:
            pygame.draw.rect(surface, iOSTheme.fill, r, border_radius=px(8))
        fg = WHITE if selected else iOSTheme.label
        sub = WHITE if selected else iOSTheme.secondary_label
        x = r.left + px(10) + px(16) * self.depth
        right = r.right - px(10)
        n = ed.problems_at(self.sel)
        if n:
            pygame.draw.circle(surface, WHITE if selected else _ORANGE, (right - px(5), r.centery), px(5))
            right -= px(16)
        f_tag = font(11, bold=True)
        if self.tag:
            ts = f_tag.render(self.tag, True, sub)
            surface.blit(ts, (x, r.centery - ts.get_height() // 2))
            x += ts.get_width() + px(8)
        f = font(13 if self.depth == 0 else 12, bold=self.depth == 0)
        text = self.text_fn()
        while text and f.size(text)[0] > right - x:
            text = text[:-2] + "…" if len(text) > 2 else ""
        ts = f.render(text, True, fg)
        surface.blit(ts, (x, r.centery - ts.get_height() // 2))


def _fill_outline(box):
    ed = _ED
    _clear(box)
    box.add_child(_Row(("lesson",), lambda: t("ed_lesson_details")))
    for i, s in enumerate(ed.steps):
        kind = s.get("type")
        if kind == "scene":
            box.add_child(_Row(("step", i), lambda i=i: _loc_get(ed.step(i), "title", ed.lang)
                               or t("ed_untitled"), tag=t("ed_tag_scene").upper()))
            for j in range(len(s.get("beats", []))):
                box.add_child(_Row(("beat", i, j),
                                   lambda i=i, j=j: f"{j + 1}. " + (_loc_get(ed.beat(i, j), "title", ed.lang)
                                                                    or t("ed_untitled")), depth=1))
        elif kind == "exercise":
            box.add_child(_Row(("step", i), lambda i=i: _exercise_summary(ed.step(i)),
                               tag=t("ed_tag_exercise").upper()))
        else:
            box.add_child(_Row(("step", i), lambda kind=kind: str(kind), tag="?"))
    box.add_child(spacer(4))
    row = Flow(gap=8)
    row.add_child(button("+ " + t("ed_add_scene"), ed.add_scene, size=12, height=32))
    row.add_child(button("+ " + t("ed_add_exercise"), ed.add_exercise, size=12, height=32))
    box.add_child(row)


def _exercise_summary(s: dict) -> str:
    tm = s.get("time") or [4, 4]
    return tn("ed_exercise_summary", len(s.get("bars", [])), time=f"{tm[0]}/{tm[1]}")


# ── the inspector (the selected part's fields) ────────────────────────────────────────

def _text_field(label: str, get, set_, lines: int = 1, placeholder: str = "", mono=False):
    out = [field_label(label)]
    box = TextBox(get(), placeholder=placeholder, min_lines=lines, mono=mono,
                  on_change=lambda v: (set_(v), _ED.changed()))
    out.append(box)
    return out


def _seg(segments, index, on_change, height=32):
    return SegmentedControl(segments=segments, selected_index=max(0, index),
                            on_change=on_change, width=1.0, height=px(height))


def _notes_line(names: list[str], live: bool = False) -> Label:
    text = "   ".join(names) if names else t("ed_no_notes")
    lab = Label(text=text, font_size=14 if names else 13, bold=bool(names),
                color=(RED if live else iOSTheme.label) if names else iOSTheme.secondary_label,
                wrap_width=max(60, int(unpx(_ED.page.get("inner_w", 400)))))
    return lab


def _notes_editor(box, label: str, names: list[str], target: str, on_clear, extra=None):
    """A row of notes with Record / Clear, or, while recording, the notes coming in."""
    ed = _ED
    box.add_child(field_label(label))
    recording = ed.rec is not None and ed.rec["target"] == target
    if recording:
        lab = _notes_line(ed.rec_names(), live=True)
        ed.page["rec_label"] = lab
        box.add_child(lab)
        box.add_child(hint(t("ed_recording_hint"), ed.page["inner_w"], color=RED))
        row = Flow()
        row.add_child(button("■ " + t("ed_stop"), ed.stop_record, kind="danger"))
        row.add_child(button(t("ed_undo_note"), ed.rec_undo))
        row.add_child(button(t("ed_cancel"), ed.cancel_record))
        box.add_child(row)
        return
    box.add_child(_notes_line(names))
    row = Flow()
    row.add_child(button("● " + t("ed_record"), lambda: ed.start_record(target), kind="primary",
                         enabled=ed.rec is None))
    if names:
        row.add_child(button(t("ed_clear"), on_clear))
    for b in extra or []:
        row.add_child(b)
    box.add_child(row)


def _step_actions(box, what: str):
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


def _fill_lesson(box):
    ed = _ED
    d, lang, w = ed.draft, ed.lang, ed.page["inner_w"]
    s = d["strings"].setdefault(lang, {})
    box.add_child(heading(t("ed_lesson_details")))

    def set_title(v):
        s["title"] = v
        _sync_bar()
    for el in _text_field(_lf("ed_field_title"),
                          lambda: s.get("title", ""), set_title):
        box.add_child(el)
    for el in _text_field(_lf("ed_field_description"), lambda: s.get("description", ""),
                          lambda v: s.__setitem__("description", v), lines=3,
                          placeholder=t("ed_description_ph")):
        box.add_child(el)
    meta = d["meta"]
    for el in _text_field(t("ed_field_author"), lambda: meta.get("author", ""),
                          lambda v: meta.__setitem__("author", v)):
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
    for el in _text_field(t("ed_field_tags"), lambda: ", ".join(meta.get("tags", [])),
                          lambda v: meta.__setitem__("tags", [x.strip() for x in v.split(",") if x.strip()]),
                          placeholder=t("ed_tags_ph")):
        box.add_child(el)
    box.add_child(hint(t("ed_id_hint", id=ed.id), w))
    if meta.get("based_on"):
        box.add_child(hint(t("ed_based_on", id=meta["based_on"]), w))

    box.add_child(spacer(4))
    box.add_child(heading(t("ed_check")))
    if not ed.problems:
        box.add_child(Label(text="✓ " + t("ed_no_problems"), font_size=13, bold=True, color=GREEN))
    else:
        box.add_child(hint(tn("ed_problems_hint", len(ed.problems)), w))
        for where, code, args in ed.problems[:40]:
            box.add_child(_ProblemRow(where, f"{ed.where_text(where)}:  {t('ed_problem_' + code, **args)}"))


def _lf(key: str) -> str:
    """A field label naming the language being edited: "Title (DE)"."""
    return f"{t(key)} ({_ED.lang.upper()})"


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
                _ED.select(("step", w[1]) if w[0] == "bar" else w)
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


def _fill_scene(box, i: int):
    ed = _ED
    s = ed.step(i)
    box.add_child(heading(t("ed_scene_n", n=i + 1)))
    for el in _text_field(_lf("ed_field_scene_title"), lambda: _loc_get(s, "title", ed.lang),
                          lambda v: _loc_set(s, "title", ed.lang, v)):
        box.add_child(el)
    box.add_child(hint(tn("ed_scene_hint", len(s.get("beats", []))), ed.page["inner_w"]))
    row = Flow()
    row.add_child(button("+ " + t("ed_add_beat"), lambda: ed.add_beat(i), kind="primary"))
    box.add_child(row)
    box.add_child(spacer(6))
    _step_actions(box, "step_actions")


def _fill_exercise(box, i: int):
    ed = _ED
    s = ed.step(i)
    w = ed.page["inner_w"]
    box.add_child(heading(t("ed_exercise_n", n=i + 1)))
    box.add_child(hint(t("ed_exercise_hint"), w))
    _add_preview(box)
    box.add_child(field_label(t("ed_field_time")))
    tm = s.get("time") or [4, 4]
    times = [list(x) for x in _TIMES]
    if tm not in times:
        times.append(list(tm))
    box.add_child(_seg([f"{a}/{b}" for a, b in times], times.index(tm),
                       lambda k: (s.__setitem__("time", list(times[k])), ed.changed())))

    box.add_child(spacer(4))
    box.add_child(heading(t("ed_bars")))
    bars = s.setdefault("bars", [])
    problems = {where[2] for where, _, _ in ed.problems if where[0] == "bar" and where[1] == i}
    for k, bar in enumerate(bars):
        row = Flow(gap=6)
        num = FloatLayout(width=px(26), height=px(38), border_radius=0)
        num.add_child(Label(text=str(k + 1), font_size=13, bold=True, color=iOSTheme.secondary_label,
                            anchor="left", x=0, y=0))
        row.add_child(num)
        field_w = max(px(80), w - px(26) - px(6) * 2 - px(40))

        def set_bar(v, k=k):
            bars[k] = split_words(v)
            ed.changed()
            _sync_rows()
        tb = TextBox(" ".join(bar), placeholder=t("ed_bar_ph"), on_change=set_bar, width=field_w)
        tb.error = k in problems
        ed.page.setdefault("bar_boxes", {})[k] = tb
        row.add_child(tb)

        def drop(k=k):
            del bars[k]
            ed.changed(structure=True)
        row.add_child(button("×", drop, size=16, height=38, min_w=40))
        box.add_child(row)
    if not bars:
        box.add_child(hint(t("ed_no_bars"), w))

    if ed.rec is not None and ed.rec["target"] == "bars":
        _notes_editor(box, t("ed_record_bars_label"), [], "bars", None)
    else:
        row = Flow()
        row.add_child(button("+ " + t("ed_add_bar"),
                             lambda: (bars.append([]), ed.changed(structure=True))))
        row.add_child(button("● " + t("ed_record_bars"), lambda: ed.start_record("bars"), kind="primary"))
        row.add_child(button(t("ed_import_xml"), _import_xml))
        if bars:
            def clear_bars():
                key = "bars"
                if ed.confirm != key:
                    ed.confirm = key
                    rebuild()
                    return
                ed.confirm = None
                bars.clear()
                ed.changed(structure=True)
            row.add_child(button(t("ed_clear_bars_confirm") if ed.confirm == "bars" else t("ed_clear_bars"),
                                 clear_bars, kind="danger" if ed.confirm == "bars" else "plain"))
        box.add_child(row)
        box.add_child(field_label(t("ed_import_hand")))
        box.add_child(_seg([t("ed_hand_right"), t("ed_hand_left")], ed.import_hand,
                           lambda k: setattr(ed, "import_hand", k)))
        box.add_child(hint(t("ed_bars_hint", n=tm[0]), w))
    box.add_child(spacer(6))
    _step_actions(box, "step_actions")


def _fill_beat(box, i: int, j: int):
    ed = _ED
    s = ed.step(i)
    b = ed.beat(i, j)
    w = ed.page["inner_w"]
    lang = ed.lang
    box.add_child(heading(t("ed_beat_n", n=j + 1, total=len(s["beats"]),
                            scene=_loc_get(s, "title", lang) or t("ed_untitled"))))
    _add_preview(box)

    for el in _text_field(_lf("ed_field_beat_title"), lambda: _loc_get(b, "title", lang),
                          lambda v: (_loc_set(b, "title", lang, v), _sync_rows())):
        box.add_child(el)
    for el in _text_field(_lf("ed_field_say"), lambda: _loc_get(b, "say", lang),
                          lambda v: _loc_set(b, "say", lang, v), lines=3,
                          placeholder=t("ed_say_ph")):
        box.add_child(el)

    # notes
    box.add_child(spacer(4))
    box.add_child(heading(t("ed_notes")))
    tempos = list(range(40, 201, 4))
    cur = int(b.get("tempo", 76))
    if cur not in tempos:
        tempos = sorted(set(tempos + [cur]))
    tempo = Stepper(options=tempos, value=cur, fmt_fn=lambda v: f"{v} BPM",
                    on_change=lambda v: (b.__setitem__("tempo", int(v)), ed.changed()),
                    width=px(180), height=px(34))
    _notes_editor(box, t("ed_field_play"), list(b.get("play", [])), "play",
                  lambda: (b.pop("play", None), b.pop("fingers", None), b.pop("velocities", None),
                           b.pop("try", None) if b.get("try") == "play" else None,
                           ed.changed(structure=True)))
    if ed.rec is None:
        box.add_child(field_label(t("ed_field_tempo")))
        box.add_child(left(tempo))
        box.add_child(field_label(t("ed_field_accent")))
        accents = [0, 2, 3, 4]
        acc = int(b.get("accent", 0) or 0)
        box.add_child(_seg([t("ed_none"), "2", "3", "4"], accents.index(acc) if acc in accents else 0,
                           lambda k: (b.__setitem__("accent", accents[k]) if accents[k] else b.pop("accent", None),
                                      ed.changed())))

    box.add_child(field_label(t("ed_field_try")))
    tr = b.get("try")
    mode = 0 if not tr else 1 if tr == "play" else 2

    def set_try(k):
        if k == 0:
            b.pop("try", None)
        elif k == 1:
            b["try"] = "play"
        else:
            b["try"] = list(b.get("play", [])) if not isinstance(b.get("try"), list) else b["try"]
        ed.changed(structure=True)
    box.add_child(_seg([t("ed_try_none"), t("ed_try_same"), t("ed_try_other")], mode, set_try))
    if mode == 2:
        _notes_editor(box, t("ed_field_try_notes"), list(tr), "try",
                      lambda: (b.__setitem__("try", []), ed.changed(structure=True)))
    if mode:
        for el in _text_field(_lf("ed_field_try_say"), lambda: _loc_get(b, "try_say", lang),
                              lambda v: _loc_set(b, "try_say", lang, v), placeholder=t("ed_try_say_ph")):
            box.add_child(el)

    # keyboard
    box.add_child(spacer(4))
    box.add_child(heading(t("ed_keyboard")))
    modes = ["mark", "labels", "right", "left"]
    box.add_child(_seg([t("ed_mode_mark"), t("ed_mode_labels"), t("ed_mode_right"), t("ed_mode_left")],
                       modes.index(ed.picker_mode),
                       lambda k: (setattr(ed, "picker_mode", modes[k]), rebuild())))
    box.add_child(hint(t("ed_picker_rec_hint") if ed.rec else t(f"ed_picker_hint_{ed.picker_mode}"), w))
    _add_picker(box)

    box.add_child(field_label(t("ed_field_labels")))
    labels = b.get("labels")
    lmode = 0 if labels is None else 1 if isinstance(labels, list) else (
        _LABEL_MODES.index(labels) if labels in _LABEL_MODES else 0)

    def set_labels(k):
        m = _LABEL_MODES[k]
        if m is None:
            b.pop("labels", None)
        elif m == "list":
            b["labels"] = labels if isinstance(labels, list) else []
            ed.picker_mode = "labels"
        else:
            b["labels"] = m
        ed.changed(structure=True)
    box.add_child(_seg([t("ed_labels_none"), t("ed_labels_list"), t("ed_labels_c"),
                        t("ed_labels_white"), t("ed_labels_hand")], lmode, set_labels))
    row = Flow(gap=10)
    row.add_child(Switch(value=bool(b.get("numbers")), width=px(51), height=px(31),
                         on_change=lambda v: (b.__setitem__("numbers", True) if v else b.pop("numbers", None),
                                              ed.changed())))
    row.add_child(Label(text=t("ed_numbers"), font_size=13, color=iOSTheme.label, height=px(31)))
    box.add_child(row)
    box.add_child(field_label(t("ed_field_side")))
    sides = [None, "right", "left"]
    box.add_child(_seg([t("ed_side_auto"), t("ed_hand_right"), t("ed_hand_left")],
                       sides.index(b.get("side")) if b.get("side") in sides else 0,
                       lambda k: (b.__setitem__("side", sides[k]) if sides[k] else b.pop("side", None),
                                  ed.changed())))

    # staff
    box.add_child(spacer(4))
    box.add_child(heading(t("ed_staff")))
    st = b.get("staff")
    row = Flow(gap=10)

    def toggle_staff(v):
        if v:
            b["staff"] = {"clef": "treble", "notes": list(b.get("play", []))}
        else:
            b.pop("staff", None)
        ed.changed(structure=True)
    row.add_child(Switch(value=bool(st), on_change=toggle_staff, width=px(51), height=px(31)))
    row.add_child(Label(text=t("ed_show_staff"), font_size=13, color=iOSTheme.label, height=px(31)))
    box.add_child(row)
    if st:
        box.add_child(field_label(t("ed_field_clef")))
        clefs = list(cs.CLEFS)
        box.add_child(_seg([t(f"ed_clef_{c}") for c in clefs],
                           clefs.index(st.get("clef")) if st.get("clef") in clefs else 0,
                           lambda k: (st.__setitem__("clef", clefs[k]), ed.changed())))
        box.add_child(field_label(t("ed_field_key")))
        keys = list(range(-7, 8))
        box.add_child(left(Stepper(options=keys, value=int(st.get("key", 0)), fmt_fn=_key_text,
                                   on_change=lambda v: (st.__setitem__("key", int(v)) if v else st.pop("key", None),
                                                        ed.changed()),
                                   width=px(220), height=px(34))))
        box.add_child(field_label(t("ed_field_staff_time")))
        stimes = [None] + [list(x) for x in _TIMES]
        cur_t = st.get("time")
        if cur_t is not None and cur_t not in stimes:
            stimes.append(cur_t)
        box.add_child(_seg([t("ed_none")] + [f"{x[0]}/{x[1]}" for x in stimes[1:]],
                           stimes.index(cur_t) if cur_t in stimes else 0,
                           lambda k: (st.__setitem__("time", stimes[k]) if stimes[k] else st.pop("time", None),
                                      ed.changed())))
        same = button(t("ed_same_as_play"), lambda: (st.__setitem__("notes", list(b.get("play", []))),
                                                     ed.changed(structure=True)))
        _notes_editor(box, t("ed_field_staff_notes"), list(st.get("notes", [])), "staff",
                      lambda: (st.__setitem__("notes", []), ed.changed(structure=True)), extra=[same])
        box.add_child(field_label(t("ed_field_under")))
        unders = [None, "names", "count"]
        u = st.get("under") or ("names" if st.get("names") else None)
        box.add_child(_seg([t("ed_none"), t("ed_under_names"), t("ed_under_count")],
                           unders.index(u) if u in unders else 0,
                           lambda k: (st.pop("names", None),
                                      st.__setitem__("under", unders[k]) if unders[k] else st.pop("under", None),
                                      ed.changed())))

    box.add_child(spacer(6))
    _step_actions(box, "beat_actions")


def _key_text(v: int) -> str:
    if v == 0:
        return t("ed_key_none")
    return t("ed_key_sharps", n=v) if v > 0 else t("ed_key_flats", n=-v)


# ── preview and keyboard canvases ─────────────────────────────────────────────────────

class _Preview:
    """The selected beat (or the start of an exercise) drawn by the lesson player's own
    scene code. Rebuilt a moment after the last change."""

    def __init__(self):
        self.scene = None
        self.wait = 0.0
        self.error = ""
        self.sel = None

    def _raw(self, ed) -> dict | None:
        if ed.sel[0] == "beat":
            _, i, j = ed.sel
            s = ed.step(i)
            return {"title": s.get("title"), "beats": [copy.deepcopy(ed.beat(i, j))]}
        if ed.sel[0] == "step" and ed.step(ed.sel[1]).get("type") == "exercise":
            s = ed.step(ed.sel[1])
            notes = [n for bar in s.get("bars", []) for n in bar][:12]
            if not notes:
                return None
            midis = [parse_chord(n) for n in notes]
            if any(m is None for m in midis):
                raise ValueError("bad note")
            low = sum(m[0] for m in midis) / len(midis) < 57
            return {"title": "", "beats": [{
                "title": "", "say": "",
                "staff": {"clef": "bass" if low else "treble", "time": s.get("time") or [4, 4],
                          "notes": notes},
                "play": notes, "tempo": 96}]}
        return None

    def stop(self):
        if self.scene is not None:
            try:
                self.scene._stop_sounds()
            except Exception:
                pass

    def _build(self, ed):
        self.stop()
        self.scene, self.error = None, ""
        try:
            raw = self._raw(ed)
            if raw is not None:
                from pianove.pages.theory import Scene
                self.scene = Scene(raw)
        except Exception:
            self.scene, self.error = None, t("ed_preview_error")
        self.sel = ed.sel

    def update(self, dt, rect):
        ed = _ED
        if ed is None:
            return
        if ed.preview_dirty or self.sel != ed.sel:
            self.wait += dt
            if self.wait > 0.3 or self.sel != ed.sel:
                ed.preview_dirty = False
                self.wait = 0.0
                self._build(ed)
                _dirty.mark()
        if self.scene is not None and ed.rec is None:
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
        f = font(13)
        ts = f.render(self.error or t("ed_preview_empty"), True, iOSTheme.secondary_label)
        surface.blit(ts, ts.get_rect(center=rect.center))

    def handle_event(self, event, rect) -> bool:
        if self.scene is not None and _ED and _ED.rec is None and rect.collidepoint(getattr(event, "pos", (-1, -1))):
            try:
                return bool(self.scene.handle_event(event, rect))
            except Exception:
                return False
        return False


_PREVIEW = _Preview()


def _add_preview(box):
    ed = _ED
    h = px(300) if not ed.page["narrow"] else max(px(220), min(px(340), int(ed.page["inner_w"] * 0.45)))
    frame = FloatLayout(width=1.0, height=h, background_color=iOSTheme.background,
                        border_radius=px(12))
    frame.add_child(PygameCanvas(target=_PREVIEW, draw_border=False, width=1.0, height=1.0))
    box.add_child(frame)
    row = Flow()
    row.add_child(button("↺ " + t("ed_play_again"),
                         lambda: _PREVIEW.scene.replay() if _PREVIEW.scene else None))
    row.add_child(Label(text=t("ed_preview_label"), font_size=12, color=iOSTheme.secondary_label,
                        height=px(34)))
    box.add_child(row)


def _add_picker(box):
    ed = _ED
    w = ed.page["inner_w"]
    whites = max(14, min(29, int(w / px(30))))
    ed.picker.octaves = max(2, min(4, whites // 7))
    box.add_child(PygameCanvas(target=ed.picker, draw_border=False, width=1.0, height=px(118)))
    row = Flow()
    row.add_child(button("‹ " + t("ed_lower"), lambda: ed.picker.shift(-1)))
    row.add_child(button(t("ed_higher") + " ›", lambda: ed.picker.shift(1)))
    b = ed.cur_beat()
    if b is not None and ed.rec is None:
        mode = ed.picker_mode
        has = (b.get("mark") if mode == "mark" else isinstance(b.get("labels"), list) and b.get("labels")
               if mode == "labels" else (b.get("hand") or {}).get(mode))
        if has:
            def clear():
                if mode == "mark":
                    b.pop("mark", None)
                elif mode == "labels":
                    b.pop("labels", None)
                else:
                    (b.get("hand") or {}).pop(mode, None)
                    if not b.get("hand"):
                        b.pop("hand", None)
                ed.changed()
            row.add_child(button(t("ed_clear_keys"), clear))
    box.add_child(row)


# ── importing an exercise from MusicXML ───────────────────────────────────────────────

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
            ex = cs.exercise_from_musicxml(path, "left" if ed.import_hand else "right")
        except Exception as e:
            _toast(t("ed_import_failed", error=str(e)[:80]), RED)
            return
        if not ex["bars"]:
            _toast(t("ed_import_empty"), RED)
            return
        s = ed.step(i)
        s["time"], s["bars"] = ex["time"], ex["bars"]
        ed.changed(structure=True)
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


def _sync_rows():
    _dirty.mark()


def _sync_rec():
    ed = _ED
    lab = ed.page.get("rec_label") if ed else None
    if lab is not None:
        names = ed.rec_names()
        lab.text = "   ".join(names) if names else t("ed_no_notes")
        lab.color = RED if names else iOSTheme.secondary_label
        lab._text_surf_cache.clear()
        lab.request_layout()
    _dirty.mark()


def rebuild(scroll_top: bool = False):
    """Refill the outline and the inspector from the draft (after a structural change)."""
    ed = _ED
    if ed is None or "inspector" not in ed.page:
        return
    p = ed.page
    p.pop("rec_label", None)
    p.pop("bar_boxes", None)
    if TextBox._focused is not None:
        TextBox._focused.focus(False)
    _fill_outline(p["outline"])
    box = p["inspector"]
    _clear(box)
    sel = ed.sel
    try:
        if sel[0] == "beat":
            _fill_beat(box, sel[1], sel[2])
        elif sel[0] == "step":
            if ed.step(sel[1]).get("type") == "exercise":
                _fill_exercise(box, sel[1])
            elif ed.step(sel[1]).get("type") == "scene":
                _fill_scene(box, sel[1])
            else:
                box.add_child(hint(t("ed_unknown_step"), p["inner_w"]))
                _step_actions(box, "step_actions")
        else:
            _fill_lesson(box)
    except (IndexError, KeyError):
        ed.sel = ("lesson",)
        _clear(box)
        _fill_lesson(box)
    box.add_child(spacer(24))
    if scroll_top:
        box.scroll_target = box.scroll_offset = 0.0
    narrow = p["narrow"]
    if narrow:
        p["outline"].visible = ed.show_outline
        box.visible = not ed.show_outline
        p["where"].text = _where_short(ed)
        p["where"]._text_surf_cache.clear()
    p["root"].layout()
    p["root"].request_layout()
    _sync_bar()
    _dirty.mark()


def _where_short(ed) -> str:
    sel = ed.sel
    if sel[0] == "lesson":
        return t("ed_lesson_details")
    if sel[0] == "step":
        return t("ed_where_step", n=sel[1] + 1)
    return t("ed_where_beat", n=sel[1] + 1, m=sel[2] + 1)


def _back():
    ed = _ED
    _PREVIEW.stop()
    if ed is not None:
        if ed.rec:
            ed.cancel_record()
        if ed.dirty:
            ed.save()
    _leave()
    ctx.router.navigate("home", "left")


def _leave():
    global _ED
    _ED = None
    if TextBox._focused is not None:
        TextBox._focused.focus(False)


def _test():
    ed = _ED
    if ed is None:
        return
    if ed.rec:
        ed.stop_record()
    if not ed.save():
        return
    _PREVIEW.stop()
    sel = ed.sel
    start = sel[1] if sel[0] in ("step", "beat") else 0
    ctx.current_lesson_id = ed.id
    ctx.current_course_id = None
    ctx.current_song_id = None
    ctx.practice_mode = False
    ctx.lesson_step_idx = start
    ctx.lesson_current_idx = 0
    ctx.lesson_section_idx = 0
    ctx.lesson_phase = "practice"
    ctx.lesson_completed = False
    ctx.lesson_test_return = "lesson_editor"
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
    previewing = _PREVIEW.scene is not None and ed.sel[0] in ("beat", "step")
    if ed.rec is not None or not previewing:
        try:
            midi_panel.update(dt, pygame.Rect(0, 0, 1, 1))
        except Exception:
            pass
        ons = midi_panel.take_note_ons()
        if ed.rec is not None and ons:
            now = time.monotonic()
            ed.rec["events"].extend((now, m) for m in ons)
            _sync_rec()
    live = set(midi_panel.active_notes)
    if live != ed.picker.live:
        ed.picker.live = live
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
    ed.rec = None
    ed.preview_dirty = True
    _PREVIEW.sel = None

    W = ctx.ui.width if ctx.ui else 1024
    H = ctx.ui.height if ctx.ui else 768
    narrow = is_narrow(W, H)
    pad = px(16)
    bar_h = px(56)
    outline_w = px(260)

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
    right = Flow(gap=8, align="right", anchor="right", x=-px(10), y=0,
                 width=px(420) if not narrow else px(220), height=px(36))
    if not narrow:
        lang_seg = SegmentedControl(segments=[x.upper() for x in cs.LOCALES],
                                    selected_index=list(cs.LOCALES).index(ed.lang),
                                    on_change=lambda k: _set_lang(cs.LOCALES[k]),
                                    width=px(96), height=px(32))
        right.add_child(lang_seg)
    right.add_child(button(("▶ " + t("ed_test")) if not narrow else "▶", _test, kind="good", height=36))
    save_w = max(text_w(t("ed_save"), 13), text_w("✓ " + t("ed_saved"), 13)) + px(26)
    save = button(t("ed_save"), lambda: (ed.save() and _toast(t("ed_saved_toast"), GREEN)),
                  kind="primary", height=36, min_w=unpx(save_w))
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
        nrow.add_child(SegmentedControl(segments=[x.upper() for x in cs.LOCALES],
                                        selected_index=list(cs.LOCALES).index(ed.lang),
                                        on_change=lambda k: _set_lang(cs.LOCALES[k]),
                                        width=px(90), height=px(32)))
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
        max_w = px(820)
        iw = min(insp_w, max_w)
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


def _set_lang(lang: str):
    ed = _ED
    if ed and lang != ed.lang:
        ed.lang = lang
        rebuild()


def open_lesson(lesson_id: str):
    """Open the editor on a lesson (from the Creator tab)."""
    global _ED
    _ED = None
    ctx.editor_lesson_id = lesson_id
    ctx.router.navigate("lesson_editor", "right")
