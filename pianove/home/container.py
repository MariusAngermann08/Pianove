import math
import pygame
from pylay import FloatLayout, State, SideNav, PageRouter, iOSTheme
from pylay.core.scale import UI_SCALE
from pianove.i18n import t
from pianove.state import midi_device_state, creator_mode_state
from pianove.home import tab_home, tab_songs, tab_lessons, tab_stats, tab_settings, tab_creator
import pianove.context as ctx

_active_tab = State(0)
_NAV_W      = 200   # base sidebar width (pixels at 1× scale)


# ── Vector icons ──────────────────────────────────────────────────────────────

def _icon_home(surf, cx, cy, scale, color):
    s  = int(7 * scale)
    pygame.draw.polygon(surf, color, [(cx, cy - s), (cx - s, cy + 1), (cx + s, cy + 1)])
    dw = max(2, s // 2)
    pygame.draw.rect(surf, color, (cx - dw // 2, cy + 1, dw, s - 2))


def _icon_songs(surf, cx, cy, scale, color):
    r  = int(4 * scale)
    sw = max(1, int(2 * scale))
    pygame.draw.circle(surf, color, (cx - 2, cy + r), r)
    pygame.draw.line(surf, color, (cx + r - 2, cy + r), (cx + r - 2, cy - r - 1), sw)
    pygame.draw.line(surf, color, (cx + r - 2, cy - r - 1), (cx + r + 4, cy), sw)


def _icon_lessons(surf, cx, cy, scale, color):
    s  = int(7 * scale)
    sw = max(1, int(2 * scale))
    pygame.draw.rect(surf, color, pygame.Rect(cx - s, cy - s // 2, s - 1, s), sw)
    pygame.draw.rect(surf, color, pygame.Rect(cx + 1, cy - s // 2, s - 1, s), sw)
    pygame.draw.line(surf, color, (cx, cy - s // 2), (cx, cy + s // 2), sw)


def _icon_stats(surf, cx, cy, scale, color):
    s   = int(7 * scale)
    bw  = max(3, int(4 * scale))
    base = cy + s // 2
    for i, h in enumerate([s // 2, s, int(s * 0.7)]):
        x = cx - s + i * (bw + 3)
        pygame.draw.rect(surf, color, (x, base - h, bw, h))


def _icon_gear(surf, cx, cy, scale, color):
    r_out = int(7 * scale)
    r_in  = int(4 * scale)
    sw    = max(1, int(2 * scale))
    pygame.draw.circle(surf, color, (cx, cy), r_out, sw)
    pygame.draw.circle(surf, color, (cx, cy), r_in,  sw)
    for i in range(4):
        a  = i * math.pi / 2
        tx = cx + int(r_out * math.cos(a))
        ty = cy + int(r_out * math.sin(a))
        pygame.draw.rect(surf, color, (tx - sw, ty - sw, sw * 2, sw * 2))


_ICONS = [_icon_home, _icon_songs, _icon_lessons, _icon_stats, _icon_gear]


# ── Builder ───────────────────────────────────────────────────────────────────

def _icon_creator(surf, cx, cy, scale, color):
    s  = int(7 * scale)
    sw = max(1, int(2 * scale))
    # Pencil icon
    tip_x, tip_y = cx - s + 2, cy + s - 2
    pygame.draw.line(surf, color, (cx + s - 2, cy - s + 2), (tip_x, tip_y), sw)
    pygame.draw.line(surf, color, (cx + s - 2, cy - s + 2), (cx + s + 2, cy - s - 2), sw)
    pygame.draw.line(surf, color, (cx + s + 2, cy - s - 2), (tip_x + 4, tip_y - 4), sw)
    pygame.draw.line(surf, color, (tip_x, tip_y), (tip_x - 2, tip_y + 2), sw)


def build():
    nav_w        = max(160, int(_NAV_W * UI_SCALE))
    content_w    = max(200, ctx.ui.width - nav_w)
    show_creator = bool(creator_mode_state.value)

    tab_keys = ["home", "songs", "lessons", "stats", "settings"]
    icons    = list(_ICONS)
    pages    = {
        "home":     tab_home.build,
        "songs":    tab_songs.build,
        "lessons":  tab_lessons.build,
        "stats":    tab_stats.build,
        "settings": tab_settings.build,
    }

    if show_creator:
        tab_keys.append("creator")
        icons.append(_icon_creator)
        pages["creator"] = tab_creator.build

    # Clamp active tab index within current tab count
    active_idx = min(int(_active_tab.value), len(tab_keys) - 1)

    root = FloatLayout(width=1.0, height=1.0, background_color=iOSTheme.background)

    # ── Tab content router (right panel) ──────────────────────────────────
    tab_router = PageRouter(
        pages=pages,
        initial_page=tab_keys[active_idx],
        anchor="top_left",
        x=nav_w,
        y=0,
        width=content_w,
        height=1.0,
    )
    ctx.inner_router = tab_router
    root.add_child(tab_router)

    # ── Side navigation (left panel) ──────────────────────────────────────
    nav_items = [
        {"title": t(f"nav_{k}"), "icon_fn": fn}
        for k, fn in zip(tab_keys, icons)
    ]
    side_nav = SideNav(
        active_tab_state=_active_tab,
        items=nav_items,
        on_change=lambda idx: tab_router.navigate(tab_keys[idx]),
        width=nav_w,
        title="Pianove",
        footer_fn=lambda: midi_device_state.value,
    )
    root.add_child(side_nav)

    return root
