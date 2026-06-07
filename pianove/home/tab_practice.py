import pygame
from pylay import FloatLayout, VStack, Label, Button, ColorPalette, iOSTheme, EmojiIcon
from pianove.i18n import t
from pianove.ui_utils import ui_dims
from pianove.state import storage
import pianove.context as ctx

_BLUE   = ColorPalette.BLUE
_GREEN  = pygame.Color(52, 199, 89)
_ORANGE = pygame.Color(255, 149, 0)
_PURPLE = pygame.Color(175, 82, 222)
_RED    = pygame.Color(255, 59, 48)

# ── Persistent config state (survive tab switches) ────────────────────────────
_CFG_KEY = "practice_config"

_CLEF_OPTIONS       = ["treble", "bass"]
_DIFFICULTY_OPTIONS = ["beginner", "intermediate", "advanced"]
_NOTE_OPTIONS       = [8, 16, 32, 64]
_BPM_OPTIONS        = [60, 80, 100, 120]
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


# ── Option row builder ────────────────────────────────────────────────────────

_ROW_H = 60   # label(18) + spacing(6) + buttons(36)

def _option_row(label: str, options: list, current, key: str, cfg: dict,
                fmt_fn=None) -> VStack:
    """A labeled row of pill buttons — one per option."""
    row = VStack(spacing=6, padding=0, width=1.0, height=_ROW_H)
    row.add_child(Label(text=label, font_size=13, bold=True,
                        color=iOSTheme.secondary_label, height=18))
    btns = FloatLayout(width=1.0, height=36)
    n = len(options)
    gap = 0.01
    w   = (1.0 - gap * (n + 1)) / n

    for i, opt in enumerate(options):
        selected = (opt == current)
        x_pos    = gap + i * (w + gap)
        label_str = fmt_fn(opt) if fmt_fn else str(opt)

        def _on_click(o=opt, k=key):
            cfg[k] = o
            _save_cfg(cfg)
            _reload()

        btns.add_child(Button(
            text=label_str,
            on_click=_on_click,
            anchor="top_left", x=x_pos, y=0,
            width=w, height=36, font_size=13,
            background_color=_BLUE if selected else iOSTheme.fill,
            text_color=pygame.Color(255, 255, 255) if selected else iOSTheme.label,
            border_radius=8,
        ))
    row.add_child(btns)
    return row


# ── Recent session card ───────────────────────────────────────────────────────

def _session_row(s: dict) -> FloatLayout:
    pct       = int(s.get("accuracy", 0) * 100)
    notes     = s.get("notes", 0)
    bpm       = s.get("bpm", 80)
    acc_color = _GREEN if pct >= 80 else (_ORANGE if pct >= 50 else _RED)

    row = FloatLayout(width=1.0, height=40,
                      background_color=iOSTheme.secondary_background,
                      border_radius=8)
    row.add_child(Label(text=f"{pct}%", font_size=15, bold=True, color=acc_color,
                        anchor="left", x=12, y=0, width=52, height=40))
    row.add_child(Label(
        text=f"{notes} {t('practice_notes')}  ·  {bpm} BPM",
        font_size=13, color=iOSTheme.secondary_label,
        anchor="left", x=68, y=0,
    ))
    # Mini accuracy bar
    bar_w  = 0.22
    filled = FloatLayout(anchor="right", x=12, y=0,
                         width=bar_w, height=8,
                         background_color=iOSTheme.fill, border_radius=4)
    fill_frac = s.get("accuracy", 0)
    if fill_frac > 0:
        fill = FloatLayout(anchor="left", x=0, y=0,
                           width=fill_frac, height=1.0,
                           background_color=acc_color, border_radius=4)
        filled.add_child(fill)
    row.add_child(filled)
    return row


# ── Tab builder ───────────────────────────────────────────────────────────────

def build():
    U   = ui_dims()
    cfg = _load_cfg()

    from pianove.progress import practice_sessions, practice_accuracy_avg

    sessions   = practice_sessions()
    recent     = sessions[-5:][::-1]   # last 5, newest first
    avg_acc    = practice_accuracy_avg()
    total_done = len(sessions)

    root   = FloatLayout(width=1.0, height=1.0, background_color=iOSTheme.background)
    scroll = VStack(spacing=14, padding=16, width=1.0, height=1.0)
    root.add_child(scroll)

    # ── Header ────────────────────────────────────────────────────────────────
    header_row = FloatLayout(width=1.0, height=40)
    header_row.add_child(Label(
        text=t("practice_tab_title"),
        font_size=U["title_size"] - 6, bold=True,
        color=iOSTheme.label, anchor="left", x=0, y=0,
    ))
    if total_done > 0:
        badge = FloatLayout(
            anchor="right", x=0, y=0, width=110, height=34,
            background_color=_PURPLE, border_radius=17,
        )
        badge.add_child(Label(
            text=f"{total_done} {t('practice_sessions_badge')}",
            font_size=12, bold=True,
            color=pygame.Color(255, 255, 255),
            anchor="center", x=0, y=0,
        ))
        header_row.add_child(badge)
    scroll.add_child(header_row)

    scroll.add_child(Label(
        text=t("practice_tab_subtitle"),
        font_size=13, color=iOSTheme.secondary_label,
        wrap_width=700, height=18,
    ))

    # title(20) + 5 rows(60) + button(44) + 6 gaps(12) + 2×padding(14) = 468
    _CARD_H = 20 + 5 * _ROW_H + 44 + 6 * 12 + 2 * 14

    # ── Config card ───────────────────────────────────────────────────────────
    config_card = VStack(spacing=12, padding=14, width=1.0, height=_CARD_H,
                         background_color=iOSTheme.secondary_background,
                         border_radius=12)

    config_card.add_child(Label(
        text=t("practice_config_title"),
        font_size=14, bold=True, color=iOSTheme.label, height=20,
    ))

    config_card.add_child(_option_row(
        t("practice_clef"), _CLEF_OPTIONS, cfg["clef"], "clef", cfg,
        fmt_fn=lambda v: t(f"practice_clef_{v}"),
    ))
    config_card.add_child(_option_row(
        t("practice_difficulty"), _DIFFICULTY_OPTIONS, cfg["difficulty"], "difficulty", cfg,
        fmt_fn=lambda v: t(f"diff_{v}"),
    ))
    config_card.add_child(_option_row(
        t("practice_notes_label"), _NOTE_OPTIONS, cfg["notes"], "notes", cfg,
        fmt_fn=lambda v: str(v),
    ))
    config_card.add_child(_option_row(
        t("practice_bpm_label"), _BPM_OPTIONS, cfg["bpm"], "bpm", cfg,
        fmt_fn=lambda v: str(v),
    ))
    config_card.add_child(_option_row(
        t("practice_key_label"), _KEY_OPTIONS, cfg["key"], "key", cfg,
        fmt_fn=lambda v: str(v),
    ))

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
        background_color=_PURPLE,
        text_color=pygame.Color(255, 255, 255),
        border_radius=12,
    ))
    scroll.add_child(config_card)

    # ── Recent sessions ───────────────────────────────────────────────────────
    if recent:
        scroll.add_child(Label(
            text=t("practice_recent"),
            font_size=U["subtitle_size"], bold=True,
            color=iOSTheme.label,
        ))
        if total_done > 0:
            avg_pct   = int(avg_acc * 100)
            avg_color = _GREEN if avg_pct >= 80 else (_ORANGE if avg_pct >= 50 else _RED)
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
