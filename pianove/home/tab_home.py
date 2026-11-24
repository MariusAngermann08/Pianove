import datetime
import pygame
import pianove.context as ctx
from pylay import (
    FloatLayout, VStack, Card, Label, Button,
    ProgressBar, Badge, ProgressRing, BarChart,
    ColorPalette, iOSTheme, EmojiIcon,
)
from pylay.widgets.icon import Icon
from pianove.i18n import t
from pianove.state import name_state, storage
from pianove.ui_utils import ui_dims
from pianove.progress import (
    streak, is_complete, active_days,
    lessons_completed_count, course_complete,
    practice_sessions_total, practice_accuracy_avg,
    weekly_practice_sessions, recent_minutes, minutes_today,
    total_practice_minutes, daily_goal_minutes,
)
from pianove.lesson_loader import list_courses, load_lesson
from pianove.components import ORANGE, GREEN, RED, PURPLE, GOLD, GRAY, section_header

def _week_labels() -> list[str]:
    return [t(f"week_{d}") for d in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")]


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
    badge.add_child(Label(text=label, font_size=12, bold=True, color=text_color))
    return badge


def build():
    from pylay.core.scale import scaled_px

    U          = ui_dims()
    name       = name_state.value.strip() or t("friend")
    courses    = list_courses()
    cur_streak = streak()

    from pianove import recommend
    next_lesson, next_course, next_idx = _find_next(recommend.ordered_courses(courses))

    today_idx    = datetime.date.today().weekday()
    goal_mins    = daily_goal_minutes()
    today_mins   = minutes_today()

    lessons_done = lessons_completed_count()
    total_mins   = total_practice_minutes()
    pr_total     = practice_sessions_total()
    pr_avg_acc   = practice_accuracy_avg()
    recent       = recent_minutes(7)
    week_data    = [m for _, m in recent]
    week_names   = _week_labels()
    recent_lbls  = [week_names[d.weekday()] for d, _ in recent]
    pr_week_data = weekly_practice_sessions()

    ach_first   = lessons_done >= 1
    ach_course  = course_complete("beginner_path")
    ach_streak3 = cur_streak >= 3
    ach_ded     = len(active_days()) >= 7
    ach_reader  = pr_total >= 5
    ach_sharp   = pr_avg_acc >= 0.80 and pr_total >= 3

    root   = FloatLayout(width=1.0, height=1.0, background_color=iOSTheme.background)
    scroll = VStack(spacing=14, padding=16, width=1.0, height=1.0)
    root.add_child(scroll)

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
        height=36, width=150,
        anchor="right", x=0, y=0,
    ))
    scroll.add_child(greeting_row)

    # ── today's session: what to play, decided for you ─────────────────────────
    from pianove import session
    scroll.add_child(_session_card(session, U))

    # ── continue: the song or lesson you opened last first ─────────────────────
    cont = _continue_card(session, next_lesson, next_course, next_idx)
    if cont is not None:
        scroll.add_child(section_header(t("continue_label"), U))
        scroll.add_child(cont)

    from pianove.song_store import list_songs
    if recommend.suggests_songs() and not list_songs():
        def _to_songs():
            from pianove.home import container
            container._active_tab.value = 1
            ctx.home_page = "songs"
            ctx.router.reload_current_page()
        own = FloatLayout(width=1.0, height=72, background_color=iOSTheme.secondary_background,
                          border_radius=16)
        own.add_child(Icon("library_music", size=26, color=ColorPalette.BLUE,
                           anchor="left", x=18, y=0))
        own.add_child(Label(text=t("home_own_piece"), font_size=15, bold=True,
                            color=iOSTheme.label, anchor="left", x=58, y=-10))
        own.add_child(Label(text=t("home_own_piece_desc"), font_size=12,
                            color=iOSTheme.secondary_label, anchor="left", x=58, y=11))
        own.add_child(Button(text=t("home_open_songs"), on_click=_to_songs,
                             anchor="right", x=-16, y=0, width=130, height=34, font_size=13,
                             background_color=iOSTheme.fill, text_color=iOSTheme.label,
                             border_radius=10))
        scroll.add_child(own)

    scroll.add_child(section_header(t("daily_goal"), U))
    reached  = today_mins >= goal_mins
    goal     = Card(width=1.0, height=80)
    goal_row = FloatLayout(width=1.0, height=52)
    goal_row.add_child(ProgressRing(
        progress=min(1.0, today_mins / max(1, goal_mins)), size=48, stroke=6,
        active_color=GREEN,
        anchor="left", x=0, y=0,
    ))
    if reached:
        goal_row.add_child(Icon("check", size=24, color=GREEN, anchor="left", x=12, y=0))
    goal_row.add_child(Label(
        text=t("home_goal_reached", done=today_mins) if reached
        else t("home_goal_today", done=today_mins, total=goal_mins),
        font_size=15, bold=True, color=GREEN if reached else iOSTheme.label,
        anchor="left", x=64, y=-10,
    ))
    goal_row.add_child(Label(
        text=t("home_goal_hint", total=goal_mins),
        font_size=12, color=iOSTheme.secondary_label,
        anchor="left", x=64, y=12,
    ))
    goal.add_child(goal_row)

    def _to_settings():                       # "change it in Settings": a tap takes you there
        ctx.home_page = "settings"
        ctx.router.reload_current_page()
    goal_wrap = FloatLayout(width=1.0, height=80)
    goal.anchor, goal.x_spec, goal.y_spec = "top_left", 0, 0
    goal_wrap.add_child(goal)
    goal_wrap.add_child(Button(text="", on_click=_to_settings, width=1.0, height=1.0,
                               background_color=pygame.Color(0, 0, 0, 0), border_radius=16))
    scroll.add_child(goal_wrap)

    scroll.add_child(section_header(t("home_overview"), U))
    stats_row = FloatLayout(width=1.0, height=scaled_px(104))
    for card in [
        _stat_card(str(cur_streak),             t("stats_streak"),  ORANGE,            "local_fire_department", 0.0),
        _stat_card(str(lessons_done),            t("stats_lessons"), ColorPalette.BLUE, "school",                0.345),
        _stat_card(_minutes_to_str(total_mins),  t("stats_time"),    GREEN,             "schedule",              0.69),
    ]:
        stats_row.add_child(card)
    scroll.add_child(stats_row)

    scroll.add_child(section_header(t("home_last_7_days"), U))
    scroll.add_child(BarChart(
        data=week_data,
        labels=recent_lbls,
        active_color=ColorPalette.BLUE,
        title=t("home_week_minutes") if any(week_data) else t("home_week_empty"),
        highlight=len(week_data) - 1,
        target=goal_mins if any(week_data) else None,
        unit="min",
        width=1.0, height=scaled_px(180),
    ))

    if pr_total > 0:
        scroll.add_child(section_header(t("stats_practice_section"), U))
        pr_row = FloatLayout(width=1.0, height=scaled_px(104))
        pr_row.add_child(_stat_card(str(pr_total),          t("stats_pr_sessions"), ColorPalette.BLUE, "auto_stories",        0.0,  w_frac=0.47))
        pr_row.add_child(_stat_card(_acc_to_str(pr_avg_acc), t("stats_pr_accuracy"), GREEN,  "center_focus_strong", 0.53, w_frac=0.47))
        scroll.add_child(pr_row)

        if any(v > 0 for v in pr_week_data):
            scroll.add_child(BarChart(
                data=pr_week_data,
                labels=_week_labels(),
                active_color=ColorPalette.BLUE,
                title=t("stats_pr_week_sessions"),
                highlight=today_idx,
                width=1.0, height=scaled_px(150),
            ))

    scroll.add_child(section_header(t("home_repertoire"), U))
    scroll.add_child(_repertoire(session, lessons_done))

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


def _session_card(session, U) -> FloatLayout:
    """Today's session: the plan (or how far it got) and one button."""
    active, done_today = session.active(), session.finished_today()
    st = session._state()
    items = st["items"] if st else session.plan()
    pos = st["i"] if st else 0
    rows = len(items)
    card = FloatLayout(width=1.0, height=96 + rows * 30, background_color=iOSTheme.secondary_background,
                       border_radius=18)
    card.add_child(Icon("event_available" if not done_today else "check_circle", size=26,
                        color=GREEN if done_today else ColorPalette.BLUE,
                        anchor="top_left", x=20, y=20))
    card.add_child(Label(text=t("session_title"), font_size=18, bold=True, color=iOSTheme.label,
                         anchor="top_left", x=58, y=18))
    card.add_child(Label(text=t("session_done") if done_today else
                         t("session_sub", min=session.minutes(items)),
                         font_size=13, color=GREEN if done_today else iOSTheme.secondary_label,
                         anchor="top_left", x=58, y=44))
    for k, it in enumerate(items):
        y = 76 + k * 30
        finished = k < pos
        now = active and k == pos
        card.add_child(Icon("check_circle" if finished else ("play_circle" if now else "radio_button_unchecked"),
                            size=18, color=GREEN if finished else (ColorPalette.BLUE if now else iOSTheme.fill_tertiary),
                            anchor="top_left", x=58, y=y))
        card.add_child(Label(text=session.describe(it), font_size=14, bold=now,
                             color=iOSTheme.secondary_label if finished else iOSTheme.label,
                             anchor="top_left", x=86, y=y))
        card.add_child(Label(text=t("lessons_minutes", n=it.get("minutes", 3)), font_size=12,
                             color=iOSTheme.secondary_label, anchor="top_right", x=-20, y=y + 1))
    if done_today:
        btn = Button(text=t("session_again"), on_click=session.start,
                     anchor="top_right", x=-20, y=20, width=150, height=38, font_size=14,
                     background_color=iOSTheme.fill, text_color=iOSTheme.label, border_radius=10)
    elif active:
        k, n = session.position()
        btn = Button(text=t("session_continue", k=k, n=n), on_click=session.launch_next,
                     anchor="top_right", x=-20, y=20, width=170, height=38, font_size=14,
                     background_color=ColorPalette.BLUE, text_color=pygame.Color(255, 255, 255),
                     border_radius=10)
    else:
        btn = Button(text=t("session_start"), on_click=session.start,
                     anchor="top_right", x=-20, y=20, width=150, height=38, font_size=15,
                     background_color=ColorPalette.BLUE, text_color=pygame.Color(255, 255, 255),
                     border_radius=10)
    card.add_child(btn)
    return card


def _continue_card(session, next_lesson, next_course, next_idx):
    """The song or lesson opened last, with the other one as a smaller second line."""
    sp = session.song_in_progress()
    last = session.last_activity() or {}
    song_first = sp is not None and (last.get("kind") == "song" or next_lesson is None)
    if sp is None and not next_lesson:
        done_card = Card(width=1.0, height=92)
        done_card.add_child(EmojiIcon("🏆", size=28, color=ORANGE))
        done_card.add_child(Label(text=t("home_all_done"), font_size=15, bold=True,
                                  color=iOSTheme.label, height=22))
        return done_card

    def _start_lesson(lid=next_lesson["id"] if next_lesson else None,
                      cid=next_course["id"] if next_course else None, ci=next_idx):
        ctx.practice_mode = False
        ctx.current_song_id = None
        ctx.path_step = ctx.song_range = None
        ctx.current_lesson_id = lid
        ctx.current_course_id = cid
        ctx.current_course_index = ci
        ctx.lesson_step_idx = ctx.lesson_current_idx = ctx.lesson_section_idx = 0
        ctx.lesson_completed = False
        ctx.router.navigate("lesson", "right")

    def _start_song():
        song, step = sp
        from pianove.pages.lesson import start_path_step
        ctx.practice_mode = False
        ctx.current_song_id = song["id"]
        start_path_step(step)
        ctx.router.navigate("lesson", "right")

    def _song_line():
        from pianove import song_path
        song, step = sp
        steps = song_path.build_path(song["id"])["steps"]
        done = song_path.progress(song["id"])
        n_done = sum(1 for st in steps if st["id"] in done)
        key, fmt = step["title"]
        return (song.get("title", ""), t("home_continue_song", step=t(key, **fmt)),
                n_done / max(1, len(steps)), _start_song, "library_music")

    def _lesson_line():
        lessons = next_course["lessons"]
        n_done = sum(1 for lid in lessons if is_complete(lid))
        return (next_lesson["title"],
                f"{next_course['title']}  ·  {t('home_n_of_done', done=n_done, total=len(lessons))}",
                n_done / max(1, len(lessons)), _start_lesson, "school")

    main_line = _song_line() if song_first else _lesson_line()
    other = (_lesson_line() if song_first else _song_line()) if (sp and next_lesson) else None

    card = FloatLayout(width=1.0, height=104 if other else 84,
                       background_color=iOSTheme.secondary_background, border_radius=16)
    title, sub, prog, action, icon = main_line
    card.add_child(Icon(icon, size=26, color=ColorPalette.BLUE, anchor="top_left", x=18, y=18))
    card.add_child(Label(text=title, font_size=16, bold=True, color=iOSTheme.label,
                         anchor="top_left", x=58, y=14))
    card.add_child(Label(text=sub, font_size=13, color=iOSTheme.secondary_label,
                         anchor="top_left", x=58, y=38))
    card.add_child(ProgressBar(progress=prog, width=0.5, height=5, active_color=ColorPalette.BLUE,
                               anchor="top_left", x=58, y=62))
    card.add_child(Button(text=t("continue"), on_click=action,
                          anchor="top_right", x=-18, y=18, width=130, height=38, font_size=14,
                          background_color=ColorPalette.BLUE, text_color=pygame.Color(255, 255, 255),
                          border_radius=10))
    if other:
        o_title, o_sub, _, o_action, _ = other
        o_text = f"{t('home_or')}  {o_title}  ·  {o_sub}"
        card.add_child(Button(text=o_text, on_click=o_action,
                              anchor="bottom_left", x=52, y=-8, width=24 + int(len(o_text) * 6.6),
                              height=26, font_size=12,
                              background_color=pygame.Color(0, 0, 0, 0), text_color=ColorPalette.BLUE,
                              border_radius=6))
    return card


def _repertoire(session, lessons_done: int) -> FloatLayout:
    """The pieces you can play: songs whose learning path is done, as chips."""
    songs = session.learned_songs()
    if not songs:
        box = FloatLayout(width=1.0, height=58, background_color=iOSTheme.secondary_background,
                          border_radius=14)
        box.add_child(Icon("piano", size=22, color=iOSTheme.secondary_label, anchor="left", x=18, y=0))
        box.add_child(Label(text=t("home_repertoire_empty"), font_size=13,
                            color=iOSTheme.secondary_label, anchor="left", x=52, y=-8))
        box.add_child(Label(text=t("home_lessons_done", n=lessons_done), font_size=12,
                            color=iOSTheme.secondary_label, anchor="left", x=52, y=11))
        return box
    row = FloatLayout(width=1.0, height=48)
    x = 0
    for s in songs[:6]:
        w = 30 + int(len(s.get("title", "")) * 8.2)

        def _open(_id=s["id"]):
            ctx.current_song_id = _id
            ctx.router.navigate("song_setup", "right")
        row.add_child(Button(text="♪  " + s.get("title", ""), on_click=_open,
                             anchor="top_left", x=x, y=4, width=w, height=38, font_size=13,
                             background_color=iOSTheme.secondary_background, text_color=iOSTheme.label,
                             border_radius=19))
        x += w + 10
    return row
