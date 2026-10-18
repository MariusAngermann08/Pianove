import pygame
from pylay import (
    FloatLayout, VStack, Label, Button, SegmentedControl,
    State, iOSTheme, EmojiIcon, ColorPalette
)
import pianove.context as ctx
from pianove.i18n import t
from pianove.ui_utils import ui_dims

_hand_state = State(0)   # 0=right, 1=left, 2=both

_HAND_KEYS  = ["right", "left", "both"]

_SEP_COLOR  = pygame.Color(120, 120, 128, 60)


def build():
    from pianove.song_store import get_song

    song_id = ctx.current_song_id
    song    = get_song(song_id) if song_id else None
    if song is None:
        ctx.router.navigate("home", "left")
        return FloatLayout(width=1.0, height=1.0)

    title    = song.get("title", "")
    composer = song.get("composer", "")
    n_bars   = song.get("n_bars", 0)
    diff     = song.get("difficulty", "beginner")

    _hand_state.value = 0   # reset each build

    def _go_back():
        ctx.current_song_id = None
        ctx.router.navigate("home", "left")

    def _start(phase: str = "practice"):
        # "practice": Pianove waits for each note, section by section.
        # "performance": play along at the song's own tempo after a count-in.
        ctx.current_song_hand  = _HAND_KEYS[_hand_state.value]
        ctx.lesson_current_idx = 0
        ctx.lesson_section_idx = 0
        ctx.lesson_completed   = False
        ctx.lesson_phase       = phase
        ctx.router.navigate("lesson", "right")

    win_h = ctx.ui.height if ctx.ui else 768

    root = FloatLayout(width=1.0, height=1.0, background_color=iOSTheme.background)
    main = VStack(spacing=0, padding=0, width=1.0, height=win_h)
    root.add_child(main)

    # Nav bar
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

    # Body
    body = VStack(spacing=28, padding=40, width=1.0, height=win_h - 54)

    # Song info card
    card = FloatLayout(width=1.0, height=110,
                       background_color=iOSTheme.secondary_background,
                       border_radius=14)
    card.add_child(EmojiIcon("🎵", size=36, color=iOSTheme.label,
                             anchor="left", x=20, y=-24))
    card.add_child(Label(
        text=title, font_size=17, bold=True, color=iOSTheme.label,
        anchor="left", x=68, y=-18,
    ))
    if composer:
        card.add_child(Label(
            text=composer, font_size=13, color=iOSTheme.secondary_label,
            anchor="left", x=68, y=6,
        ))
    card.add_child(Label(
        text=t("song_bars", n=n_bars),
        font_size=12, color=iOSTheme.secondary_label,
        anchor="left", x=68, y=24 if composer else 6,
    ))
    diff_color = {
        "beginner":     pygame.Color(52, 199, 89),
        "intermediate": pygame.Color(255, 149, 0),
        "advanced":     pygame.Color(255, 59, 48),
    }.get(diff, iOSTheme.secondary_label)
    card.add_child(Label(
        text=t(f"diff_{diff}"),
        font_size=11, color=diff_color,
        anchor="right", x=16, y=-30,
    ))
    body.add_child(card)

    # Hand selection
    body.add_child(Label(
        text=t("song_hand_label"),
        font_size=14, bold=True, color=iOSTheme.label,
        anchor="left", x=4, y=0,
    ))
    body.add_child(SegmentedControl(
        segments=[t("hand_right"), t("hand_left"), t("hand_both")],
        selected_index=_hand_state,
        on_change=lambda i: setattr(_hand_state, "value", i),
        anchor="center", x=0, y=0,
        width=1.0, height=36,
    ))

    # Explanation label (reactive)
    hand_desc_state = State(_hand_desc(0))

    def _on_hand(i):
        _hand_state.value = i
        hand_desc_state.value = _hand_desc(i)

    # Re-wire so description updates too alongside the state
    body.children[-1].on_change = _on_hand

    body.add_child(Label(
        text=hand_desc_state,
        font_size=13, color=iOSTheme.secondary_label,
        anchor="center", x=0, y=0,
        width=1.0, height=40,
    ))

    # Start buttons: practise note by note, or play along in tempo
    buttons = FloatLayout(width=1.0, height=52)
    buttons.add_child(Button(
        text=t("song_start"),
        on_click=_start,
        anchor="left", x=0, y=0,
        width=0.49, height=52, font_size=16,
        background_color=ColorPalette.BLUE,
        text_color=pygame.Color(255, 255, 255),
        border_radius=14,
    ))
    buttons.add_child(Button(
        text=t("song_play_along"),
        on_click=lambda: _start("performance"),
        anchor="right", x=0, y=0,
        width=0.49, height=52, font_size=16,
        background_color=iOSTheme.fill,
        text_color=iOSTheme.label,
        border_radius=14,
    ))
    body.add_child(buttons)

    main.add_child(body)
    return root


def _hand_desc(i: int) -> str:
    return t(["hand_right_desc", "hand_left_desc", "hand_both_desc"][i])
