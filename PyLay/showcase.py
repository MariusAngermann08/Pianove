"""
PyLay 0.1.0 — Component Showcase  (800 × 600)

Anchor guide for PyLay (substring match on "center" takes priority):
  "top_left"   — element top-left at parent top-left + offset
  "top_right"  — element top-right at parent top-right + offset
  "left"       — element left-edge at parent left + offset, Y centred in parent
  "right"      — element right-edge at parent right + offset, Y centred in parent
  "bottom"     — element bottom, X centred in parent
  "center"     — element centred in parent
  !! "center_left" == "center" — "center" substring match overrides everything !!
"""

import pygame
import pylay as pl
from pylay.core.theme import iOSTheme, ColorPalette

_NAV_H    = 56   # bottom navigation bar height (px)
_TOPBAR_H = 48   # top safe-area height (px) — clears the hamburger button

# Set by __main__ so page builders can call app.apply_theme()
_app = None

# ---------------------------------------------------------------------------
# Shared reactive state
# ---------------------------------------------------------------------------
dark_mode_st  = pl.State(False)
active_tab_st = pl.State(0)
drawer_open   = pl.State(False)

toggle_a   = pl.State(True)
toggle_b   = pl.State(False)
check_a    = pl.State(True)
check_b    = pl.State(False)
check_c    = pl.State(False)
radio_val  = pl.State(0)
seg_val    = pl.State(0)
text_val   = pl.State("")
option_val = pl.State("spring")
counter    = pl.State(0)


# ---------------------------------------------------------------------------
# Layout helpers
# ---------------------------------------------------------------------------

def _page(title: str) -> pl.VStack:
    """VStack whose first child is a transparent header that clears the hamburger."""
    page = pl.VStack(spacing=14, padding=16,
                     anchor="top_left", x=0, y=0, width=1.0, height=1.0)
    hdr = pl.FloatLayout(
        anchor="top_left", x=0, y=0, width=1.0, height=_TOPBAR_H,
        background_color=pygame.Color(0, 0, 0, 0), border_radius=0,
    )
    # anchor="left" → left-aligned, vertically centred in hdr — x=52 clears the 40px hamburger
    hdr.add_child(pl.Label(title, font_size=20, bold=True, anchor="left", x=52, y=0))
    page.add_child(hdr)
    return page


def _section(text: str) -> pl.FloatLayout:
    """Full-width row containing a left-aligned section header label."""
    row = pl.FloatLayout(
        anchor="top_left", x=0, y=0, width=1.0, height=18,
        background_color=pygame.Color(0, 0, 0, 0), border_radius=0,
    )
    row.add_child(pl.Label(text, font_size=10, bold=True,
                            color=iOSTheme.secondary_label,
                            anchor="left", x=0, y=0))
    return row


def _row(height: int = 40) -> pl.FloatLayout:
    """Transparent row — add children with anchor="left" or anchor="right"."""
    return pl.FloatLayout(
        anchor="top_left", x=0, y=0, width=1.0, height=height,
        background_color=pygame.Color(0, 0, 0, 0), border_radius=0,
    )


def _nav_spacer() -> pl.FloatLayout:
    """Transparent gap so last item is not hidden behind the bottom nav."""
    return pl.FloatLayout(
        anchor="top_left", x=0, y=0, width=1.0, height=_NAV_H,
        background_color=pygame.Color(0, 0, 0, 0), border_radius=0,
    )


# ---------------------------------------------------------------------------
# Tab icons
# ---------------------------------------------------------------------------

def _icon_controls(surf, cx, cy, scale, color):
    r = int(pl.scaled_px(5) * scale)
    pygame.draw.rect(surf, color, (cx - r, cy - r, r * 2, r * 2), border_radius=2)

def _icon_inputs(surf, cx, cy, scale, color):
    r = int(pl.scaled_px(5) * scale)
    pygame.draw.circle(surf, color, (cx, cy), r, max(1, int(2 * scale)))
    pygame.draw.circle(surf, color, (cx, cy), max(2, r // 2))

def _icon_data(surf, cx, cy, scale, color):
    r = int(pl.scaled_px(5) * scale)
    pygame.draw.polygon(surf, color,
                         [(cx, cy - r), (cx + r, cy + r), (cx - r, cy + r)])

def _icon_about(surf, cx, cy, scale, color):
    r = int(pl.scaled_px(5) * scale)
    pygame.draw.circle(surf, color, (cx, cy), r)
    pygame.draw.circle(surf, iOSTheme.background, (cx, cy),
                        max(2, r - int(2 * scale)))


# ---------------------------------------------------------------------------
# Page: Controls
# ---------------------------------------------------------------------------

def build_controls_page():
    page = _page("Controls")

    # Dark mode toggle
    page.add_child(_section("APPEARANCE"))
    row = _row(38)
    # anchor="left"  → left edge at row.left + x=0, vertically centred in row
    # anchor="right" → right edge at row.right + x=0, vertically centred in row
    row.add_child(pl.Label("Dark Mode", font_size=14, anchor="left", x=0, y=0))
    row.add_child(pl.Switch(
        value=dark_mode_st,
        on_change=lambda v: _app.apply_theme(dark=bool(v)) if _app else None,
        anchor="right", x=0, y=0,
    ))
    page.add_child(row)

    # Segmented control
    page.add_child(_section("SEGMENT"))
    page.add_child(pl.SegmentedControl(
        segments=["Filled", "Outline", "Ghost"],
        selected_index=seg_val,
        width=0.95, height=34,
    ))

    # Buttons
    page.add_child(_section("BUTTONS"))
    page.add_child(pl.Button(
        "Primary Action",
        on_click=lambda: setattr(counter, "value", counter.value + 1),
        width=0.95, height=44,
        background_color=ColorPalette.BLUE,
    ))
    page.add_child(pl.Button(
        "Success", on_click=lambda: None,
        width=0.95, height=40,
        background_color=ColorPalette.GREEN,
    ))
    page.add_child(pl.Button(
        "Destructive", on_click=lambda: None,
        width=0.95, height=40,
        background_color=ColorPalette.RED,
    ))

    # Tap counter — Label accepts a State object and converts it to str automatically
    crow = _row(38)
    crow.add_child(pl.Label("Taps:", font_size=14, anchor="left", x=0, y=0))
    crow.add_child(pl.Label(counter, font_size=22, bold=True,
                             color=ColorPalette.BLUE, anchor="right", x=0, y=0))
    page.add_child(crow)

    # Text field
    page.add_child(_section("TEXT INPUT"))
    page.add_child(pl.TextField(
        text=text_val, placeholder="Type something…",
        width=0.95, height=40,
    ))
    page.add_child(pl.Label(text_val, font_size=12, color=iOSTheme.secondary_label))

    page.add_child(_nav_spacer())
    return page


# ---------------------------------------------------------------------------
# Page: Inputs
# ---------------------------------------------------------------------------

def build_inputs_page():
    page = _page("Inputs")

    # Three slider → progress pairs, each with their own independent state
    page.add_child(_section("SLIDER  →  PROGRESS"))
    for color, init in [
        (ColorPalette.BLUE,   0.5),
        (ColorPalette.GREEN,  0.65),
        (ColorPalette.ORANGE, 0.3),
    ]:
        sv = pl.State(init)
        pv = pl.State(init)
        sv.bind(lambda v, _p=pv: setattr(_p, "value", max(0.0, min(1.0, v))))
        page.add_child(pl.Slider(value=sv, min_val=0.0, max_val=1.0,
                                  width=0.95, height=26, active_color=color))
        page.add_child(pl.ProgressBar(progress=pv, width=0.95, height=6,
                                       active_color=color))

    # Switches — label at left, switch at right, both vertically centred in row
    page.add_child(_section("SWITCHES"))
    for label, state, color in [
        ("Notifications",   toggle_a, ColorPalette.BLUE),
        ("Background Sync", toggle_b, ColorPalette.GREEN),
    ]:
        row = _row(38)
        row.add_child(pl.Label(label, font_size=14, anchor="left", x=0, y=0))
        row.add_child(pl.Switch(value=state, active_color=color,
                                 anchor="right", x=0, y=0))
        page.add_child(row)

    # Checkboxes — checkbox at x=0 left, label offset to x=30 left
    page.add_child(_section("CHECKBOXES"))
    for label, state in [
        ("Accept terms and conditions", check_a),
        ("Subscribe to newsletter",     check_b),
        ("Enable analytics",            check_c),
    ]:
        row = _row(34)
        row.add_child(pl.Checkbox(value=state, size=22, anchor="left", x=0, y=0))
        row.add_child(pl.Label(label, font_size=13, anchor="left", x=30, y=0))
        page.add_child(row)

    # Radio group
    page.add_child(_section("RADIO GROUP"))
    for i, label in enumerate(["Option Alpha", "Option Beta", "Option Gamma"]):
        row = _row(34)
        row.add_child(pl.RadioButton(group_state=radio_val, choice_value=i,
                                      size=22, anchor="left", x=0, y=0))
        row.add_child(pl.Label(label, font_size=13, anchor="left", x=30, y=0))
        page.add_child(row)

    page.add_child(_nav_spacer())
    return page


# ---------------------------------------------------------------------------
# Page: Data
# ---------------------------------------------------------------------------

def build_data_page():
    page = _page("Data")

    page.add_child(_section("ACTIVITY — 7 DAYS"))
    page.add_child(pl.LineChart(
        data=[12, 28, 19, 45, 38, 52, 41],
        labels=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        width=0.95, height=140,
        active_color=ColorPalette.BLUE,
    ))

    page.add_child(_section("REVENUE — 6 MONTHS"))
    page.add_child(pl.LineChart(
        data=[8400, 11200, 9800, 14600, 13100, 17800],
        labels=["Jan", "Feb", "Mar", "Apr", "May", "Jun"],
        width=0.95, height=140,
        active_color=ColorPalette.GREEN,
    ))

    page.add_child(_section("ANIMATION PRESET"))
    page.add_child(pl.OptionSelector(
        options=[
            ("Spring Physics", "spring"),
            ("Ease In-Out",    "ease"),
            ("Linear",         "linear"),
            ("Bouncy",         "bouncy"),
        ],
        value=option_val,
        width=0.95, row_height=42, spacing=6,
    ))

    page.add_child(_nav_spacer())
    return page


# ---------------------------------------------------------------------------
# Page: About
# ---------------------------------------------------------------------------

def build_about_page():
    page = _page("About")

    page.add_child(pl.Label("PyLay  v0.1.0", font_size=26, bold=True,
                             color=ColorPalette.BLUE))
    page.add_child(pl.Label(
        "An iOS-inspired UI library for pygame with spring physics and reactive state.",
        font_size=12, color=iOSTheme.secondary_label, wrap_width=340,
    ))

    # Feature card — content laid out by a VStack so nothing overlaps
    card = pl.FloatLayout(
        anchor="top_left", x=0, y=0, width=0.95, height=198,
        background_color=iOSTheme.secondary_background,
        border_radius=14, shadow_depth=8,
    )
    feats = pl.VStack(spacing=6, padding=16,
                       anchor="top_left", x=0, y=0, width=1.0, height=1.0)
    feats.add_child(pl.Label("What's inside", font_size=14, bold=True))
    for line in [
        "Spring physics — UIKit-identical math",
        "Inter font — open-source SF Pro substitute",
        "AA rounded rects via 2x supersampling",
        "Fake drop shadows — zero GPU blur cost",
        "Reactive State — automatic widget updates",
        "Idle frame skip — 0 CPU when nothing moves",
    ]:
        feats.add_child(pl.Label("● " + line, font_size=11,
                                  color=iOSTheme.secondary_label))
    card.add_child(feats)
    page.add_child(card)

    # Spring formula card — also uses VStack internally
    page.add_child(_section("SPRING FORMULA"))
    demo = pl.FloatLayout(
        anchor="top_left", x=0, y=0, width=0.95, height=72,
        background_color=iOSTheme.secondary_background,
        border_radius=12, shadow_depth=6,
    )
    demo_inner = pl.VStack(spacing=6, padding=14,
                            anchor="top_left", x=0, y=0, width=1.0, height=1.0)
    demo_inner.add_child(pl.Label("response=0.35   damping=0.8",
                                   font_size=12, bold=True))
    demo_inner.add_child(pl.Label(
        "Same formula as SwiftUI .spring(response:dampingFraction:)",
        font_size=10, color=iOSTheme.secondary_label, wrap_width=300,
    ))
    demo.add_child(demo_inner)
    page.add_child(demo)

    page.add_child(_nav_spacer())
    return page


# ---------------------------------------------------------------------------
# Root layout
# ---------------------------------------------------------------------------

def build_root() -> pl.FloatLayout:
    root = pl.FloatLayout(
        anchor="top_left", x=0, y=0, width=1.0, height=1.0,
        background_color=iOSTheme.background, border_radius=0,
    )

    _page_names = ["controls", "inputs", "data", "about"]

    router = pl.PageRouter(
        pages={name: fn for name, fn in zip(
            _page_names,
            [build_controls_page, build_inputs_page,
             build_data_page, build_about_page],
        )},
        initial_page="controls",
        anchor="top_left", x=0, y=0, width=1.0, height=1.0,
    )

    def _on_tab(idx):
        name = _page_names[int(idx)]
        if name != router.active_page_name:
            router.navigate(name)

    active_tab_st.bind(_on_tab)   # fires immediately; guard prevents double-navigate

    nav = pl.BottomNavigationBar(
        active_tab_state=active_tab_st,
        items=[
            {"title": "Controls", "icon_fn": _icon_controls},
            {"title": "Inputs",   "icon_fn": _icon_inputs},
            {"title": "Data",     "icon_fn": _icon_data},
            {"title": "About",    "icon_fn": _icon_about},
        ],
        height=_NAV_H,
    )

    hamburger = pl.HamburgerButton(
        open_state=drawer_open,
        anchor="top_left", x=10, y=6, width=38, height=38,
    )

    drawer = pl.SidebarDrawer(
        open_state=drawer_open,
        width=240,
        active_tab_state=active_tab_st,
        tabs=["Controls", "Inputs", "Data", "About"],
    )

    root.add_child(router)
    root.add_child(nav)
    root.add_child(hamburger)
    root.add_child(drawer)
    return root


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    pl.set_window_size(800, 600)
    app = pl.App(title="PyLay Showcase", width=800, height=600, dark_mode=False)
    import showcase as _self; _self._app = app
    app.root = build_root()
    app.root.layout(app.screen.get_rect())
    app.run()
