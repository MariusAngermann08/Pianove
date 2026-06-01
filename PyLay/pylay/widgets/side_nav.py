import pygame
from pylay.layouts.float_layout import FloatLayout
from pylay.core.theme import iOSTheme
from pylay.core.state import State
from pylay.core.scale import scaled_font_size, scaled_px
from typing import List, Dict, Any, Optional, Callable

# Base (un-scaled) metrics — scaled at render time via scaled_px()
_BASE_HEADER_H  = 64
_BASE_ITEM_H    = 52
_BASE_ITEM_PAD  = 10
_BASE_ICON_OFF  = 22
_BASE_LABEL_OFF = 50


class SideNav(FloatLayout):
    """
    iOS-style left sidebar navigation panel.
    Items: [{"title": str, "icon_fn": Callable(surf, cx, cy, scale, color)}]
    """

    def __init__(self,
                 active_tab_state: State,
                 items: List[Dict[str, Any]],
                 on_change: Optional[Callable[[int], None]] = None,
                 width: int = 200,
                 title: str = "",
                 footer_fn: Optional[Callable[[], str]] = None,
                 **kwargs):
        super().__init__(anchor="top_left", x=0, y=0,
                         width=width, height=1.0,
                         background_color=iOSTheme.secondary_background,
                         border_radius=0, **kwargs)
        self.active_tab = active_tab_state
        self.items      = items
        self.on_change  = on_change
        self._title     = title
        self._footer_fn = footer_fn
        self._hover_idx = -1
        self._font:        Optional[pygame.font.Font] = None
        self._title_font:  Optional[pygame.font.Font] = None
        self._footer_font: Optional[pygame.font.Font] = None
        self._font_px: int = 0
        self.active_tab.bind(lambda _: None)   # force dirty flag on tab change

    # ── cache invalidation ─────────────────────────────────────────────────

    def _on_scale_changed(self):
        self._font = self._title_font = self._footer_font = None
        self._font_px = 0

    def _on_theme_changed(self):
        self._font = self._title_font = self._footer_font = None
        self._font_px = 0

    # ── fonts ──────────────────────────────────────────────────────────────

    def _get_fonts(self):
        px = scaled_font_size(14)
        if self._font is None or self._font_px != px:
            pygame.font.get_init() or pygame.font.init()
            self._font        = pygame.font.SysFont("Arial", px)
            self._title_font  = pygame.font.SysFont("Arial", scaled_font_size(17), bold=True)
            self._footer_font = pygame.font.SysFont("Arial", scaled_font_size(11))
            self._font_px = px
        return self._font, self._title_font, self._footer_font

    # ── geometry helpers ───────────────────────────────────────────────────

    def _item_rect(self, idx: int) -> pygame.Rect:
        header_h = scaled_px(_BASE_HEADER_H)
        item_h   = scaled_px(_BASE_ITEM_H)
        item_pad = scaled_px(_BASE_ITEM_PAD)
        rx, ry   = self.rect.left, self.rect.top
        y = ry + header_h + idx * item_h
        return pygame.Rect(rx + item_pad, y + 4,
                           self.rect.width - item_pad * 2, item_h - 8)

    # ── render ─────────────────────────────────────────────────────────────

    def render(self, surface: pygame.Surface):
        super().render(surface)
        if not self.rect.width:
            return

        font, title_font, footer_font = self._get_fonts()
        rx, ry = self.rect.left, self.rect.top
        w, h   = self.rect.width, self.rect.height
        active = int(self.active_tab.value)

        header_h  = scaled_px(_BASE_HEADER_H)
        icon_off  = scaled_px(_BASE_ICON_OFF)
        label_off = scaled_px(_BASE_LABEL_OFF)

        # ── header ────────────────────────────────────────────────────────
        ts = title_font.render(self._title, True, iOSTheme.label)
        surface.blit(ts, (rx + scaled_px(16), ry + (header_h - ts.get_height()) // 2))

        div_y = ry + header_h - 1
        pygame.draw.line(surface, iOSTheme.fill_tertiary,
                         (rx, div_y), (rx + w, div_y), 1)

        # ── nav items ─────────────────────────────────────────────────────
        for i, item in enumerate(self.items):
            ir = self._item_rect(i)

            if i == active:
                pygame.draw.rect(surface, iOSTheme.accent, ir, border_radius=scaled_px(10))
                text_col = pygame.Color(255, 255, 255)
                icon_col = pygame.Color(255, 255, 255)
            else:
                if i == self._hover_idx:
                    hs = pygame.Surface((ir.width, ir.height), pygame.SRCALPHA)
                    pygame.draw.rect(hs, pygame.Color(120, 120, 120, 60),
                                     (0, 0, ir.width, ir.height), border_radius=scaled_px(10))
                    surface.blit(hs, ir.topleft)
                text_col = iOSTheme.label if i == self._hover_idx else iOSTheme.secondary_label
                icon_col = text_col

            # icon
            cx = ir.left + icon_off
            cy = ir.centery
            fn = item.get("icon_fn")
            if fn:
                fn(surface, cx, cy, 1.0, icon_col)
            else:
                pygame.draw.circle(surface, icon_col, (cx, cy), scaled_px(6), 2)

            # label
            ls = font.render(item["title"], True, text_col)
            surface.blit(ls, (ir.left + label_off, cy - ls.get_height() // 2))

        # ── right border ──────────────────────────────────────────────────
        pygame.draw.line(surface, iOSTheme.fill_tertiary,
                         (rx + w - 1, ry), (rx + w - 1, ry + h), 1)

        # ── footer text ───────────────────────────────────────────────────
        if self._footer_fn:
            text = self._footer_fn()
            fs = footer_font.render(text, True, iOSTheme.secondary_label)
            surface.blit(fs, (rx + scaled_px(12), ry + h - scaled_px(28)))

    # ── events ─────────────────────────────────────────────────────────────

    def on_event(self, event: pygame.event.Event) -> bool:
        if not self.enabled or not self.visible:
            return False

        if event.type == pygame.MOUSEMOTION:
            self._hover_idx = -1
            for i in range(len(self.items)):
                if self._item_rect(i).collidepoint(event.pos):
                    self._hover_idx = i
                    break
            return False

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for i in range(len(self.items)):
                if self._item_rect(i).collidepoint(event.pos):
                    if i != int(self.active_tab.value):
                        self.active_tab.value = i
                        if self.on_change:
                            self.on_change(i)
                    return True

        return False
