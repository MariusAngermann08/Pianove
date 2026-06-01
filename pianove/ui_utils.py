import pygame
from pylay import FloatLayout, VStack, Label, Button, iOSTheme, ColorPalette
from pylay.core.scale import set_window_size, REF_WIDTH, REF_HEIGHT
from pianove.i18n import t

PAGE_ORDER = ["language", "name", "welcome", "experience", "midi", "ready"]

UI_BASE = {
    "card_width": 0.76,
    "card_height": 0.82,
    "card_padding": 30,
    "card_spacing": 18,
    "card_radius": 16,
    "title_size": 28,
    "subtitle_size": 15,
    "subtitle_wrap": 600,
    "content_height": 0.56,
    "content_spacing": 12,
    "nav_height_frac": 0.11,
    "btn_h_frac": 0.82,
    "btn_font": 15,
    "btn_back_w_frac": 0.34,
    "btn_next_w_frac": 0.48,
    "field_h_frac": 0.22,
    "option_row_h": 48,
    "option_spacing": 8,
    "option_font": 14,
    "summary_size": 14,
}


def ui_dims(w: int | None = None, h: int | None = None) -> dict:
    import pianove.context as ctx
    if w is None or h is None:
        w, h = ctx.ui.width, ctx.ui.height
    set_window_size(w, h, REF_WIDTH, REF_HEIGHT)
    from pylay.core.scale import UI_SCALE

    px = lambda v: max(1, int(v * UI_SCALE))
    d = {}
    for key, val in UI_BASE.items():
        if isinstance(val, float) and val <= 1.0:
            d[key] = val
        elif isinstance(val, int):
            d[key] = px(val)
        else:
            d[key] = val
    d["subtitle_wrap"] = px(UI_BASE["subtitle_wrap"])
    return d


def go_next(current: str):
    import pianove.context as ctx
    idx = PAGE_ORDER.index(current)
    if idx < len(PAGE_ORDER) - 1:
        ctx.router.navigate(PAGE_ORDER[idx + 1], "right")


def go_back(current: str):
    import pianove.context as ctx
    idx = PAGE_ORDER.index(current)
    if idx > 0:
        ctx.router.navigate(PAGE_ORDER[idx - 1], "left")


def set_continue_enabled(btn: Button, ok: bool):
    btn.enabled = ok
    if ok:
        btn.background_color = ColorPalette.BLUE
        btn.text_color = pygame.Color(255, 255, 255)
    else:
        btn.background_color = (
            ColorPalette.LIGHT_GRAY_3 if not iOSTheme.dark else ColorPalette.DARK_GRAY_3
        )
        btn.text_color = (
            ColorPalette.LIGHT_GRAY_1 if not iOSTheme.dark else ColorPalette.DARK_GRAY_2
        )
    btn._cached_surf = None
    btn._cache_key = None


def page_shell(
    title: str,
    subtitle: str = "",
    page_id: str = "",
    show_back: bool = False,
    next_label: str | None = None,
    on_next=None,
    continue_enabled: bool = True,
    show_next: bool = True,
):
    U = ui_dims()
    if next_label is None:
        next_label = t("continue")
    root = FloatLayout(width=1.0, height=1.0, background_color=pygame.Color(0, 0, 0, 0))
    card = VStack(
        spacing=U["card_spacing"],
        padding=U["card_padding"],
        anchor="center",
        x=0,
        y=0,
        width=U["card_width"],
        height=U["card_height"],
        border_radius=U["card_radius"],
        border_width=1,
        background_color=iOSTheme.secondary_background,
    )
    root.add_child(card)
    if title:
        card.add_child(Label(text=title, font_size=U["title_size"], bold=True))
    if subtitle:
        card.add_child(
            Label(
                text=subtitle,
                font_size=U["subtitle_size"],
                color=iOSTheme.secondary_label,
                wrap_width=U["subtitle_wrap"],
            )
        )
    content = VStack(
        spacing=U["content_spacing"], width=0.95, height=U["content_height"]
    )
    card.add_child(content)

    nav = FloatLayout(width=0.95, height=U["nav_height_frac"])
    if show_back:
        nav.add_child(
            Button(
                text=t("back"),
                on_click=lambda: go_back(page_id),
                anchor="left",
                x=0,
                y=0,
                width=U["btn_back_w_frac"],
                height=U["btn_h_frac"],
                font_size=U["btn_font"],
                background_color=iOSTheme.fill,
                text_color=iOSTheme.label,
            )
        )
    next_btn = None
    if show_next:
        next_btn = Button(
            text=next_label,
            on_click=on_next if on_next else (lambda: go_next(page_id)),
            anchor="right",
            x=0,
            y=0,
            width=U["btn_next_w_frac"],
            height=U["btn_h_frac"],
            font_size=U["btn_font"],
            background_color=ColorPalette.BLUE,
        )
        set_continue_enabled(next_btn, continue_enabled)
        nav.add_child(next_btn)
    card.add_child(nav)
    return root, card, content, next_btn
