import datetime
import pygame
import pianove.context as ctx
from pylay import (
    FloatLayout, VStack, Card, Label, Button,
    ProgressBar, Badge, ProgressRing, LineChart,
    ColorPalette, iOSTheme, EmojiIcon,
)
from pylay.widgets.icon import Icon
from pianove.i18n import t
from pianove.state import name_state, storage
from pianove.ui_utils import ui_dims
from pianove.progress import (
    streak, is_complete, weekly_lessons,
    lessons_completed_count, course_complete,
    practice_sessions_total, practice_accuracy_avg,
    weekly_practice_sessions,
)
from pianove.lesson_loader import list_courses, load_lesson
from pianove.components import ORANGE, GREEN, RED, PURPLE, GOLD, GRAY, section_header

_WEEK_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _greeting_key() -> str:
    h = datetime.datetime.now().hour
    if h < 12:  return "greeting_morning"
    if h < 17:  return "greeting_afternoon"
    return "greeting_evening"


def _find_next(courses):
    for course in courses:
        for i, lid in enumerate(course["lessons"]):
            if not is_complete(lid):
                return load_lesson(lid), course, i
    return None, None, 0


def _minutes_to_str(mins: int) -> str:
    if mins == 0:
        return "—"
    h, m = divmod(mins, 60)
    return f"{h}h {m:02d}m" if h else f"{m}m"


def _acc_to_str(acc: float) -> str:
    return "—" if acc == 0.0 else f"{int(acc * 100)}%"


def _stat_card(value, label, color, icon_name, x_frac, w_frac=0.31):
    from pylay.core.scale import scaled_px
    card = Card(
        spacing=4, padding=12,
        anchor="top_left", x=x_frac, y=0,
        width=w_frac, height=1.0,
    )
    card.add_child(Icon(icon_name, size=20, color=color))
    card.add_child(Label(text=value, font_size=22, bold=True, color=color, height=30))
    card.add_child(Label(text=label, font_size=13, color=iOSTheme.secondary_label, height=18))
    return card


def _achievement(icon_name, label, color, x_frac, earned):
    bg         = color if earned else iOSTheme.secondary_background
    icon_color = pygame.Color(255, 255, 255) if earned else GRAY
    text_color = pygame.Color(255, 255, 255) if earned else GRAY
    badge = Card(
        spacing=2, padding=6,
        anchor="top_left", x=x_frac, y=0.0,
        width=0.22, height=1.0,
        background_color=bg,
    )
    badge.add_child(Icon(icon_name, size=22, color=icon_color, anchor="center", x=0, y=0))
    badge.add_child(Label(text=label, font_size=10, bold=True, color=text_color))
    return badge


def build():
    from pylay.core.scale import scaled_px

    U          = ui_dims()
    name       = name_state.value.strip() or t("friend")
    courses    = list_courses()
    cur_streak = streak()

    next_lesson, next_course, next_idx = _find_next(courses)

    today_idx   = datetime.date.today().weekday()
    today_count = weekly_lessons()[today_idx]

    lessons_done = lessons_completed_count()
    total_mins   = storage.get("total_minutes", 0)
    pr_total     = practice_sessions_total()
    pr_avg_acc   = practice_accuracy_avg()
    week_data    = weekly_lessons()
    pr_week_data = weekly_practice_sessions()

    ach_first   = lessons_done >= 1
    ach_course  = course_complete("beginner_path")
    ach_streak3 = cur_streak >= 3
    ach_ded     = len(storage.get("lesson_dates", [])) >= 7
    ach_reader  = pr_total >= 5
    ach_sharp   = pr_avg_acc >= 0.80 and pr_total >= 3

    root   = FloatLayout(width=1.0, height=1.0, background_color=iOSTheme.background)
    scroll = VStack(spacing=14, padding=16, width=1.0, height=1.0)
    root.add_child(scroll)

    # ── Greeting ──────────────────────────────────────────────────────────────
    greeting_row = FloatLayout(width=1.0, height=40)
    greeting_row.add_child(Label(
        text=t(_greeting_key(), name=name),
        font_size=U["title_size"] - 4, bold=True,
        color=iOSTheme.label,
        anchor="left", x=0, y=0,
    ))
    on_streak = cur_streak > 0
    greeting_row.add_child(Badge(
        text=t("streak_label", n=cur_streak),
        color=ORANGE if on_streak else iOSTheme.fill,
        icon_fn=Icon.as_icon_fn("local_fire_department", base_size=18),
        icon_size=18,
        text_color=pygame.Color(255, 255, 255) if on_streak else iOSTheme.secondary_label,
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

        cont.add_child(Button(
            text=t("continue") if n_done > 0 else t("lesson_start"),
            on_click=_start,
            width=0.4, height=34, font_size=13,
            background_color=ColorPalette.BLUE,
            text_color=pygame.Color(255, 255, 255),
            border_radius=10,
        ))
        scroll.add_child(cont)
    else:
        done_card = Card(width=1.0, height=92)
        done_card.add_child(EmojiIcon("🏆", size=28, color=ORANGE))
        done_card.add_child(Label(
            text=t("home_all_done"),
            font_size=15, bold=True, color=iOSTheme.label, height=22,
        ))
        scroll.add_child(done_card)

    # ── Daily goal ────────────────────────────────────────────────────────────
    scroll.add_child(section_header(t("daily_goal"), U))
    goal_progress = min(today_count, 1.0)
    goal     = Card(width=1.0, height=72)
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

    # ── Stats ─────────────────────────────────────────────────────────────────
    scroll.add_child(section_header(t("stats_lessons_section"), U))
    stats_row = FloatLayout(width=1.0, height=scaled_px(104))
    for card in [
        _stat_card(str(cur_streak),             t("stats_streak"),  ORANGE,            "local_fire_department", 0.0),
        _stat_card(str(lessons_done),            t("stats_lessons"), ColorPalette.BLUE, "school",                0.345),
        _stat_card(_minutes_to_str(total_mins),  t("stats_time"),    GREEN,             "schedule",              0.69),
    ]:
        stats_row.add_child(card)
    scroll.add_child(stats_row)

    # ── Weekly chart ──────────────────────────────────────────────────────────
    scroll.add_child(section_header(t("stats_week"), U))
    scroll.add_child(LineChart(
        data=week_data,
        labels=_WEEK_LABELS,
        active_color=ColorPalette.BLUE,
        title=t("stats_week"),
        width=1.0, height=scaled_px(160),
    ))

    # ── Sight-reading stats ───────────────────────────────────────────────────
    if pr_total > 0:
        scroll.add_child(section_header(t("stats_practice_section"), U))
        pr_row = FloatLayout(width=1.0, height=scaled_px(104))
        pr_row.add_child(_stat_card(str(pr_total),          t("stats_pr_sessions"), PURPLE, "auto_stories",        0.0,  w_frac=0.47))
        pr_row.add_child(_stat_card(_acc_to_str(pr_avg_acc), t("stats_pr_accuracy"), GREEN,  "center_focus_strong", 0.53, w_frac=0.47))
        scroll.add_child(pr_row)

        if any(v > 0 for v in pr_week_data):
            scroll.add_child(section_header(t("stats_pr_week"), U))
            scroll.add_child(LineChart(
                data=pr_week_data,
                labels=_WEEK_LABELS,
                active_color=PURPLE,
                title=t("stats_pr_week"),
                width=1.0, height=scaled_px(140),
            ))

    # ── Achievements ──────────────────────────────────────────────────────────
    scroll.add_child(section_header(t("stats_achievements"), U))

    badges_row1 = FloatLayout(width=1.0, height=scaled_px(64))
    for icon, label, color, x_frac, earned in [
        ("school",                t("ach_first_lesson"), GREEN,             0.0,   ach_first),
        ("emoji_events",          t("ach_course_done"),  GOLD,              0.245, ach_course),
        ("local_fire_department", t("ach_streak_3"),     ORANGE,            0.49,  ach_streak3),
        ("hotel_class",           t("ach_dedicated"),    ColorPalette.BLUE, 0.735, ach_ded),
    ]:
        badges_row1.add_child(_achievement(icon, label, color, x_frac, earned))
    scroll.add_child(badges_row1)

    badges_row2 = FloatLayout(width=1.0, height=scaled_px(64))
    for icon, label, color, x_frac, earned in [
        ("auto_stories",        t("ach_sight_reader"), PURPLE, 0.0,   ach_reader),
        ("center_focus_strong", t("ach_sharp_eye"),    GREEN,  0.245, ach_sharp),
    ]:
        badges_row2.add_child(_achievement(icon, label, color, x_frac, earned))
    scroll.add_child(badges_row2)

    return root
