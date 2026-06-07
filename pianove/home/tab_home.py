import datetime
import pygame
import pianove.context as ctx
from pylay import FloatLayout, VStack, Card, Label, Button, ProgressBar, Badge, ProgressRing, ColorPalette, iOSTheme, EmojiIcon
from pianove.i18n import t
from pianove.state import name_state
from pianove.ui_utils import ui_dims
from pianove.progress import streak, is_complete, weekly_lessons
from pianove.lesson_loader import list_courses, load_lesson
from pianove.components import ORANGE, GREEN, section_header


def _greeting_key() -> str:
    h = datetime.datetime.now().hour
    if h < 12:  return "greeting_morning"
    if h < 17:  return "greeting_afternoon"
    return "greeting_evening"


def _find_next(courses: list[dict]) -> tuple[dict | None, dict | None, int]:
    """Return (lesson_info, course, course_index) for first incomplete lesson."""
    for course in courses:
        for i, lid in enumerate(course["lessons"]):
            if not is_complete(lid):
                return load_lesson(lid), course, i
    return None, None, 0


def build():
    U      = ui_dims()
    name   = name_state.value.strip() or t("friend")
    courses = list_courses()
    cur_streak = streak()

    # Next lesson to play
    next_lesson, next_course, next_idx = _find_next(courses)

    # Today's practice (index 0=Mon … 6=Sun)
    today_idx   = datetime.date.today().weekday()
    today_count = weekly_lessons()[today_idx]

    root   = FloatLayout(width=1.0, height=1.0, background_color=iOSTheme.background)
    scroll = VStack(spacing=14, padding=16, width=1.0, height=1.0)
    root.add_child(scroll)

    # ── Greeting row ──────────────────────────────────────────────────────────
    greeting_row = FloatLayout(width=1.0, height=40)
    greeting_row.add_child(Label(
        text=t(_greeting_key(), name=name),
        font_size=U["title_size"] - 4, bold=True,
        color=iOSTheme.label,
        anchor="left", x=0, y=0,
    ))
    greeting_row.add_child(Badge(
        text=t("streak_label", n=cur_streak),
        color=ORANGE if cur_streak > 0 else iOSTheme.fill,
        icon="🔥", icon_size=20,
        text_color=pygame.Color(255, 255, 255) if cur_streak > 0 else iOSTheme.secondary_label,
        height=36, width=120,
        anchor="right", x=0, y=0,
    ))
    scroll.add_child(greeting_row)

    # ── Continue card ─────────────────────────────────────────────────────────
    scroll.add_child(section_header(t("continue_label"), U))

    if next_lesson and next_course:
        n_total  = len(next_course["lessons"])
        n_done   = sum(1 for lid in next_course["lessons"] if is_complete(lid))
        progress = n_done / n_total

        cont = Card(width=1.0, height=138)
        cont.add_child(Label(
            text=next_lesson["title"],
            font_size=15, bold=True, color=iOSTheme.label, height=22,
        ))
        cont.add_child(Label(
            text=f"{next_course['title']}  ·  {t('home_n_of_done', done=n_done, total=n_total)}",
            font_size=12, color=iOSTheme.secondary_label, height=18,
        ))
        cont.add_child(ProgressBar(
            progress=progress, width=1.0, height=6,
            active_color=ColorPalette.BLUE,
        ))

        lid, cid, ci = next_lesson["id"], next_course["id"], next_idx
        def _start():
            ctx.current_lesson_id    = lid
            ctx.current_course_id    = cid
            ctx.current_course_index = ci
            ctx.router.navigate("lesson", "right")

        btn_text = t("continue") if n_done > 0 else t("lesson_start")
        cont.add_child(Button(
            text=btn_text,
            on_click=_start,
            width=0.4, height=34, font_size=13,
            background_color=ColorPalette.BLUE,
            text_color=pygame.Color(255, 255, 255),
            border_radius=10,
        ))
        scroll.add_child(cont)
    else:
        # All lessons done
        done_card = Card(width=1.0, height=92)
        done_card.add_child(EmojiIcon("🏆", size=28, color=ORANGE))
        done_card.add_child(Label(
            text=t("home_all_done"),
            font_size=15, bold=True, color=iOSTheme.label, height=22,
        ))
        scroll.add_child(done_card)

    # ── Daily goal card ───────────────────────────────────────────────────────
    scroll.add_child(section_header(t("daily_goal"), U))
    goal_progress = min(today_count, 1.0)
    goal = Card(width=1.0, height=72)
    goal_row = FloatLayout(width=1.0, height=44)
    goal_row.add_child(ProgressRing(
        progress=goal_progress, size=44, stroke=5,
        active_color=GREEN,
        anchor="left", x=0, y=0,
    ))
    goal_row.add_child(Label(
        text=t("home_today_progress", n=int(today_count)),
        font_size=14, bold=True, color=iOSTheme.label,
        anchor="left", x=56, y=0,
    ))
    goal.add_child(goal_row)
    scroll.add_child(goal)

    # ── Your courses ──────────────────────────────────────────────────────────
    if courses:
        scroll.add_child(section_header(t("home_courses"), U))
        for course in courses:
            lessons   = course["lessons"]
            n_total   = len(lessons)
            n_done    = sum(1 for lid in lessons if is_complete(lid))
            progress  = n_done / n_total if n_total else 0.0

            # Find first incomplete lesson for this course's button
            next_lid = next((lid for lid in lessons if not is_complete(lid)), lessons[0])
            next_ci  = lessons.index(next_lid)

            c = Card(width=1.0, height=116)
            header = FloatLayout(width=1.0, height=30)
            header.add_child(EmojiIcon("🎓", size=22, color=ColorPalette.BLUE,
                                       anchor="left", x=0, y=0))
            header.add_child(Label(
                text=course["title"],
                font_size=14, bold=True, color=iOSTheme.label,
                anchor="left", x=30, y=0,
            ))
            header.add_child(Label(
                text=t("home_n_of_done", done=n_done, total=n_total),
                font_size=12, color=iOSTheme.secondary_label,
                anchor="right", x=0, y=0,
            ))
            c.add_child(header)
            c.add_child(ProgressBar(
                progress=progress, width=1.0, height=6,
                active_color=GREEN if progress >= 1.0 else ColorPalette.BLUE,
            ))

            cid = course["id"]
            def _open_course(lid=next_lid, cid=cid, ci=next_ci):
                ctx.current_lesson_id    = lid
                ctx.current_course_id    = cid
                ctx.current_course_index = ci
                ctx.router.navigate("lesson", "right")

            btn_text = t("continue") if 0 < n_done < n_total else (
                t("lesson_start") if n_done == 0 else t("lesson_restart")
            )
            c.add_child(Button(
                text=btn_text,
                on_click=_open_course,
                width=0.4, height=32, font_size=13,
                background_color=GREEN if progress >= 1.0 else ColorPalette.BLUE,
                text_color=pygame.Color(255, 255, 255),
                border_radius=10,
            ))
            scroll.add_child(c)

    return root
