from pylay import FloatLayout, State, SideNav, PageRouter, iOSTheme
from pylay.widgets.icon import Icon
from pylay.core.scale import UI_SCALE, scaled_px
from pianove.i18n import t
from pianove.state import midi_device_state, creator_mode_state
from pianove.home import tab_home, tab_songs, tab_lessons, tab_settings, tab_creator, tab_practice
from pianove.home.ui_logo import PianoveLogoWidget
import pianove.context as ctx

_active_tab = State(0)
_NAV_W      = 200   # base sidebar width (pixels at 1× scale)

_ICON_FNS = {
    "home":     Icon.as_icon_fn("home",          base_size=20),
    "songs":    Icon.as_icon_fn("library_music", base_size=20),
    "lessons":  Icon.as_icon_fn("school",        base_size=20),
    "practice": Icon.as_icon_fn("piano",         base_size=20),
    "creator":  Icon.as_icon_fn("brush",         base_size=20),
}


def build():
    nav_w        = max(160, int(_NAV_W * UI_SCALE))
    content_w    = max(200, ctx.ui.width - nav_w)
    show_creator = bool(creator_mode_state.value)

    tab_keys = ["home", "songs", "lessons", "practice"]
    icons    = [_ICON_FNS[k] for k in tab_keys]
    pages    = {
        "home":          tab_home.build,
        "songs":         tab_songs.build,
        "lessons":       tab_lessons.build,
        "course_detail": tab_lessons.build_detail,
        "practice":      tab_practice.build,
        "settings":      tab_settings.build,
    }

    if show_creator:
        tab_keys.append("creator")
        icons.append(_ICON_FNS["creator"])
        pages["creator"] = tab_creator.build

    # Clamp active tab index within current tab count
    active_idx = min(int(_active_tab.value), len(tab_keys) - 1)

    root = FloatLayout(width=1.0, height=1.0, background_color=iOSTheme.background)

    initial = tab_keys[active_idx]
    if ctx.home_page in pages and ctx.home_page not in tab_keys:
        initial = ctx.home_page

    tab_router = PageRouter(
        pages=pages,
        initial_page=initial,
        anchor="top_left",
        x=nav_w,
        y=0,
        width=content_w,
        height=1.0,
    )
    ctx.inner_router = tab_router
    root.add_child(tab_router)

    nav_items = [
        {"title": t(f"nav_{k}"), "icon_fn": fn}
        for k, fn in zip(tab_keys, icons)
    ]
    header_h = scaled_px(64)

    def _go(page: str):
        ctx.home_page = page
        tab_router.navigate(page)

    side_nav = SideNav(
        active_tab_state=_active_tab,
        items=nav_items,
        on_change=lambda idx: _go(tab_keys[idx]),
        width=nav_w,
        title="",          # suppressed — logo widget renders in its place
        footer_fn=lambda: midi_device_state.value,
        bottom_action={
            "icon_fn":  Icon.as_icon_fn("settings", base_size=20),
            "label":    t("nav_settings"),
            "on_click": lambda: _go("settings"),
        },
    )
    if initial == "settings":
        side_nav._bottom_active = True
    side_nav.add_child(PianoveLogoWidget(
        anchor="top_left", x=0, y=0,
        width=nav_w, height=header_h,
    ))
    root.add_child(side_nav)

    return root
