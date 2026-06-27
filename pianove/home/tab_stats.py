import pygame
from pylay import FloatLayout, VStack, Card, Label, LineChart, ColorPalette, iOSTheme, EmojiIcon
from pylay.widgets.icon import Icon
from pianove.i18n import t
from pianove.ui_utils import ui_dims
from pianove.progress import (
    streak, lessons_completed_count, weekly_lessons, is_complete, course_complete,
    practice_sessions_total, practice_accuracy_avg, weekly_practice_sessions,
)
from pianove.state import storage
from pianove.components import ORANGE, GREEN, RED, PURPLE, GOLD, GRAY, section_header

_WEEK_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _minutes_to_str(mins: int) -> str:
    if mins == 0:
        return "—"
    h, m = divmod(mins, 60)
    return f"{h}h {m:02d}m" if h else f"{m}m"


def _acc_to_str(acc: float) -> str:
    if acc == 0.0:
        return "—"
    return f"{int(acc * 100)}%"


def _stat_card(value: str, label: str, color: pygame.Color, icon: str,
               x_frac: float, w_frac: float = 0.31) -> Card:
    card = Card(
        spacing=4, padding=12,
        anchor="top_left", x=x_frac, y=0,
        width=w_frac, height=1.0,
    )
    card.add_child(EmojiIcon(icon, size=20, color=color))
    card.add_child(Label(text=value, font_size=22, bold=True, color=color, height=30))
    card.add_child(Label(text=label, font_size=13, color=iOSTheme.secondary_label, height=18))
    return card


def _achievement(icon: str, label: str, color: pygame.Color,
                 x_frac: float, earned: bool) -> Card:
    bg         = color if earned else iOSTheme.secondary_background
    icon_color = pygame.Color(255, 255, 255) if earned else GRAY
    text_color = pygame.Color(255, 255, 255) if earned else GRAY
    badge = Card(
        spacing=2, padding=6,
        anchor="top_left", x=x_frac, y=0.0,
        width=0.22, height=1.0,
        background_color=bg,
    )
    badge.add_child(Icon(icon, size=22, color=icon_color,
                         anchor="center", x=0, y=0))
    badge.add_child(Label(text=label, font_size=10, bold=True, color=text_color))
    return badge


def build():
    U = ui_dims()

    cur_streak     = streak()
    lessons_done   = lessons_completed_count()
    total_mins     = storage.get("total_minutes", 0)
    week_data      = weekly_lessons()
    pr_total       = practice_sessions_total()
    pr_avg_acc     = practice_accuracy_avg()
    pr_week_data   = weekly_practice_sessions()

    # Achievements
    ach_first    = lessons_done >= 1
    ach_course   = course_complete("beginner_path")
    ach_streak3  = cur_streak >= 3
    ach_ded      = len(storage.get("lesson_dates", [])) >= 7
    ach_reader   = pr_total >= 5
    ach_sharp    = pr_avg_acc >= 0.80 and pr_total >= 3

    root   = FloatLayout(width=1.0, height=1.0, background_color=iOSTheme.background)
    scroll = VStack(spacing=14, padding=16, width=1.0, height=1.0)
    root.add_child(scroll)

    scroll.add_child(Label(
        text=t("stats_title"),
        font_size=U["title_size"] - 6,
        bold=True, color=iOSTheme.label,
    ))

    from pylay.core.scale import scaled_px

    scroll.add_child(section_header(t("stats_lessons_section"), U))
    stats_row = FloatLayout(width=1.0, height=scaled_px(104))
    cards = [
        (_stat_card(str(cur_streak),            t("stats_streak"),  ORANGE,           "🔥", 0.0)),
        (_stat_card(str(lessons_done),           t("stats_lessons"), ColorPalette.BLUE, "🎓", 0.345)),
        (_stat_card(_minutes_to_str(total_mins), t("stats_time"),    GREEN,            "⏱", 0.69)),
    ]
    for card in cards:
        stats_row.add_child(card)
    scroll.add_child(stats_row)

    scroll.add_child(section_header(t("stats_week"), U))
    scroll.add_child(LineChart(
        data=week_data,
        labels=_WEEK_LABELS,
        active_color=ColorPalette.BLUE,
        title=t("stats_week"),
        width=1.0, height=scaled_px(160),
    ))

    scroll.add_child(section_header(t("stats_practice_section"), U))

    pr_row = FloatLayout(width=1.0, height=scaled_px(104))
    pr_row.add_child(_stat_card(
        str(pr_total),         t("stats_pr_sessions"), PURPLE, "🎯", 0.0,   w_frac=0.47,
    ))
    pr_row.add_child(_stat_card(
        _acc_to_str(pr_avg_acc), t("stats_pr_accuracy"), GREEN,  "✅", 0.53, w_frac=0.47,
    ))
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

    scroll.add_child(section_header(t("stats_achievements"), U))

    badges_row1 = FloatLayout(width=1.0, height=scaled_px(64))
    row1 = [
        ("school",                t("ach_first_lesson"), GREEN,             0.0,   ach_first),
        ("emoji_events",          t("ach_course_done"),  GOLD,              0.245, ach_course),
        ("local_fire_department", t("ach_streak_3"),     ORANGE,            0.49,  ach_streak3),
        ("hotel_class",           t("ach_dedicated"),    ColorPalette.BLUE, 0.735, ach_ded),
    ]
    for icon, label, color, x_frac, earned in row1:
        badges_row1.add_child(_achievement(icon, label, color, x_frac, earned))
    scroll.add_child(badges_row1)

    badges_row2 = FloatLayout(width=1.0, height=scaled_px(64))
    row2 = [
        ("auto_stories",        t("ach_sight_reader"), PURPLE, 0.0,   ach_reader),
        ("center_focus_strong", t("ach_sharp_eye"),    GREEN,  0.245, ach_sharp),
    ]
    for icon, label, color, x_frac, earned in row2:
        badges_row2.add_child(_achievement(icon, label, color, x_frac, earned))
    scroll.add_child(badges_row2)

    return root
