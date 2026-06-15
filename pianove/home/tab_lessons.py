import pygame
import pianove.context as ctx
from pianove.lesson_loader import list_courses, standalone_lessons, list_lessons
from pianove.progress import is_complete
from pylay import (
    FloatLayout, VStack, Card, Label, Button,
    ProgressBar, Badge, Divider, ColorPalette, iOSTheme,
)
from pylay.widgets.icon import Icon
from pianove.i18n import t
from pianove.components import ORANGE, GREEN, RED, section_header

# ── Persistent selected course ─────────────────────────────────────────────────
_active_course: dict | None = None

_COURSE_ICONS = {
    "beginner_path":   "school",
    "melody_explorer": "piano",
}
_DIFF_COLORS = {
    "beginner":     GREEN,
    "intermediate": ORANGE,
    "advanced":     RED,
}
_HEADER_H = 56


def _open_lesson(lesson_id: str, course_id: str | None = None, course_index: int = 0):
    ctx.current_lesson_id    = lesson_id
    ctx.current_course_id    = course_id
    ctx.current_course_index = course_index
    ctx.router.navigate("lesson", "right")


def _open_course(course: dict):
    global _active_course
    _active_course = course
    ctx.inner_router.navigate("course_detail")


# ── Course card (used on the courses list page) ────────────────────────────────

def _course_card(course: dict) -> Card:
    lessons    = course["lessons"]
    n_total    = len(lessons)
    n_done     = sum(1 for lid in lessons if is_complete(lid))
    progress   = n_done / n_total if n_total else 0.0
    diff       = course["meta"].get("difficulty", "beginner")
    diff_color = _DIFF_COLORS.get(diff, ColorPalette.BLUE)
    icon_name  = _COURSE_ICONS.get(course["id"], "library_music")
    all_done   = n_done == n_total

    card = Card(width=1.0, height=160, spacing=8, padding=16)

    # ── Header: icon + title + difficulty badge ───────────────────────────────
    header = FloatLayout(width=1.0, height=28)
    header.add_child(Icon(
        icon_name, size=24,
        color=ColorPalette.BLUE if not all_done else GREEN,
        anchor="left", x=0, y=0,
    ))
    header.add_child(Label(
        text=course["title"],
        font_size=15, bold=True, color=iOSTheme.label,
        anchor="left", x=32, y=0,
    ))
    header.add_child(Badge(
        text=t(f"diff_{diff}"),
        color=diff_color,
        height=22, font_size=11,
        anchor="right", x=0, y=0,
    ))
    card.add_child(header)

    # ── Description ───────────────────────────────────────────────────────────
    card.add_child(Label(
        text=course["description"],
        font_size=12, color=iOSTheme.secondary_label,
        width=1.0, height=18,
    ))

    # ── Progress ──────────────────────────────────────────────────────────────
    prog_row = FloatLayout(width=1.0, height=22)
    prog_row.add_child(ProgressBar(
        progress=progress,
        width=0.68, height=6,
        active_color=GREEN if all_done else ColorPalette.BLUE,
        anchor="left", x=0, y=0,
    ))
    prog_row.add_child(Label(
        text=t("home_n_of_done", done=n_done, total=n_total),
        font_size=11, color=iOSTheme.secondary_label,
        anchor="right", x=0, y=0,
    ))
    card.add_child(prog_row)

    # ── Open button ───────────────────────────────────────────────────────────
    footer = FloatLayout(width=1.0, height=36)
    btn_text  = t("continue") if 0 < n_done < n_total else (
        t("lesson_start") if n_done == 0 else t("lesson_replay")
    )
    footer.add_child(Button(
        text=btn_text,
        on_click=lambda c=course: _open_course(c),
        anchor="right", x=0, y=0,
        width=124, height=34, font_size=13,
        background_color=GREEN if all_done else ColorPalette.BLUE,
        text_color=pygame.Color(255, 255, 255),
        border_radius=10,
    ))
    card.add_child(footer)

    return card


# ── Lesson row (used on the course detail page) ────────────────────────────────

def _lesson_row(index: int, lesson_id: str, course_id: str,
                done: bool, is_next: bool, all_lessons: dict) -> FloatLayout:
    info  = all_lessons.get(lesson_id)
    title = info["title"] if info else lesson_id

    if done:
        status_icon  = "check_circle"
        icon_color   = GREEN
        label_color  = iOSTheme.secondary_label
        btn_text     = t("lesson_replay")
        btn_bg       = iOSTheme.fill
        btn_fg       = iOSTheme.secondary_label
        show_btn     = True
    elif is_next:
        status_icon  = "play_circle"
        icon_color   = ColorPalette.BLUE
        label_color  = iOSTheme.label
        btn_text     = t("lesson_start")
        btn_bg       = ColorPalette.BLUE
        btn_fg       = pygame.Color(255, 255, 255)
        show_btn     = True
    else:
        status_icon  = "radio_button_unchecked"
        icon_color   = iOSTheme.fill_tertiary
        label_color  = iOSTheme.secondary_label
        show_btn     = False

    row = FloatLayout(width=1.0, height=52)

    row.add_child(Icon(
        status_icon, size=20, color=icon_color,
        anchor="left", x=0, y=0,
    ))
    row.add_child(Label(
        text=f"{index + 1}.  {title}",
        font_size=14, bold=is_next,
        color=label_color,
        anchor="left", x=28, y=0,
    ))

    if show_btn:
        ci = index
        row.add_child(Button(
            text=btn_text,
            on_click=lambda _id=lesson_id, _ci=ci: _open_lesson(_id, course_id, _ci),
            anchor="right", x=0, y=0,
            width=80, height=32, font_size=12,
            background_color=btn_bg,
            text_color=btn_fg,
            border_radius=8,
        ))

    return row


# ── Pages ──────────────────────────────────────────────────────────────────────

def build():
    """Courses list — the main lessons tab view."""
    courses    = list_courses()
    standalone = standalone_lessons()
    all_lsn    = {l["id"]: l for l in list_lessons()}

    root   = FloatLayout(width=1.0, height=1.0, background_color=iOSTheme.background)
    scroll = VStack(spacing=14, padding=16, width=1.0, height=1.0)
    root.add_child(scroll)

    if courses:
        from pianove.ui_utils import ui_dims
        U = ui_dims()
        scroll.add_child(section_header(t("lessons_courses"), U))
        for course in courses:
            scroll.add_child(_course_card(course))

    if standalone:
        from pianove.ui_utils import ui_dims
        U = ui_dims()
        scroll.add_child(section_header(t("lessons_standalone"), U))
        for lesson in standalone:
            _open = lambda lid=lesson["id"]: _open_lesson(lid)
            done  = is_complete(lesson["id"])
            card  = Card(width=1.0, height=80, spacing=6, padding=14)
            hdr   = FloatLayout(width=1.0, height=28)
            hdr.add_child(Icon(
                "music_note", size=22, color=ColorPalette.BLUE,
                anchor="left", x=0, y=0,
            ))
            hdr.add_child(Label(
                text=lesson["title"], font_size=14, bold=True,
                color=iOSTheme.label, anchor="left", x=30, y=0,
            ))
            if done:
                hdr.add_child(Icon(
                    "check_circle", size=18, color=GREEN,
                    anchor="right", x=0, y=0,
                ))
            card.add_child(hdr)
            foot = FloatLayout(width=1.0, height=30)
            foot.add_child(Button(
                text=t("lesson_replay") if done else t("lesson_start"),
                on_click=_open,
                anchor="right", x=0, y=0,
                width=80, height=28, font_size=12,
                background_color=iOSTheme.fill if done else ColorPalette.BLUE,
                text_color=iOSTheme.secondary_label if done else pygame.Color(255, 255, 255),
                border_radius=8,
            ))
            card.add_child(foot)
            scroll.add_child(card)

    return root


def build_detail():
    """Lesson list for the currently selected course."""
    course = _active_course
    if course is None:
        return build()

    all_lessons = {l["id"]: l for l in list_lessons()}
    lesson_ids  = course["lessons"]
    first_inc   = next((i for i, lid in enumerate(lesson_ids) if not is_complete(lid)), None)
    course_id   = course["id"]
    scroll_h    = max(200, ctx.ui.height - _HEADER_H) if ctx.ui else 600

    root = FloatLayout(width=1.0, height=1.0, background_color=iOSTheme.background)

    # ── Header ────────────────────────────────────────────────────────────────
    hdr = FloatLayout(
        anchor="top_left", x=0, y=0,
        width=1.0, height=_HEADER_H,
        background_color=iOSTheme.background,
    )
    hdr.add_child(Button(
        icon_fn=Icon.as_icon_fn("arrow_back", base_size=20),
        on_click=lambda: ctx.inner_router.navigate("lessons"),
        anchor="left", x=12, y=0,
        width=40, height=40,
        background_color=iOSTheme.fill,
        text_color=iOSTheme.label,
        border_radius=20,
    ))
    hdr.add_child(Label(
        text=course["title"],
        font_size=17, bold=True, color=iOSTheme.label,
        anchor="center", x=0, y=0,
    ))
    root.add_child(hdr)

    # ── Scrollable lesson list ─────────────────────────────────────────────────
    scroll = VStack(
        spacing=0, padding=16,
        anchor="top_left", x=0, y=_HEADER_H,
        width=1.0, height=scroll_h,
        background_color=iOSTheme.background,
    )

    # Course description
    scroll.add_child(Label(
        text=course["description"],
        font_size=13, color=iOSTheme.secondary_label,
        width=1.0, height=36,
    ))
    scroll.add_child(Divider(width=1.0))

    for i, lid in enumerate(lesson_ids):
        done    = is_complete(lid)
        is_next = (i == first_inc)
        scroll.add_child(_lesson_row(i, lid, course_id, done, is_next, all_lessons))
        if i < len(lesson_ids) - 1:
            scroll.add_child(Divider(width=1.0))

    root.add_child(scroll)
    return root
