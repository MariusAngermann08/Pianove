import pygame
from pylay import Label, Button, FloatLayout, ColorPalette, iOSTheme
from pianove.i18n import t
from pianove.state import (
    name_state, experience_state, midi_device_state, language_state,
    summary_text, refresh_summary, storage,
)
from pianove.ui_utils import page_shell, ui_dims, set_continue_enabled
import pianove.context as ctx


def _save():
    storage.set("onboarding_complete", True)
    storage.set("name", name_state.value.strip())
    storage.set("experience", experience_state.value)
    storage.set("language", language_state.value)


def _go_home():
    _save()
    ctx.router.navigate("home", "right")


def _first_lesson():
    """Straight into the first lesson of the course suggested for your experience."""
    _save()
    from pianove import recommend
    from pianove.lesson_loader import list_courses
    from pianove.progress import is_complete
    course = next((c for c in list_courses() if c["id"] == recommend.course_id()), None)
    if not course or not course["lessons"]:
        _go_home()
        return
    idx = next((i for i, lid in enumerate(course["lessons"]) if not is_complete(lid)), 0)
    ctx.current_lesson_id    = course["lessons"][idx]
    ctx.current_course_id    = course["id"]
    ctx.current_course_index = idx
    ctx.lesson_step_idx      = 0
    ctx.router.navigate("lesson", "right")


def build():
    U = ui_dims()
    refresh_summary()
    root, card, content, _ = page_shell(
        t("ready_title"),
        t("ready_subtitle"),
        page_id="ready",
        show_back=True,
        next_label=t("ready_start"),        # the main way on: straight into a lesson
        on_next=_first_lesson,
    )

    content.add_child(
        Label(
            text=summary_text,
            font_size=U["summary_size"],
            color=iOSTheme.label,
            wrap_width=int(U["subtitle_wrap"] * 0.85),
            width=0.95,
            height=0.5,
        )
    )

    from pianove import recommend
    from pianove.lesson_loader import list_courses
    course = next((c for c in list_courses() if c["id"] == recommend.course_id()), None)
    if course:
        content.add_child(Label(
            text=t("ready_suggested", course=course["title"]),
            font_size=U["summary_size"], bold=True, color=ColorPalette.BLUE,
            width=0.95,
        ))
    content.add_child(Button(
        text=t("ready_go_home"),
        on_click=_go_home,
        width=0.98,
        height=U["field_h_frac"] * 0.75,
        font_size=U["option_font"],
        background_color=iOSTheme.fill,
        text_color=iOSTheme.label,
        border_radius=10,
    ))
    return root
