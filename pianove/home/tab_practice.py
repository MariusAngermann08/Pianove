import pygame
from pylay import (
    FloatLayout, VStack, Card, Label, Button, Badge,
    SegmentedControl, Stepper,
    ColorPalette, iOSTheme,
)
from pylay.core.scale import scaled_px
from pianove.i18n import t
from pianove.ui_utils import ui_dims
from pianove.state import storage
from pianove.components import ORANGE, GREEN, RED, PURPLE
import pianove.context as ctx

_BLUE = ColorPalette.BLUE

_CFG_KEY = "practice_config"

_CLEF_OPTIONS       = ["treble", "bass"]
_DIFFICULTY_OPTIONS = ["beginner", "intermediate", "advanced"]
_NOTE_OPTIONS       = [8, 16, 32, 64]
_BPM_OPTIONS        = [40, 50, 60, 70, 80, 90, 100, 110, 120, 140, 160, 180, 200]
_KEY_OPTIONS        = ["C", "G", "D", "F"]

_DEFAULTS = {
    "clef":       "treble",
    "difficulty": "intermediate",
    "notes":      16,
    "bpm":        80,
    "key":        "C",
}


def _load_cfg() -> dict:
    saved = storage.get(_CFG_KEY, {})
    cfg = dict(_DEFAULTS)
    cfg.update({k: v for k, v in saved.items() if k in _DEFAULTS})
    return cfg


def _save_cfg(cfg: dict):
    storage.set(_CFG_KEY, cfg)


def _reload():
    if ctx.inner_router:
        ctx.inner_router.reload_current_page()


def _section_label(text: str):
    return Label(
        text=text, font_size=12, bold=True,
        color=iOSTheme.secondary_label, height=16,
    )


def _key_pill_row(cfg: dict) -> FloatLayout:
    row = FloatLayout(width=1.0, height=36)
    n   = len(_KEY_OPTIONS)
    gap = 0.012
    w   = (1.0 - gap * (n + 1)) / n
    for i, key in enumerate(_KEY_OPTIONS):
        selected = key == cfg["key"]
        x_pos    = gap + i * (w + gap)

        def _on_click(k=key):
            cfg["key"] = k
            _save_cfg(cfg)
            _reload()

        row.add_child(Button(
            text=key,
            on_click=_on_click,
            anchor="top_left", x=x_pos, y=0,
            width=w, height=36, font_size=14,
            background_color=_BLUE if selected else iOSTheme.fill,
            text_color=pygame.Color(255, 255, 255) if selected else iOSTheme.label,
            border_radius=8,
        ))
    return row


def _inline_row(label_text: str, widget, row_h: int = 44) -> FloatLayout:
    row = FloatLayout(width=1.0, height=row_h)
    row.add_child(Label(
        text=label_text, font_size=14, bold=True,
        color=iOSTheme.label,
        anchor="left", x=0, y=0,
    ))
    row.add_child(widget)
    return row


def _session_row(s: dict) -> FloatLayout:
    pct       = int(s.get("accuracy", 0) * 100)
    notes     = s.get("notes", 0)
    bpm       = s.get("bpm", 80)
    acc_color = GREEN if pct >= 80 else (ORANGE if pct >= 50 else RED)

    row = FloatLayout(
        width=1.0, height=40,
        background_color=iOSTheme.secondary_background,
        border_radius=8,
    )
    row.add_child(Label(
        text=f"{pct}%", font_size=15, bold=True, color=acc_color,
        anchor="left", x=12, y=0, width=52, height=40,
    ))
    row.add_child(Label(
        text=f"{notes} {t('practice_notes')}  ·  {bpm} BPM",
        font_size=13, color=iOSTheme.secondary_label,
        anchor="left", x=68, y=0,
    ))
    bar_w  = 0.22
    filled = FloatLayout(
        anchor="right", x=12, y=0,
        width=bar_w, height=8,
        background_color=iOSTheme.fill, border_radius=4,
    )
    fill_frac = s.get("accuracy", 0)
    if fill_frac > 0:
        filled.add_child(FloatLayout(
            anchor="left", x=0, y=0,
            width=fill_frac, height=1.0,
            background_color=acc_color, border_radius=4,
        ))
    row.add_child(filled)
    return row


def build():
    U   = ui_dims()
    cfg = _load_cfg()

    from pianove.progress import practice_sessions, practice_accuracy_avg

    sessions   = practice_sessions()
    recent     = sessions[-5:][::-1]
    avg_acc    = practice_accuracy_avg()
    total_done = len(sessions)

    root   = FloatLayout(width=1.0, height=1.0, background_color=iOSTheme.background)
    scroll = VStack(spacing=14, padding=16, width=1.0, height=1.0)
    root.add_child(scroll)

    header_row = FloatLayout(width=1.0, height=40)
    header_row.add_child(Label(
        text=t("practice_tab_title"),
        font_size=U["title_size"] - 6, bold=True,
        color=iOSTheme.label, anchor="left", x=0, y=0,
    ))
    if total_done > 0:
        header_row.add_child(Badge(
            text=f"{total_done} {t('practice_sessions_badge')}",
            color=PURPLE,
            font_size=12, height=34, width=110,
            anchor="right", x=0, y=0,
        ))
    scroll.add_child(header_row)
    scroll.add_child(Label(
        text=t("practice_tab_subtitle"),
        font_size=13, color=iOSTheme.secondary_label,
        wrap_width=700, height=18,
    ))

    # Heights: title=20, section_label=16, control=36, inline_row=44
    # Rows: 2×(16+6+36) + (16+6+36) + 2×44 + button=44
    # Spacing between children: 8px × 8 gaps
    # Padding: 14×2
    _CARD_H = (20          # card title
               + 3*(16+8+36)  # 3 label+control blocks (clef, diff, key)
               + 2*44         # 2 inline rows (notes, bpm)
               + 44           # start button
               + 7*10         # 8 spacing gaps
               + 2*14)        # top+bottom padding

    config_card = Card(spacing=10, padding=14, width=1.0, height=_CARD_H)

    config_card.add_child(Label(
        text=t("practice_config_title"),
        font_size=14, bold=True, color=iOSTheme.label, height=20,
    ))

    # Clef — SegmentedControl (binary, full-width)
    clef_idx   = _CLEF_OPTIONS.index(cfg["clef"]) if cfg["clef"] in _CLEF_OPTIONS else 0
    config_card.add_child(_section_label(t("practice_clef")))
    config_card.add_child(SegmentedControl(
        segments=[t("practice_clef_treble"), t("practice_clef_bass")],
        selected_index=clef_idx,
        on_change=lambda i: (cfg.update({"clef": _CLEF_OPTIONS[i]}), _save_cfg(cfg)),
        width=1.0, height=36,
    ))

    # Difficulty — SegmentedControl (3 categorical options)
    diff_idx   = _DIFFICULTY_OPTIONS.index(cfg["difficulty"]) if cfg["difficulty"] in _DIFFICULTY_OPTIONS else 1
    config_card.add_child(_section_label(t("practice_difficulty")))
    config_card.add_child(SegmentedControl(
        segments=[t("diff_beginner"), t("diff_intermediate"), t("diff_advanced")],
        selected_index=diff_idx,
        on_change=lambda i: (cfg.update({"difficulty": _DIFFICULTY_OPTIONS[i]}), _save_cfg(cfg)),
        width=1.0, height=36,
    ))

    # Key — compact pill row (4 single-char labels, pills are right here)
    config_card.add_child(_section_label(t("practice_key_label")))
    config_card.add_child(_key_pill_row(cfg))

    # Notes — Stepper (discrete list: 8 / 16 / 32 / 64)
    notes_stepper = Stepper(
        options=_NOTE_OPTIONS,
        value=cfg["notes"],
        label_suffix=f" {t('practice_notes')}",
        active_color=PURPLE,
        anchor="right", x=0, y=0,
        width=0.45, height=36,
        on_change=lambda v: (cfg.update({"notes": v}), _save_cfg(cfg)),
    )
    config_card.add_child(_inline_row(t("practice_notes_label"), notes_stepper, row_h=44))

    # BPM — Stepper (more granular options than before)
    bpm_stepper = Stepper(
        options=_BPM_OPTIONS,
        value=cfg["bpm"],
        label_suffix=" BPM",
        active_color=PURPLE,
        anchor="right", x=0, y=0,
        width=0.45, height=36,
        on_change=lambda v: (cfg.update({"bpm": v}), _save_cfg(cfg)),
    )
    config_card.add_child(_inline_row(t("practice_bpm_label"), bpm_stepper, row_h=44))

    # Start button
    def _start():
        from pianove.note_generator import generate_bars
        bars = generate_bars(cfg["clef"], cfg["difficulty"], cfg["key"], cfg["notes"])
        ctx.practice_mode        = True
        ctx.practice_bars        = bars
        ctx.practice_bpm         = cfg["bpm"]
        ctx.practice_clef        = cfg["clef"]
        ctx.practice_last_hits   = 0
        ctx.practice_last_total  = 0
        ctx.current_lesson_id    = "__practice__"
        ctx.current_song_id      = None
        ctx.current_course_id    = None
        ctx.lesson_phase         = "performance"
        ctx.lesson_section_idx   = 0
        ctx.lesson_current_idx   = 0
        ctx.lesson_completed     = False
        ctx.router.navigate("lesson", "right")

    config_card.add_child(Button(
        text=t("practice_start"),
        on_click=_start,
        width=1.0, height=44, font_size=15,
        background_color=PURPLE,
        text_color=pygame.Color(255, 255, 255),
        border_radius=12,
    ))
    scroll.add_child(config_card)

    if recent:
        scroll.add_child(Label(
            text=t("practice_recent"),
            font_size=U["subtitle_size"], bold=True,
            color=iOSTheme.label,
        ))
        if total_done > 0:
            avg_pct   = int(avg_acc * 100)
            avg_color = GREEN if avg_pct >= 80 else (ORANGE if avg_pct >= 50 else RED)
            avg_row   = FloatLayout(width=1.0, height=36)
            avg_row.add_child(Label(
                text=t("practice_avg_accuracy"),
                font_size=13, color=iOSTheme.secondary_label,
                anchor="left", x=0, y=0,
            ))
            avg_row.add_child(Label(
                text=f"{avg_pct}%",
                font_size=15, bold=True, color=avg_color,
                anchor="right", x=0, y=0, width=60, height=36,
            ))
            scroll.add_child(avg_row)

        _stack_h = len(recent) * 40 + max(0, len(recent) - 1) * 6
        sessions_stack = VStack(spacing=6, padding=0, width=1.0, height=_stack_h)
        for s in recent:
            sessions_stack.add_child(_session_row(s))
        scroll.add_child(sessions_stack)

    return root
