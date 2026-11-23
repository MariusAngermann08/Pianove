import pygame
from typing import List, Optional, Union

from pylay.core.element import UIElement
from pylay.core.theme import iOSTheme, ColorPalette
from pylay.core.scale import scaled_font_size, scaled_px
from pylay.core import font_loader


class BarChart(UIElement):
    """A card with one rounded bar per value: for counts per day, per week, per item.

        BarChart([12, 0, 30, 8, 0, 0, 0], labels=["Mon", …], title="Minutes this week",
                 highlight=2, target=10, unit="min")

    highlight: index of a bar drawn in the full colour (the others are lighter), e.g. today.
    target:    draws a dashed line at this value, e.g. a daily goal.
    unit:      appended to the value printed above each non-zero bar.
    """

    def __init__(self,
                 data: List[float],
                 labels: Optional[List[str]] = None,
                 active_color: Optional[pygame.Color] = None,
                 title: str = "",
                 highlight: Optional[int] = None,
                 target: Optional[float] = None,
                 unit: str = "",
                 anchor: str = "top_left",
                 x: Union[int, float] = 0,
                 y: Union[int, float] = 0,
                 width: Union[int, float] = 400,
                 height: Union[int, float] = 200,
                 **kwargs):
        super().__init__(anchor=anchor, x=x, y=y, width=width, height=height, **kwargs)
        self.data = [max(0.0, float(v)) for v in data]
        self.labels = labels if labels is not None else [str(i + 1) for i in range(len(data))]
        self.active_color = active_color if active_color is not None else ColorPalette.BLUE
        self.title = title
        self.highlight = highlight
        self.target = target
        self.unit = unit
        self.grow = 0.0
        self.animate_to("grow", 1.0, response=0.5, damping_fraction=0.8)
        self._fonts = None
        self._font_px = 0

    def _on_scale_changed(self):
        self._fonts = None

    def _on_theme_changed(self):
        self._fonts = None

    def _get_fonts(self):
        px = scaled_font_size(13)
        if self._fonts is None or self._font_px != px:
            self._fonts = (font_loader.load_font(13, bold=True),
                           font_loader.load_font(11, bold=False),
                           font_loader.load_font(11, bold=True))
            self._font_px = px
        return self._fonts

    @staticmethod
    def _fmt(v: float) -> str:
        return str(int(round(v))) if v >= 10 or abs(v - round(v)) < 0.05 else f"{v:.1f}"

    def render(self, surface: pygame.Surface):
        w, h = self.rect.width, self.rect.height
        if w <= 20 or h <= 40 or not self.data:
            return
        rx, ry = self.rect.left, self.rect.top
        f_title, f_small, f_bold = self._get_fonts()
        pygame.draw.rect(surface, iOSTheme.secondary_background, self.rect, border_radius=scaled_px(16))

        pad = scaled_px(18)
        top = ry + pad
        if self.title:
            surface.blit(f_title.render(self.title, True, iOSTheme.label), (rx + pad, top))
            top += f_title.get_linesize() + scaled_px(10)
        label_h = f_small.get_linesize() + scaled_px(6)
        value_h = f_bold.get_linesize() + scaled_px(2)
        base_y = ry + h - pad - label_h
        plot_top = top + value_h
        avail_h = max(10, base_y - plot_top)

        peak = max(max(self.data), self.target or 0.0, 1e-6)
        n = len(self.data)
        slot = (w - 2 * pad) / n
        bar_w = max(4, min(int(slot * 0.5), scaled_px(44)))
        radius = min(bar_w // 2, scaled_px(7))

        pygame.draw.line(surface, iOSTheme.fill_tertiary, (rx + pad, base_y), (rx + w - pad, base_y), 1)
        if self.target:
            ty = base_y - self.target / peak * avail_h
            x0 = rx + pad
            while x0 < rx + w - pad:
                pygame.draw.line(surface, iOSTheme.secondary_label, (x0, ty), (min(x0 + 6, rx + w - pad), ty), 1)
                x0 += 11

        light = pygame.Color(self.active_color)
        light.a = 255
        bg = iOSTheme.secondary_background
        mix = 0.45
        light = pygame.Color(int(light.r * mix + bg.r * (1 - mix)), int(light.g * mix + bg.g * (1 - mix)),
                             int(light.b * mix + bg.b * (1 - mix)))

        for i, v in enumerate(self.data):
            cx = rx + pad + slot * (i + 0.5)
            strong = self.highlight is None or i == self.highlight
            color = self.active_color if strong else light
            bh = v / peak * avail_h * self.grow
            if v > 0:
                bh = max(bh, scaled_px(4))
                bar = pygame.Rect(int(cx - bar_w / 2), int(base_y - bh), bar_w, int(bh))
                pygame.draw.rect(surface, color, bar, border_top_left_radius=radius, border_top_right_radius=radius)
                txt = f_bold.render(self._fmt(v) + (f" {self.unit}" if self.unit and strong else ""),
                                    True, iOSTheme.label if strong else iOSTheme.secondary_label)
                surface.blit(txt, txt.get_rect(midbottom=(cx, bar.top - scaled_px(3))))
            else:
                pygame.draw.circle(surface, iOSTheme.fill_tertiary, (int(cx), int(base_y - 2)), 2)
            lbl_font = f_bold if (self.highlight is not None and i == self.highlight) else f_small
            lbl = lbl_font.render(self.labels[i] if i < len(self.labels) else "", True,
                                  iOSTheme.label if i == self.highlight else iOSTheme.secondary_label)
            surface.blit(lbl, lbl.get_rect(midtop=(cx, base_y + scaled_px(6))))
