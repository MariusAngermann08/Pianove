"""The Creator tab (shown when Creator Mode is on in Settings): make a lesson or a course,
open the ones you made in their editors, duplicate a built-in lesson to change it, and
share lessons and courses as .pianove-pkg files."""
import time

import pianove.context as ctx
from pylay import FloatLayout, Label, FilePicker, iOSTheme
from pylay.core import _dirty
from pianove.i18n import t
from pianove import creator_store as cs
from pianove.creator_ui import (px, tn, button, Flow, DragScroll, TextBox, ItemRow,
                                heading, hint, spacer, Ticker, Toast, export_dir, RED, GREEN)

_HEADER_H = 64
_page: dict = {}
_confirm: dict = {"key": None, "t": 0.0}
_drafts = {"lesson": "", "course": ""}      # what was typed into the "new" fields


def _author() -> str:
    from pianove.state import name_state
    return str(name_state.value or "").strip()


def _toast(text: str, color=None):
    if "toast" in _page:
        _page["toast"].show(text, seconds=6.0, color=color)


# ── actions ───────────────────────────────────────────────────────────────────────────

def _new_lesson():
    title = _drafts["lesson"].strip() or t("cr_untitled_lesson")
    lid = cs.new_lesson(title, author=_author())
    _drafts["lesson"] = ""
    from pianove.pages.lesson_editor import open_lesson
    open_lesson(lid)


def _new_course():
    title = _drafts["course"].strip() or t("cr_untitled_course")
    cid = cs.new_course(title, author=_author())
    _drafts["course"] = ""
    from pianove.pages.course_editor import open_course
    open_course(cid)


def _edit(lid: str):
    from pianove.pages.lesson_editor import open_lesson
    open_lesson(lid)


def _edit_course(cid: str):
    from pianove.pages.course_editor import open_course
    open_course(cid)


def _duplicate(lid: str):
    try:
        new_id = cs.duplicate_lesson(lid, author=_author())
    except (KeyError, OSError) as e:
        _toast(t("cr_failed", error=str(e)[:80]), RED)
        return
    _toast(t("cr_duplicated", id=new_id), GREEN)
    _refresh()


def _export(kind: str, item_id: str):
    try:
        path = cs.export_package(kind, item_id, export_dir())
    except Exception as e:
        _toast(t("cr_export_failed", error=str(e)[:80]), RED)
        return
    _toast(t("cr_exported", path=str(path)), GREEN)


def _delete(kind: str, item_id: str):
    key = f"{kind}:{item_id}"
    if _confirm["key"] != key or time.monotonic() - _confirm["t"] > 4.0:
        _confirm.update(key=key, t=time.monotonic())
        _refresh()
        return
    _confirm["key"] = None
    ok = cs.delete_lesson(item_id) if kind == "lesson" else cs.delete_course(item_id)
    if ok:
        _toast(t("cr_deleted"), GREEN)
    _refresh()


def _import():
    picker = _page.get("picker")
    if picker is None:
        return

    def got(path):
        if not path:
            return
        try:
            res = cs.import_package(path)
        except cs.PackageError as e:
            _toast(t("cr_import_failed", reason=t(f"cr_pkg_{e.code}")), RED)
            return
        except Exception as e:
            _toast(t("cr_import_failed", reason=str(e)[:80]), RED)
            return
        msg = t("cr_imported", lessons=len(res["lessons"]), courses=len(res["courses"]))
        if res["replaced_builtin"]:
            msg += "  " + t("cr_imported_replaces", ids=", ".join(res["replaced_builtin"]))
        _toast(msg, GREEN)
        _refresh()
    picker.pick(got)


# ── the list ──────────────────────────────────────────────────────────────────────────

def _delete_button(kind: str, item_id: str):
    confirming = _confirm["key"] == f"{kind}:{item_id}"
    return button(t("ed_delete_confirm") if confirming else t("ed_delete"),
                  lambda: _delete(kind, item_id), kind="danger" if confirming else "plain")


def _new_row(which: str, placeholder: str, label: str, on_create, w: int):
    row = Flow(gap=8)
    btn = button(label, on_create, kind="primary", height=40)
    field_w = int(btn.width_spec) + px(8)
    field_w = w - field_w if w - field_w >= px(220) else w
    row.add_child(TextBox(_drafts[which], placeholder=placeholder, width=field_w,
                          on_change=lambda v: _drafts.__setitem__(which, v)))
    row.add_child(btn)
    return row


def _fill(box):
    w = _page["inner_w"]
    box.add_child(heading(t("cr_new_lesson")))
    box.add_child(_new_row("lesson", t("cr_lesson_title_ph"), t("cr_create"), _new_lesson, w))
    row = Flow()
    row.add_child(button(t("cr_import"), _import))
    box.add_child(row)
    box.add_child(hint(t("cr_import_hint"), w))

    own = cs.list_own_lessons()
    box.add_child(spacer(6))
    box.add_child(heading(t("cr_my_lessons", n=len(own))))
    if not own:
        box.add_child(hint(t("cr_no_lessons"), w))
    for info in own:
        lid = info["id"]
        sub = tn("cr_lesson_sub", info.get("n_steps", 0), id=lid)
        if info.get("replaces_builtin"):
            sub = t("cr_replaces_builtin", id=lid)
        box.add_child(ItemRow(info["title"], sub, [
            button(t("cr_edit"), lambda i=lid: _edit(i), kind="primary"),
            button(t("cr_duplicate"), lambda i=lid: _duplicate(i)),
            button(t("cr_export"), lambda i=lid: _export("lesson", i)),
            _delete_button("lesson", lid),
        ], w, warn=bool(info.get("replaces_builtin"))))

    courses = cs.list_own_courses()
    box.add_child(spacer(6))
    box.add_child(heading(t("cr_my_courses", n=len(courses))))
    box.add_child(_new_row("course", t("cr_course_title_ph"), t("cr_create"), _new_course, w))
    for c in courses:
        cid = c["id"]
        box.add_child(ItemRow(c["title"], tn("cr_course_sub", len(c["lessons"])), [
            button(t("cr_edit"), lambda i=cid: _edit_course(i), kind="primary"),
            button(t("cr_export"), lambda i=cid: _export("course", i)),
            _delete_button("course", cid),
        ], w))

    box.add_child(spacer(6))
    box.add_child(heading(t("cr_builtin_lessons")))
    box.add_child(hint(t("cr_builtin_hint"), w))
    for info in cs.list_builtin_lessons():
        box.add_child(ItemRow(info["title"], info["id"],
                              [button(t("cr_duplicate"), lambda i=info["id"]: _duplicate(i))], w))
    box.add_child(spacer(24))


def _refresh():
    box = _page.get("box")
    if box is None:
        return
    if TextBox._focused is not None:
        TextBox._focused.focus(False)
    keep = box.scroll_target
    for c in list(box.children):
        c.parent = None
    box.children.clear()
    _fill(box)
    _page["root"].layout()
    box.scroll_target = min(keep, box.scroll_max)
    _page["root"].request_layout()
    _dirty.mark()


def _tick(dt):
    if "toast" in _page:
        _page["toast"].tick()
    if _confirm["key"] and time.monotonic() - _confirm["t"] > 4.0:
        _confirm["key"] = None
        _refresh()


def build():
    _page.clear()
    win_w = ctx.ui.width if ctx.ui else 1024
    win_h = ctx.ui.height if ctx.ui else 768
    router = ctx.inner_router
    content_w = router.rect.width if router is not None and router.rect.width > 50 else win_w - 200
    header_h = px(_HEADER_H)
    pad = px(16)

    root = FloatLayout(width=1.0, height=1.0, background_color=iOSTheme.background)
    _page["root"] = root
    root.add_child(Ticker(_tick))
    picker = FilePicker(title=t("cr_import_title"),
                        filters=["Pianove package | *.pianove-pkg *.zip", "All files | *"])
    root.add_child(picker)
    _page["picker"] = picker

    header = FloatLayout(anchor="top_left", x=0, y=0, width=1.0, height=header_h,
                         background_color=iOSTheme.background)
    header.add_child(Label(text=t("creator_title"), font_size=20, bold=True, color=iOSTheme.label,
                           anchor="left", x=px(20), y=-px(8)))
    toast = Label(text="", font_size=12, color=iOSTheme.secondary_label, anchor="left", x=px(20), y=px(16))
    header.add_child(toast)
    _page["toast"] = Toast(toast)
    root.add_child(header)

    iw = min(content_w, px(820))
    box = DragScroll(spacing=px(8), padding=pad, anchor="top_left", x=(content_w - iw) // 2, y=header_h,
                     width=iw, height=max(px(200), win_h - header_h), background_color=iOSTheme.background)
    _page["box"] = box
    _page["inner_w"] = iw - 2 * pad
    root.add_child(box)
    _fill(box)
    return root
