import pygame
from pylay.layouts.float_layout import FloatLayout
from pylay.core.theme import iOSTheme
from pylay.core.state import State
from pylay.core.scale import scaled_font_size, scaled_px
from typing import List, Dict, Any, Optional, Callable

_BASE_HEADER_H  = 64
_BASE_ITEM_H    = 52
_BASE_ITEM_PAD  = 10
_BASE_ICON_OFF  = 22
_BASE_LABEL_OFF = 50


class SideNav(FloatLayout):
    def __init__(self,
                 active_tab_state: State,
                 items: List[Dict[str, Any]],
                 on_change: Optional[Callable[[int], None]] = None,
                 width: int = 200,
                 title: str = "",
                 footer_fn: Optional[Callable[[], str]] = None,
                 bottom_action: Optional[Dict[str, Any]] = None,
                 **kwargs):
        super().__init__(anchor="top_left", x=0, y=0,
                         width=width, height=1.0,
                         background_color=iOSTheme.secondary_background,
                         border_radius=0, **kwargs)
        self.active_tab     = active_tab_state
        self.items          = items
        self.on_change      = on_change
        self._title         = title
        self._footer_fn     = footer_fn        # shown as subtitle of bottom_action
        self._bottom_action = bottom_action
        self._hover_idx     = -1
        self._bottom_hover  = False
        self._bottom_active = False            # True when bottom action is selected
        self._bottom_rect:  Optional[pygame.Rect] = None

        self._font:        Optional[pygame.font.Font] = None
        self._title_font:  Optional[pygame.font.Font] = None
        self._sub_font:    Optional[pygame.font.Font] = None
        self._font_px: int = 0

        # Spring-animated marker Y. Negative = snap on first valid frame.
        self._marker_y: float = -1.0

        self.active_tab.bind(lambda _: setattr(self, "_bottom_active", False))

    def _on_scale_changed(self):
        self._font = self._title_font = self._sub_font = None
        self._font_px  = 0
        self._marker_y = -1.0

    def _on_theme_changed(self):
        self._font = self._title_font = self._sub_font = None
        self._font_px = 0

    def _get_fonts(self):
        px = scaled_font_size(14)
        if self._font is None or self._font_px != px:
            pygame.font.get_init() or pygame.font.init()
            self._font       = pygame.font.SysFont("Arial", px)
            self._title_font = pygame.font.SysFont("Arial", scaled_font_size(17), bold=True)
            self._sub_font   = pygame.font.SysFont("Arial", scaled_font_size(11))
            self._font_px = px
        return self._font, self._title_font, self._sub_font

    def _item_rect(self, idx: int) -> pygame.Rect:
        header_h = scaled_px(_BASE_HEADER_H)
        item_h   = scaled_px(_BASE_ITEM_H)
        item_pad = scaled_px(_BASE_ITEM_PAD)
        rx, ry   = self.rect.left, self.rect.top
        y = ry + header_h + idx * item_h
        return pygame.Rect(rx + item_pad, y + 4,
                           self.rect.width - item_pad * 2, item_h - 8)

    def _bottom_item_rect(self) -> Optional[pygame.Rect]:
        if not self._bottom_action or not self.rect.width:
            return None
        item_h   = scaled_px(_BASE_ITEM_H)
        item_pad = scaled_px(_BASE_ITEM_PAD)
        rx, ry   = self.rect.left, self.rect.top
        h        = self.rect.height
        # Subtitle adds one small-font line (~16px) below the pill
        sub_h    = scaled_px(20)
        pill_h   = item_h - 8
        total_h  = pill_h + sub_h
        y        = ry + h - total_h - scaled_px(12)
        return pygame.Rect(rx + item_pad, y, self.rect.width - item_pad * 2, pill_h)

    def _marker_target(self) -> float:
        if self._bottom_active:
            r = self._bottom_item_rect()
            return float(r.centery) if r else self._marker_y
        return float(self._item_rect(int(self.active_tab.value)).centery)

    def update(self, dt: float):
        if self.rect.width:
            target = self._marker_target()
            if self._marker_y < 0:
                self._marker_y = target
            else:
                self.animate_to("_marker_y", target,
                                response=0.40, damping_fraction=0.72)
        super().update(dt)

    def _blend_color(self, dist_px: float, item_h: float) -> pygame.Color:
        blend = max(0.0, 1.0 - abs(dist_px) / max(item_h, 1))
        if blend < 0.01:
            return iOSTheme.secondary_label
        base = iOSTheme.secondary_label
        r = int(base.r + blend * (255 - base.r))
        g = int(base.g + blend * (255 - base.g))
        b = int(base.b + blend * (255 - base.b))
        return pygame.Color(r, g, b)

    def render(self, surface: pygame.Surface):
        super().render(surface)
        if not self.rect.width:
            return

        font, title_font, sub_font = self._get_fonts()
        rx, ry = self.rect.left, self.rect.top
        w, h   = self.rect.width, self.rect.height
        active = int(self.active_tab.value)

        item_h    = scaled_px(_BASE_ITEM_H)
        item_pad  = scaled_px(_BASE_ITEM_PAD)
        header_h  = scaled_px(_BASE_HEADER_H)
        icon_off  = scaled_px(_BASE_ICON_OFF)
        label_off = scaled_px(_BASE_LABEL_OFF)

        marker_h = item_h - 8
        marker_w = w - item_pad * 2

        if self._title:
            ts = title_font.render(self._title, True, iOSTheme.label)
            surface.blit(ts, (rx + scaled_px(16), ry + (header_h - ts.get_height()) // 2))
            pygame.draw.line(surface, iOSTheme.fill_tertiary,
                             (rx, ry + header_h - 1), (rx + w, ry + header_h - 1), 1)

        if self._marker_y > 0:
            pygame.draw.rect(
                surface, iOSTheme.accent,
                pygame.Rect(rx + item_pad,
                            int(self._marker_y) - marker_h // 2,
                            marker_w, marker_h),
                border_radius=scaled_px(10),
            )

        for i, item in enumerate(self.items):
            ir       = self._item_rect(i)
            text_col = self._blend_color(ir.centery - self._marker_y, item_h)
            if self._marker_y < 0:
                text_col = pygame.Color(255, 255, 255) if i == active else iOSTheme.secondary_label

            if i == self._hover_idx and i != active:
                hs = pygame.Surface((ir.width, ir.height), pygame.SRCALPHA)
                pygame.draw.rect(hs, pygame.Color(120, 120, 120, 60),
                                 (0, 0, ir.width, ir.height), border_radius=scaled_px(10))
                surface.blit(hs, ir.topleft)

            fn = item.get("icon_fn")
            cx, cy = ir.left + icon_off, ir.centery
            if fn:
                fn(surface, cx, cy, 1.0, text_col)
            else:
                pygame.draw.circle(surface, text_col, (cx, cy), scaled_px(6), 2)

            ls = font.render(item["title"], True, text_col)
            surface.blit(ls, (ir.left + label_off, cy - ls.get_height() // 2))

        if self._bottom_action:
            br = self._bottom_item_rect()
            self._bottom_rect = br

            text_col = self._blend_color(br.centery - self._marker_y, item_h)
            if self._marker_y < 0:
                text_col = pygame.Color(255, 255, 255) if self._bottom_active else iOSTheme.secondary_label

            if self._bottom_hover and not self._bottom_active:
                hs = pygame.Surface((br.width, br.height), pygame.SRCALPHA)
                pygame.draw.rect(hs, pygame.Color(120, 120, 120, 60),
                                 (0, 0, br.width, br.height), border_radius=scaled_px(10))
                surface.blit(hs, br.topleft)

            fn = self._bottom_action.get("icon_fn")
            cx, cy = br.left + icon_off, br.centery
            if fn:
                fn(surface, cx, cy, 1.0, text_col)

            lbl = self._bottom_action.get("label", "")
            if lbl:
                ls = font.render(lbl, True, text_col)
                surface.blit(ls, (br.left + label_off, cy - ls.get_height() // 2))

            # Subtitle (footer_fn) — sits just below the pill, always secondary
            if self._footer_fn:
                sub_text = self._footer_fn()
                if sub_text:
                    ss = sub_font.render(sub_text, True, iOSTheme.secondary_label)
                    surface.blit(ss, (br.left + label_off,
                                      br.bottom + scaled_px(4)))

        pygame.draw.line(surface, iOSTheme.fill_tertiary,
                         (rx + w - 1, ry), (rx + w - 1, ry + h), 1)

    def on_event(self, event: pygame.event.Event) -> bool:
        if not self.enabled or not self.visible:
            return False

        if event.type == pygame.MOUSEMOTION:
            self._hover_idx    = -1
            self._bottom_hover = False
            for i in range(len(self.items)):
                if self._item_rect(i).collidepoint(event.pos):
                    self._hover_idx = i
                    break
            if self._bottom_rect and self._bottom_rect.collidepoint(event.pos):
                self._bottom_hover = True
            return False

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for i in range(len(self.items)):
                if self._item_rect(i).collidepoint(event.pos):
                    self._bottom_active = False
                    if i != int(self.active_tab.value):
                        self.active_tab.value = i
                        if self.on_change:
                            self.on_change(i)
                    return True
            if self._bottom_rect and self._bottom_rect.collidepoint(event.pos):
                self._bottom_active = True
                cb = self._bottom_action.get("on_click")
                if cb:
                    cb()
                return True

        return False
