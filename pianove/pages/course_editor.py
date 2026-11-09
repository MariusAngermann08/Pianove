"""The course editor (Creator Mode): a course's title and description, and which lessons
it holds in which order. Any lesson can be added, built-in or own; a course refers to
its lessons by id."""
from __future__ import annotations

from pylay import FloatLayout, Label, SegmentedControl, iOSTheme
from pylay.core import _dirty

import pianove.context as ctx
from pianove.i18n import t, language_state
from pianove import creator_store as cs
from pianove import lesson_loader
from pianove.creator_ui import (px, unpx, is_narrow, tn, font, text_w, button, Flow, DragScroll, TextBox, ItemRow,
                                heading, field_label, hint, spacer, Ticker, Toast, export_dir,
                                RED, GREEN, WHITE)
from pylay import ColorPalette

_CE: "_CourseEditor | None" = None


class _CourseEditor:
    def __init__(self, course_id: str):
        self.id = course_id
        self.draft = cs.load_course(course_id)
        self.lang = language_state.value if language_state.value in cs.LOCALES else "en"
        self.dirty = False
        self.page: dict = {}

    @property
    def lessons(self) -> list:
        return self.draft["meta"].setdefault("lessons", [])

    def title(self) -> str:
        lang = language_state.value if language_state.value in cs.LOCALES else "en"
        s = self.draft["strings"]
        return s.get(lang, {}).get("title") or s.get("en", {}).get("title") or self.id

    def changed(self, structure: bool = False):
        self.dirty = True
        _sync_bar()
        if structure:
            _rebuild()

    def save(self) -> bool:
        try:
            cs.save_course(self.draft)
        except OSError as e:
            _toast(t("ed_save_failed", error=str(e)), RED)
            return False
        self.dirty = False
        _sync_bar()
        return True

    def move(self, k: int, delta: int):
        j = k + delta
        if 0 <= j < len(self.lessons):
            self.lessons[k], self.lessons[j] = self.lessons[j], self.lessons[k]
            self.changed(structure=True)

    def remove(self, k: int):
        del self.lessons[k]
        self.changed(structure=True)

    def add(self, lesson_id: str):
        self.lessons.append(lesson_id)
        self.changed(structure=True)


def _clear(container):
    for c in list(container.children):
        c.parent = None
    container.children.clear()


def _fill(box):
    ce = _CE
    w = ce.page["inner_w"]
    lang = ce.lang
    s = ce.draft["strings"].setdefault(lang, {})
    meta = ce.draft["meta"]
    box.add_child(heading(t("ce_course")))

    def set_title(v):
        s["title"] = v
        ce.changed()
    box.add_child(field_label(f"{t('ed_field_title')} ({lang.upper()})"))
    box.add_child(TextBox(s.get("title", ""), on_change=set_title))
    box.add_child(field_label(f"{t('ed_field_description')} ({lang.upper()})"))
    box.add_child(TextBox(s.get("description", ""), min_lines=3, placeholder=t("ce_description_ph"),
                          on_change=lambda v: (s.__setitem__("description", v), ce.changed())))
    box.add_child(field_label(t("ed_field_author")))
    box.add_child(TextBox(meta.get("author", ""),
                          on_change=lambda v: (meta.__setitem__("author", v), ce.changed())))
    box.add_child(field_label(t("ed_field_difficulty")))
    diffs = list(cs.DIFFICULTIES)
    box.add_child(SegmentedControl(segments=[t(f"ed_diff_{x}") for x in diffs],
                                   selected_index=diffs.index(meta.get("difficulty"))
                                   if meta.get("difficulty") in diffs else 0,
                                   on_change=lambda k: (meta.__setitem__("difficulty", diffs[k]), ce.changed()),
                                   width=1.0, height=px(32)))
    box.add_child(hint(t("ce_id_hint", id=ce.id), w))

    all_lessons = {i["id"]: i for i in lesson_loader.list_lessons()}
    box.add_child(spacer(6))
    box.add_child(heading(tn("ce_lessons_in", len(ce.lessons))))
    if not ce.lessons:
        box.add_child(hint(t("ce_no_lessons"), w))
    for k, lid in enumerate(ce.lessons):
        info = all_lessons.get(lid)
        title = f"{k + 1}. " + (info["title"] if info else lid)
        sub = (t("ce_missing_lesson", id=lid) if info is None
               else t("cr_own") if cs.is_own_lesson(lid) else t("cr_builtin"))
        btns = [button("↑", lambda k=k: ce.move(k, -1), min_w=36),
                button("↓", lambda k=k: ce.move(k, 1), min_w=36),
                button(t("ce_remove"), lambda k=k: ce.remove(k))]
        box.add_child(ItemRow(title, sub, btns, w, warn=info is None))

    box.add_child(spacer(6))
    box.add_child(heading(t("ce_add_lessons")))
    rest = [i for i in all_lessons.values() if i["id"] not in ce.lessons]
    rest.sort(key=lambda i: (not cs.is_own_lesson(i["id"]), i["title"].lower()))
    if not rest:
        box.add_child(hint(t("ce_all_added"), w))
    for info in rest:
        sub = t("cr_own") if cs.is_own_lesson(info["id"]) else t("cr_builtin")
        box.add_child(ItemRow(info["title"], sub,
                                 [button("+ " + t("ce_add"), lambda i=info["id"]: ce.add(i), kind="primary")], w))
    if ce.page.get("narrow"):            # no room for Export in the top bar
        box.add_child(spacer(6))
        row = Flow()
        row.add_child(button(t("cr_export"), _export))
        box.add_child(row)
    box.add_child(spacer(24))


def _sync_bar():
    ce = _CE
    if ce is None:
        return
    p = ce.page
    if "title" in p:
        text, f, room = ce.title(), font(15, bold=True), p.get("title_max", 10_000)
        while len(text) > 1 and f.size(text)[0] > room:
            text = text[:-2] + "…"
        p["title"].text = text
        p["title"]._text_surf_cache.clear()
        p["title"].request_layout()
    save = p.get("save")
    if save is not None:
        save.text = t("ed_save") if ce.dirty else "✓ " + t("ed_saved")
        save.background_color = ColorPalette.BLUE if ce.dirty else iOSTheme.fill
        save.text_color = WHITE if ce.dirty else iOSTheme.label
        save._cache_key = None
    _dirty.mark()


def _toast(text, color=None):
    if _CE and "toast" in _CE.page:
        _CE.page["toast"].show(text, color=color)


def _rebuild():
    ce = _CE
    if ce is None or "box" not in ce.page:
        return
    if TextBox._focused is not None:
        TextBox._focused.focus(False)
    box = ce.page["box"]
    _clear(box)
    _fill(box)
    ce.page["root"].layout()
    ce.page["root"].request_layout()
    _sync_bar()


def _back():
    global _CE
    if _CE is not None and _CE.dirty:
        _CE.save()
    _CE = None
    if TextBox._focused is not None:
        TextBox._focused.focus(False)
    from pianove.creator_ui import restore_scale
    restore_scale()
    ctx.router.navigate("home", "left")


def _export():
    ce = _CE
    if ce is None or not ce.save():
        return
    try:
        path = cs.export_package("course", ce.id, export_dir())
    except Exception as e:
        _toast(t("cr_export_failed", error=str(e)[:80]), RED)
        return
    _toast(t("cr_exported", path=str(path)), GREEN)


def _set_lang(lang):
    if _CE and lang != _CE.lang:
        _CE.lang = lang
        _rebuild()


def build():
    global _CE
    cid = getattr(ctx, "editor_course_id", None)
    if _CE is None or _CE.id != cid:
        try:
            _CE = _CourseEditor(cid)
        except KeyError:
            _CE = None
            ctx.router.navigate("home", "left")
            return FloatLayout(width=1.0, height=1.0, background_color=iOSTheme.background)
    ce = _CE
    ce.page = {}
    from pianove.creator_ui import apply_page_scale
    apply_page_scale()                       # bigger on a phone or tablet
    W = ctx.ui.width if ctx.ui else 1024
    H = ctx.ui.height if ctx.ui else 768
    narrow = is_narrow(W, H)
    ce.page["narrow"] = narrow
    bar_h, pad, toast_h = px(56), px(16), px(26)

    root = FloatLayout(width=1.0, height=1.0, background_color=iOSTheme.background, border_radius=0)
    ce.page["root"] = root
    root.add_child(Ticker(lambda dt: ce.page["toast"].tick() if "toast" in ce.page else None))

    bar = FloatLayout(anchor="top_left", x=0, y=0, width=1.0, height=bar_h,
                      background_color=iOSTheme.secondary_background, border_radius=0)
    back = button("‹ " + t("back"), _back, height=36)
    back.anchor, back.x_spec = "left", px(10)
    bar.add_child(back)
    right = Flow(gap=8, align="right", anchor="right", x=-px(10), y=0, width=px(420), height=px(36))
    right.add_child(SegmentedControl(segments=[x.upper() for x in cs.LOCALES],
                                     selected_index=list(cs.LOCALES).index(ce.lang),
                                     on_change=lambda k: _set_lang(cs.LOCALES[k]),
                                     width=px(90), height=px(32)))
    if not narrow:
        right.add_child(button(t("cr_export"), _export, height=36))
    save_w = max(text_w(t("ed_save"), 13), text_w("✓ " + t("ed_saved"), 13)) + px(26)
    save = button(t("ed_save"), lambda: ce.save() and _toast(t("ed_saved_toast"), GREEN),
                  kind="primary", height=36, min_w=unpx(save_w))
    right.add_child(save)
    ce.page["save"] = save
    bar.add_child(right)
    title_x = int(back.width_spec) + px(22)
    used = sum(int(c.width_spec) for c in right.children) + px(8) * (len(right.children) - 1)
    ce.page["title_max"] = W - title_x - used - px(30)
    title = Label(text="", font_size=15, bold=True, color=iOSTheme.label, anchor="left", x=title_x, y=0)
    bar.add_child(title)
    ce.page["title"] = title
    root.add_child(bar)

    iw = min(W, px(760))
    box = DragScroll(spacing=px(8), padding=pad, anchor="top_left", x=(W - iw) // 2, y=bar_h + 1,
                     width=iw, height=H - bar_h - 1 - toast_h, background_color=iOSTheme.background,
                     border_radius=0)
    ce.page["box"] = box
    ce.page["inner_w"] = iw - 2 * pad
    root.add_child(box)
    tbar = FloatLayout(anchor="bottom_left", x=0, y=0, width=1.0, height=toast_h,
                       background_color=iOSTheme.background, border_radius=0)
    tl = Label(text="", font_size=12, color=iOSTheme.secondary_label, anchor="left", x=pad, y=0)
    tbar.add_child(tl)
    root.add_child(tbar)
    ce.page["toast"] = Toast(tl)
    _rebuild()
    return root


def open_course(course_id: str):
    global _CE
    _CE = None
    ctx.editor_course_id = course_id
    ctx.router.navigate("course_editor", "right")
