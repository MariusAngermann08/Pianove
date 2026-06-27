import pygame
import pylay as pl
from pylay.core.theme import iOSTheme, ColorPalette

_NAV_H    = 56
_TOPBAR_H = 48

dark_st      = pl.State(True)
tab_st       = pl.State(0)
drawer_open  = pl.State(False)

sw_notif     = pl.State(True)
sw_sync      = pl.State(False)
sw_analytics = pl.State(True)
check_a      = pl.State(True)
check_b      = pl.State(False)
radio_val    = pl.State(0)
seg_val      = pl.State(0)
text_val     = pl.State("")
counter      = pl.State(0)
reveal_vis   = pl.State(True)
picked_file  = pl.State("No file selected")


def _page(title):
    page = pl.VStack(spacing=12, padding=16,
                     anchor="top_left", x=0, y=0, width=1.0, height=1.0)
    hdr = pl.FloatLayout(anchor="top_left", x=0, y=0, width=1.0, height=_TOPBAR_H,
                         background_color=pygame.Color(0, 0, 0, 0), border_radius=0)
    hdr.add_child(pl.Label(title, font_size=20, bold=True, anchor="left", x=52, y=0))
    page.add_child(hdr)
    return page


def _section(text):
    row = pl.FloatLayout(anchor="top_left", x=0, y=0, width=1.0, height=18,
                         background_color=pygame.Color(0, 0, 0, 0), border_radius=0)
    row.add_child(pl.Label(text, font_size=10, bold=True,
                           color=iOSTheme.secondary_label, anchor="left", x=0, y=0))
    return row


def _row(h=40):
    return pl.FloatLayout(anchor="top_left", x=0, y=0, width=1.0, height=h,
                          background_color=pygame.Color(0, 0, 0, 0), border_radius=0)


def _spacer():
    return pl.FloatLayout(anchor="top_left", x=0, y=0, width=1.0, height=_NAV_H,
                          background_color=pygame.Color(0, 0, 0, 0), border_radius=0)


def build_controls_page():
    page = _page("Controls")

    page.add_child(_section("APPEARANCE"))
    r = _row(38)
    r.add_child(pl.Label("Dark Mode", font_size=14, anchor="left", x=0, y=0))
    # Switch toggles dark_st; __main__ binds dark_st → app.apply_theme
    r.add_child(pl.Switch(value=dark_st, anchor="right", x=0, y=0))
    page.add_child(r)

    page.add_child(_section("SEGMENT"))
    page.add_child(pl.SegmentedControl(
        segments=["Rounded", "Sharp", "Ghost"],
        selected_index=seg_val,
        width=0.95, height=34,
    ))

    page.add_child(_section("BUTTONS"))
    page.add_child(pl.Button(
        "Primary  +1",
        on_click=lambda: setattr(counter, "value", counter.value + 1),
        width=0.95, height=44,
        background_color=ColorPalette.BLUE,
    ))
    pair = _row(40)
    pair.add_child(pl.Button("Success", on_click=lambda: None,
                             width=0.455, height=40,
                             background_color=ColorPalette.GREEN,
                             anchor="left", x=0, y=0))
    pair.add_child(pl.Button("Danger", on_click=lambda: None,
                             width=0.455, height=40,
                             background_color=ColorPalette.RED,
                             anchor="right", x=0, y=0))
    page.add_child(pair)

    cnt = _row(38)
    cnt.add_child(pl.Label("Tap count:", font_size=14, anchor="left", x=0, y=0))
    cnt.add_child(pl.Label(counter, font_size=22, bold=True,
                           color=ColorPalette.BLUE, anchor="right", x=0, y=0))
    page.add_child(cnt)

    page.add_child(_section("STEPPER"))
    step_row = _row(40)
    step_row.add_child(pl.Label("Font size:", font_size=14, anchor="left", x=0, y=0))
    step_row.add_child(pl.Stepper(
        options=["XS", "S", "M", "L", "XL", "2XL"],
        value="M",
        active_color=ColorPalette.BLUE,
        width=160, height=36,
        anchor="right", x=0, y=0,
    ))
    page.add_child(step_row)

    page.add_child(_section("BADGES"))
    badge_row = _row(34)
    for i, (lbl, col) in enumerate([
        ("New",    ColorPalette.BLUE),
        ("Pro",    ColorPalette.PURPLE),
        ("Beta",   ColorPalette.ORANGE),
        ("Live",   ColorPalette.GREEN),
        ("Danger", ColorPalette.RED),
    ]):
        badge_row.add_child(pl.Badge(lbl, col, anchor="left", x=i * 62, y=0))
    page.add_child(badge_row)

    page.add_child(_spacer())
    return page


def build_forms_page():
    page = _page("Forms")

    page.add_child(_section("TEXT INPUT"))
    page.add_child(pl.TextField(
        text=text_val, placeholder="Type something…",
        width=0.95, height=40,
    ))
    page.add_child(pl.Label(text_val, font_size=12, color=iOSTheme.secondary_label))

    page.add_child(_section("SLIDER  →  PROGRESS"))
    for col, init in [
        (ColorPalette.BLUE,   0.6),
        (ColorPalette.GREEN,  0.35),
        (ColorPalette.ORANGE, 0.8),
    ]:
        sv = pl.State(init)
        pv = pl.State(init)
        sv.bind(lambda v, _p=pv: setattr(_p, "value", max(0.0, min(1.0, v))))
        page.add_child(pl.Slider(value=sv, min_val=0.0, max_val=1.0,
                                 width=0.95, height=26, active_color=col))
        page.add_child(pl.ProgressBar(progress=pv, width=0.95, height=6, active_color=col))

    page.add_child(_section("SWITCHES"))
    for lbl, st, col in [
        ("Notifications",   sw_notif,     ColorPalette.BLUE),
        ("Background Sync", sw_sync,      ColorPalette.GREEN),
        ("Analytics",       sw_analytics, ColorPalette.ORANGE),
    ]:
        r = _row(38)
        r.add_child(pl.Label(lbl, font_size=14, anchor="left", x=0, y=0))
        r.add_child(pl.Switch(value=st, active_color=col, anchor="right", x=0, y=0))
        page.add_child(r)

    page.add_child(_section("CHECKBOXES"))
    for lbl, st in [("Accept terms and conditions", check_a), ("Subscribe to newsletter", check_b)]:
        r = _row(34)
        r.add_child(pl.Checkbox(value=st, size=22, anchor="left", x=0, y=0))
        r.add_child(pl.Label(lbl, font_size=13, anchor="left", x=30, y=0))
        page.add_child(r)

    page.add_child(_section("RADIO GROUP"))
    for i, lbl in enumerate(["Option Alpha", "Option Beta", "Option Gamma"]):
        r = _row(34)
        r.add_child(pl.RadioButton(group_state=radio_val, choice_value=i,
                                   size=22, anchor="left", x=0, y=0))
        r.add_child(pl.Label(lbl, font_size=13, anchor="left", x=30, y=0))
        page.add_child(r)

    page.add_child(_spacer())
    return page


def build_lists_page():
    page = _page("Lists")

    page.add_child(_section("AVATARS"))
    av_row = _row(52)
    for i, (nm, col) in enumerate(zip(
        ["Alice", "Bob", "Carol", "Dave", "Eve"],
        [ColorPalette.BLUE, ColorPalette.GREEN, ColorPalette.PURPLE,
         ColorPalette.ORANGE, ColorPalette.RED],
    )):
        av_row.add_child(pl.Avatar(initials=nm[:2], size=44, color=col,
                                   anchor="left", x=i * 54, y=0))
    page.add_child(av_row)

    page.add_child(_section("LIST WITH CARDS"))
    card = pl.Card(spacing=0, padding=0, width=0.95)
    entries = [
        ("Inbox",  "5 unread",  ColorPalette.BLUE),
        ("Drafts", "2 drafts",  ColorPalette.ORANGE),
        ("Sent",   "All clear", ColorPalette.GREEN),
        ("Trash",  "3 items",   ColorPalette.RED),
    ]
    for i, (title, sub, col) in enumerate(entries):
        av = pl.Avatar(initials=title[:2], size=32, color=col)
        card.add_child(pl.ListItem(title=title, subtitle=sub, leading=av,
                                   width=1.0, height=56, border_radius=0))
        if i < len(entries) - 1:
            card.add_child(pl.Divider(width=0.9))
    page.add_child(card)

    page.add_child(_section("SLIDE REVEAL"))
    reveal_content = pl.Card(spacing=6, padding=14, width=1.0)
    reveal_content.add_child(pl.Label(
        "Spring-animated panel — toggle to hide or show.",
        font_size=13, color=iOSTheme.secondary_label, wrap_width=300,
    ))
    reveal_card = pl.SlideReveal(child=reveal_content, max_height=70, visible=True, width=0.95)

    toggle_row = _row(38)
    toggle_row.add_child(pl.Label("Show details", font_size=14, anchor="left", x=0, y=0))
    toggle_row.add_child(pl.Switch(value=reveal_vis, anchor="right", x=0, y=0))
    page.add_child(toggle_row)
    reveal_vis.bind(lambda v: reveal_card.reveal(bool(v)))
    page.add_child(reveal_card)

    page.add_child(_section("EMPTY STATE"))
    page.add_child(pl.EmptyState(
        icon="📭",
        title="Nothing here yet",
        subtitle="Items you add will appear here.",
        icon_size=40,
        width=0.95, height=120,
    ))

    page.add_child(_spacer())
    return page


def build_display_page():
    page = _page("Display")

    page.add_child(_section("PROGRESS RINGS"))
    ring_row = _row(64)
    for i, (p, col) in enumerate(zip(
        [0.2, 0.45, 0.7, 0.88, 1.0],
        [ColorPalette.RED, ColorPalette.ORANGE, ColorPalette.BLUE,
         ColorPalette.GREEN, ColorPalette.PURPLE],
    )):
        ring_row.add_child(pl.ProgressRing(progress=p, size=52, active_color=col,
                                           anchor="left", x=i * 62, y=0))
    page.add_child(ring_row)

    page.add_child(_section("LINE CHART — 7 DAYS"))
    page.add_child(pl.LineChart(
        data=[12, 28, 19, 45, 38, 52, 41],
        labels=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        width=0.95, height=120,
        active_color=ColorPalette.BLUE,
    ))

    page.add_child(_section("LINE CHART — REVENUE"))
    page.add_child(pl.LineChart(
        data=[8400, 11200, 9800, 14600, 13100, 17800],
        labels=["Jan", "Feb", "Mar", "Apr", "May", "Jun"],
        width=0.95, height=100,
        active_color=ColorPalette.GREEN,
    ))

    page.add_child(_section("OPTION SELECTOR"))
    page.add_child(pl.OptionSelector(
        options=[
            ("Spring Physics", "spring"),
            ("Ease In-Out",    "ease"),
            ("Linear",         "linear"),
        ],
        value=pl.State("spring"),
        width=0.95, row_height=40, spacing=6,
    ))

    page.add_child(_spacer())
    return page


def build_extras_page():
    page = _page("Extras")

    page.add_child(_section("MATERIAL ICONS"))
    icon_row = _row(36)
    for i, name in enumerate(["home", "search", "settings", "favorite", "star",
                               "music_note", "play_arrow", "person"]):
        icon_row.add_child(pl.Icon(name, size=26, anchor="left", x=i * 38, y=0))
    page.add_child(icon_row)

    page.add_child(_section("EMOJI ICONS  (requires Pillow + NotoColorEmoji)"))
    emoji_row = _row(48)
    for i, ch in enumerate(["🎹", "🎵", "🎶", "🎸", "🥁", "🎺", "🎻"]):
        emoji_row.add_child(pl.EmojiIcon(ch, size=38, anchor="left", x=i * 48, y=0))
    page.add_child(emoji_row)

    page.add_child(_section("FILE PICKER"))
    picker = pl.FilePicker(title="Choose a file",
                           filters=["All files|*", "Python files|*.py"])
    page.add_child(picker)

    pick_row = _row(40)
    pick_row.add_child(pl.Button(
        "Browse…",
        on_click=lambda: picker.pick(lambda p: setattr(picked_file, "value", p or "Cancelled")),
        width=100, height=36,
        background_color=ColorPalette.BLUE,
        anchor="left", x=0, y=0,
    ))
    pick_row.add_child(pl.Label(picked_file, font_size=12,
                                color=iOSTheme.secondary_label,
                                anchor="left", x=112, y=0))
    page.add_child(pick_row)

    page.add_child(_section("CODE VIEWER"))
    sample = """\
import pylay as pl

dark = pl.State(True)
app  = pl.App(dark_mode=True)

btn = pl.Button(
    "Click me",
    on_click=lambda: print("hi"),
    width=200, height=44,
)
app.root.add_child(btn)
app.run()
"""
    page.add_child(pl.CodeViewer(
        code_text=sample,
        width=0.95, height=200,
    ))

    page.add_child(_spacer())
    return page


def _ic_controls(s, cx, cy, sc, col):
    r = int(pl.scaled_px(5) * sc)
    pygame.draw.rect(s, col, (cx - r, cy - r, r * 2, r * 2), border_radius=2)

def _ic_forms(s, cx, cy, sc, col):
    r = int(pl.scaled_px(5) * sc)
    for dy in (-3, 3):
        pygame.draw.line(s, col, (cx - r, cy + dy), (cx + r, cy + dy), 2)

def _ic_lists(s, cx, cy, sc, col):
    r = int(pl.scaled_px(5) * sc)
    for dy in (-r, 0, r):
        pygame.draw.circle(s, col, (cx - r // 2, cy + dy), max(1, r // 3))
        pygame.draw.line(s, col, (cx, cy + dy), (cx + r, cy + dy), 2)

def _ic_display(s, cx, cy, sc, col):
    r = int(pl.scaled_px(5) * sc)
    pygame.draw.circle(s, col, (cx, cy), r, max(1, int(2 * sc)))

def _ic_extras(s, cx, cy, sc, col):
    r = int(pl.scaled_px(5) * sc)
    pygame.draw.polygon(s, col,
                        [(cx, cy - r), (cx + r, cy + r), (cx - r, cy + r)])


def build_root():
    root = pl.FloatLayout(
        anchor="top_left", x=0, y=0, width=1.0, height=1.0,
        background_color=iOSTheme.background, border_radius=0,
    )

    page_names = ["controls", "forms", "lists", "display", "extras"]
    page_fns   = [build_controls_page, build_forms_page,
                  build_lists_page, build_display_page, build_extras_page]

    router = pl.PageRouter(
        pages=dict(zip(page_names, page_fns)),
        initial_page="controls",
        anchor="top_left", x=0, y=0, width=1.0, height=1.0,
    )

    def _on_tab(idx):
        name = page_names[int(idx)]
        if name != router.active_page_name:
            router.navigate(name)

    tab_st.bind(_on_tab)

    nav = pl.BottomNavigationBar(
        active_tab_state=tab_st,
        items=[
            {"title": "Controls", "icon_fn": _ic_controls},
            {"title": "Forms",    "icon_fn": _ic_forms},
            {"title": "Lists",    "icon_fn": _ic_lists},
            {"title": "Display",  "icon_fn": _ic_display},
            {"title": "Extras",   "icon_fn": _ic_extras},
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
        active_tab_state=tab_st,
        tabs=["Controls", "Forms", "Lists", "Display", "Extras"],
    )

    root.add_child(router)
    root.add_child(nav)
    root.add_child(hamburger)
    root.add_child(drawer)
    return root


if __name__ == "__main__":
    pl.set_window_size(800, 600)
    app = pl.App(title="PyLay Demo", width=800, height=600, dark_mode=True)
    # Bind here so dark_st changes reach the live app instance
    dark_st.bind(lambda v: app.apply_theme(dark=bool(v)))
    app.root = build_root()
    app.root.layout(app.screen.get_rect())
    app.run()
