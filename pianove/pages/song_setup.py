import pygame
from pylay import (
    FloatLayout, VStack, Label, Button, SegmentedControl, ProgressBar,
    State, iOSTheme, EmojiIcon, ColorPalette
)
from pylay.widgets.icon import Icon
import pianove.context as ctx
from pianove.i18n import t
from pianove.components import GREEN, ORANGE

_hand_state = State(0)   # 0=right, 1=left, 2=both
_mode       = [0]        # 0=learning path, 1=free practice (kept while the app runs)

_HAND_KEYS  = ["right", "left", "both"]
_HAND_ICONS = {"right": "front_hand", "left": "back_hand", "both": "sign_language"}

_SEP_COLOR  = pygame.Color(120, 120, 128, 60)


def build():
    from pianove.song_store import get_song

    song_id = ctx.current_song_id
    song    = get_song(song_id) if song_id else None
    if song is None:
        ctx.router.navigate("home", "left")
        return FloatLayout(width=1.0, height=1.0)

    # back on this page: no step is being played
    ctx.song_range = None
    ctx.path_step  = None

    def _go_back():
        ctx.current_song_id = None
        ctx.router.navigate("home", "left")

    win_h = ctx.ui.height if ctx.ui else 768

    root = FloatLayout(width=1.0, height=1.0, background_color=iOSTheme.background)
    main = VStack(spacing=0, padding=0, width=1.0, height=win_h)
    root.add_child(main)

    nav = FloatLayout(width=1.0, height=52,
                      background_color=iOSTheme.secondary_background)
    nav.add_child(Button(
        text=t("back"), on_click=_go_back,
        anchor="left", x=12, y=0, width=72, height=34, font_size=14,
        background_color=iOSTheme.fill, text_color=iOSTheme.label,
        border_radius=8,
    ))
    nav.add_child(Label(
        text=t("song_setup_title"),
        font_size=16, bold=True, color=iOSTheme.label,
        anchor="center", x=0, y=0,
    ))
    main.add_child(nav)
    main.add_child(FloatLayout(width=1.0, height=1, background_color=_SEP_COLOR))

    compact = win_h < 640                     # a phone on its side: every line counts
    body = VStack(spacing=10 if compact else 14, padding=14 if compact else 20,
                  width=1.0, height=win_h - 54)
    body.add_child(_song_card(song, compact))

    def _on_mode(i):
        _mode[0] = i
        ctx.router.refresh()

    body.add_child(SegmentedControl(
        segments=[t("path_mode_path"), t("path_mode_free")],
        selected_index=State(_mode[0]),
        on_change=_on_mode,
        anchor="center", x=0, y=0,
        width=1.0, height=36,
    ))

    from pianove import song_path
    path = song_path.build_path(song_id) if _mode[0] == 0 else None
    if path and path["steps"]:
        _path_view(body, song_id, path)
    else:
        if _mode[0] == 0:          # nothing to cut into steps (a piece with one short part)
            body.add_child(Label(text=t("path_none"), font_size=13,
                                 color=iOSTheme.secondary_label, anchor="center", x=0, y=0,
                                 width=1.0, height=36))
        _free_view(body)

    main.add_child(body)
    return root


def _song_card(song: dict, compact: bool = False) -> FloatLayout:
    title    = song.get("title", "")
    composer = song.get("composer", "")
    n_bars   = song.get("n_bars", 0)
    diff     = song.get("difficulty", "beginner")

    diff_color = {
        "beginner":     pygame.Color(52, 199, 89),
        "intermediate": pygame.Color(255, 149, 0),
        "advanced":     pygame.Color(255, 59, 48),
    }.get(diff, iOSTheme.secondary_label)
    if compact:                               # title, then composer and length on one line
        card = FloatLayout(width=1.0, height=60,
                           background_color=iOSTheme.secondary_background,
                           border_radius=12)
        card.add_child(Icon("library_music", size=26, color=ColorPalette.BLUE,
                            anchor="left", x=16, y=0))
        card.add_child(Label(text=title, font_size=16, bold=True, color=iOSTheme.label,
                             anchor="left", x=56, y=-9))
        card.add_child(Label(text="  ·  ".join(x for x in (composer, t("song_bars", n=n_bars)) if x),
                             font_size=12, color=iOSTheme.secondary_label,
                             anchor="left", x=56, y=11))
        card.add_child(Label(text=t(f"diff_{diff}"), font_size=11, color=diff_color,
                             anchor="right", x=-16, y=0))
        return card

    card = FloatLayout(width=1.0, height=96,
                       background_color=iOSTheme.secondary_background,
                       border_radius=14)
    card.add_child(EmojiIcon("🎵", size=34, color=iOSTheme.label,
                             anchor="left", x=18, y=0))
    card.add_child(Label(
        text=title, font_size=17, bold=True, color=iOSTheme.label,
        anchor="left", x=66, y=-18 if composer else -10,
    ))
    if composer:
        card.add_child(Label(
            text=composer, font_size=13, color=iOSTheme.secondary_label,
            anchor="left", x=66, y=4,
        ))
    card.add_child(Label(
        text=t("song_bars", n=n_bars),
        font_size=12, color=iOSTheme.secondary_label,
        anchor="left", x=66, y=24 if composer else 10,
    ))
    card.add_child(Label(
        text=t(f"diff_{diff}"),
        font_size=11, color=diff_color,
        anchor="top_right", x=-16, y=14,
    ))
    return card


# ── The learning path ────────────────────────────────────────────────────────────────

def _start_step(step: dict):
    from pianove.pages.lesson import start_path_step
    start_path_step(step)
    ctx.router.navigate("lesson", "right")


def _path_view(body: VStack, song_id: str, path: dict):
    from pianove import song_path
    steps = path["steps"]
    done  = song_path.progress(song_id)
    nxt   = song_path.next_step(path, done)
    n_done = sum(1 for s in steps if s["id"] in done)

    # how far along, and the one button that matters: the next step
    prog = FloatLayout(width=1.0, height=22)
    prog.add_child(ProgressBar(progress=n_done / len(steps), width=0.70, height=6,
                               active_color=GREEN if n_done == len(steps) else ColorPalette.BLUE,
                               anchor="left", x=0, y=0))
    prog.add_child(Label(text=t("path_progress", done=n_done, total=len(steps)),
                         font_size=12, color=iOSTheme.secondary_label,
                         anchor="right", x=0, y=0))
    body.add_child(prog)
    if nxt < len(steps):
        key, fmt = steps[nxt]["title"]
        body.add_child(Button(
            text=t("path_continue", step=t(key, **fmt)) if n_done else t("path_begin"),
            on_click=lambda s=steps[nxt]: _start_step(s),
            width=1.0, height=48, font_size=15,
            background_color=ColorPalette.BLUE, text_color=pygame.Color(255, 255, 255),
            border_radius=14,
        ))
    else:
        body.add_child(Label(text=t("path_all_done"), font_size=15, bold=True, color=GREEN,
                             anchor="center", x=0, y=0, width=1.0, height=40))

    parts = {p["letter"]: p for p in path["parts"]}
    shown_part = None
    for i, step in enumerate(steps):
        letter = step["part"]
        if letter is not None and letter != shown_part:
            shown_part = letter
            body.add_child(_part_header(parts.get(letter), step))
        elif letter is None:
            shown_part = None
        body.add_child(_step_row(step, done.get(step["id"], 0), i == nxt))


def _part_header(part: dict | None, step: dict) -> FloatLayout:
    a, b = step["bars"]
    has_topics = bool(step["topics"])
    hdr = FloatLayout(width=1.0, height=52 if has_topics else 32)
    top = -9 if has_topics else 2
    hdr.add_child(Label(text=t("path_part", part=step["part"]), font_size=15, bold=True,
                        color=iOSTheme.label, anchor="left", x=2, y=top))
    hdr.add_child(Label(text=t("path_bars", first=a + 1, last=b), font_size=12,
                        color=iOSTheme.secondary_label, anchor="left", x=74, y=top + 1))
    diff = step["difficulty"] or 1
    for k in range(3):                                      # how hard: one to three dots
        hdr.add_child(FloatLayout(width=8, height=8, border_radius=4,
                                  background_color=(ORANGE if k < diff else iOSTheme.fill),
                                  anchor="right", x=-4 - (2 - k) * 12, y=top))
    if has_topics:
        hdr.add_child(Label(text=t("path_new", topics=" · ".join(t(k) for k in step["topics"])),
                            font_size=12, color=ColorPalette.BLUE,
                            anchor="left", x=2, y=14))
    return hdr


def _step_row(step: dict, stars: int, is_next: bool) -> FloatLayout:
    key, fmt = step["title"]
    done = stars > 0
    if done:
        icon, icon_color = "check_circle", GREEN
    elif is_next:
        icon, icon_color = "play_circle", ColorPalette.BLUE
    else:
        icon, icon_color = "lock", iOSTheme.fill_tertiary
    startable = done or is_next

    big = step["kind"] != "learn"                         # a join, or the whole piece
    row = FloatLayout(width=1.0, height=58 if big else 50,
                      background_color=(iOSTheme.secondary_background if (is_next or big)
                                        else None),
                      border_radius=12)
    row.add_child(Icon(icon, size=24, color=icon_color, anchor="left", x=12, y=0))
    label_color = iOSTheme.label if startable else iOSTheme.secondary_label
    row.add_child(Label(text=t(key, **fmt), font_size=14, bold=is_next or big,
                        color=label_color, anchor="left", x=46, y=-8))
    sub = (t("path_kind_join") if step["kind"] == "join" else
           t("path_kind_full") if step["kind"] == "full" else
           t("path_kind_learn"))
    row.add_child(Label(text=sub, font_size=11, color=iOSTheme.secondary_label,
                        anchor="left", x=46, y=10))
    if done:
        for k in range(3):
            row.add_child(Icon("star" if k < stars else "star_border", size=18,
                               color=ORANGE if k < stars else iOSTheme.fill_tertiary,
                               anchor="right", x=-12 - (2 - k) * 19, y=0))
    else:
        row.add_child(Icon(_HAND_ICONS.get(step["hand"], "piano"), size=20,
                           color=iOSTheme.secondary_label if startable else iOSTheme.fill_tertiary,
                           anchor="right", x=-14, y=0))
    if startable:
        row.add_child(Button(text="", on_click=lambda s=step: _start_step(s),
                             width=1.0, height=1.0, background_color=pygame.Color(0, 0, 0, 0),
                             border_radius=12))
    return row


# ── Free practice: any hand, the whole piece ─────────────────────────────────────────

def _free_view(body: VStack):
    _hand_state.value = 0

    def _start(phase: str = "practice"):
        # "practice": Pianove waits for each note, section by section.
        # "performance": play along at the song's own tempo after a count-in.
        # listening plays the whole piece, both hands
        ctx.song_range         = None
        ctx.path_step          = None
        ctx.current_song_hand  = "both" if phase == "listen" else _HAND_KEYS[_hand_state.value]
        ctx.lesson_current_idx = 0
        ctx.lesson_section_idx = 0
        ctx.lesson_completed   = False
        ctx.lesson_phase       = phase
        ctx.router.navigate("lesson", "right")

    body.add_child(Label(
        text=t("song_hand_label"),
        font_size=14, bold=True, color=iOSTheme.label,
        anchor="left", x=4, y=0,
    ))
    hand_desc_state = State(_hand_desc(0))

    def _on_hand(i):
        _hand_state.value = i
        hand_desc_state.value = _hand_desc(i)

    body.add_child(SegmentedControl(
        segments=[t("hand_right"), t("hand_left"), t("hand_both")],
        selected_index=_hand_state,
        on_change=_on_hand,
        anchor="center", x=0, y=0,
        width=1.0, height=36,
    ))
    body.add_child(Label(
        text=hand_desc_state,
        font_size=13, color=iOSTheme.secondary_label,
        anchor="center", x=0, y=0,
        width=1.0, height=40,
    ))

    # Start buttons: practise note by note, or play along in tempo; with beta features
    # also listen to the piece played for you
    from pianove.state import beta_features_state
    listen = bool(beta_features_state.value)
    bw = 0.32 if listen else 0.49
    buttons = FloatLayout(width=1.0, height=52)
    buttons.add_child(Button(
        text=t("song_start"),
        on_click=_start,
        anchor="left", x=0, y=0,
        width=bw, height=52, font_size=16,
        background_color=ColorPalette.BLUE,
        text_color=pygame.Color(255, 255, 255),
        border_radius=14,
    ))
    buttons.add_child(Button(
        text=t("song_play_along"),
        on_click=lambda: _start("performance"),
        anchor="center" if listen else "right", x=0, y=0,
        width=bw, height=52, font_size=16,
        background_color=iOSTheme.fill,
        text_color=iOSTheme.label,
        border_radius=14,
    ))
    if listen:
        buttons.add_child(Button(
            text=t("song_listen"),
            on_click=lambda: _start("listen"),
            anchor="right", x=0, y=0,
            width=bw, height=52, font_size=16,
            background_color=iOSTheme.fill,
            text_color=iOSTheme.label,
            border_radius=14,
        ))
    body.add_child(buttons)


def _hand_desc(i: int) -> str:
    return t(["hand_right_desc", "hand_left_desc", "hand_both_desc"][i])
