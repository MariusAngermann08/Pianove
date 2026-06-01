import pygame
import pianove.context as ctx
from pianove.lesson_loader import list_courses, standalone_lessons, list_lessons
from pianove.progress import is_complete
from pylay import FloatLayout, VStack, Label, Button, EmojiIcon, ColorPalette, iOSTheme
from pianove.i18n import t
from pianove.ui_utils import ui_dims


def _open_lesson(lesson_id: str, course_id: str | None = None, course_index: int = 0):
    ctx.current_lesson_id    = lesson_id
    ctx.current_course_id    = course_id
    ctx.current_course_index = course_index
    ctx.router.navigate("lesson", "right")


def _course_card(course: dict, all_lessons: dict) -> VStack:
    card = VStack(
        spacing=8, padding=16, width=1.0,
        background_color=iOSTheme.secondary_background,
        border_radius=14,
    )

    header = FloatLayout(width=1.0, height=32)
    header.add_child(EmojiIcon("🎓", size=26, color=ColorPalette.BLUE,
                               anchor="left", x=0, y=0))
    header.add_child(Label(
        text=course["title"],
        font_size=15, bold=True,
        color=iOSTheme.label,
        anchor="left", x=34, y=0,
    ))
    n = len(course["lessons"])
    header.add_child(Label(
        text=t("lesson_count", n=n),
        font_size=12,
        color=iOSTheme.secondary_label,
        anchor="right", x=0, y=0,
    ))
    card.add_child(header)

    card.add_child(Label(
        text=course["description"],
        font_size=13,
        color=iOSTheme.secondary_label,
        width=1.0, height=36,
    ))

    for i, lesson_id in enumerate(course["lessons"]):
        info  = all_lessons.get(lesson_id)
        title = info["title"] if info else lesson_id
        done  = is_complete(lesson_id)

        row = FloatLayout(width=1.0, height=38)

        # Checkmark for completed lessons
        if done:
            row.add_child(Label(
                text="✓",
                font_size=14, bold=True,
                color=pygame.Color(52, 199, 89),
                anchor="left", x=4, y=0,
            ))
        row.add_child(Label(
            text=title,
            font_size=14,
            color=iOSTheme.secondary_label if done else iOSTheme.label,
            anchor="left", x=22, y=0,
        ))

        lid, ci = lesson_id, i
        btn_color = iOSTheme.fill if done else ColorPalette.BLUE
        btn_text_color = iOSTheme.secondary_label if done else pygame.Color(255, 255, 255)
        row.add_child(Button(
            text=t("lesson_start"),
            on_click=lambda _id=lid, _ci=ci: _open_lesson(_id, course["id"], _ci),
            anchor="right", x=0, y=0,
            width=90, height=30, font_size=13,
            background_color=btn_color,
            text_color=btn_text_color,
            border_radius=8,
        ))
        card.add_child(row)

    return card


def _lesson_card(lesson: dict) -> VStack:
    done = is_complete(lesson["id"])
    card = VStack(
        spacing=10, padding=16, width=1.0,
        background_color=iOSTheme.secondary_background,
        border_radius=14,
    )

    header = FloatLayout(width=1.0, height=32)
    header.add_child(EmojiIcon("🎵", size=26, color=ColorPalette.BLUE,
                               anchor="left", x=0, y=0))
    header.add_child(Label(
        text=lesson["title"],
        font_size=15, bold=True,
        color=iOSTheme.label,
        anchor="left", x=34, y=0,
    ))
    if done:
        header.add_child(Label(
            text="✓",
            font_size=14, bold=True,
            color=pygame.Color(52, 199, 89),
            anchor="right", x=0, y=0,
        ))
    card.add_child(header)

    card.add_child(Label(
        text=lesson["description"],
        font_size=13,
        color=iOSTheme.secondary_label,
        width=1.0, height=40,
    ))

    lid = lesson["id"]
    card.add_child(Button(
        text=t("lesson_start"),
        on_click=lambda: _open_lesson(lid),
        width=0.5, height=36,
        font_size=14,
        background_color=iOSTheme.fill if done else ColorPalette.BLUE,
        text_color=iOSTheme.secondary_label if done else pygame.Color(255, 255, 255),
        border_radius=10,
    ))

    return card


def build():
    root   = FloatLayout(width=1.0, height=1.0, background_color=iOSTheme.background)
    scroll = VStack(spacing=14, padding=16, width=1.0, height=1.0)
    root.add_child(scroll)

    courses    = list_courses()
    standalone = standalone_lessons()
    all_lessons = {l["id"]: l for l in list_lessons()}

    if courses:
        scroll.add_child(Label(
            text=t("lessons_courses"),
            font_size=13, bold=True,
            color=iOSTheme.secondary_label,
            width=1.0, height=22,
        ))
        for course in courses:
            scroll.add_child(_course_card(course, all_lessons))

    if standalone:
        scroll.add_child(Label(
            text=t("lessons_standalone"),
            font_size=13, bold=True,
            color=iOSTheme.secondary_label,
            width=1.0, height=22,
        ))
        for lesson in standalone:
            scroll.add_child(_lesson_card(lesson))

    return root
