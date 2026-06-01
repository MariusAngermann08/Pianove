import pygame
from pylay.core.element import UIElement
from pylay.core.state import State
from pylay.core.theme import iOSTheme, ColorPalette
from pylay.core.scale import scaled_font_size
from typing import Any, Callable, List, Optional, Tuple, Union

Option = Tuple[str, Any]

_RADIUS = 10
_PAD_X  = 16
_DOT_R  = 5


class OptionSelector(UIElement):
    """
    Vertical single-choice selector styled as iOS settings rows.

    Each option is a rounded card. The selected row gets a bold label, accent
    dot on the right, and a spring-animated accent bar on the left.
    Row dimensions are expected in actual pixels (already scaled by the caller).
    """

    def __init__(
        self,
        options: List[Option],
        value: State,
        on_change: Optional[Callable[[Any], None]] = None,
        anchor: str = "top_left",
        x: Union[int, float] = 0,
        y: Union[int, float] = 0,
        width: Union[int, float] = 300,
        row_height: int = 48,
        spacing: int = 6,
        font_size: int = 15,
        **kwargs,
    ):
        n = max(1, len(options))
        total_h = n * row_height + (n - 1) * spacing
        super().__init__(
            anchor=anchor, x=x, y=y, width=width, height=total_h, **kwargs
        )
        self.options    = options
        self.value      = value
        self.on_change  = on_change
        self.row_height = row_height
        self.spacing    = spacing
        self.font_size  = font_size

        self._selected_idx = self._index_for(value.value)
        # pill_y: y-offset of the animated left accent bar (in local row-index units)
        self.pill_y = float(self._selected_idx * (row_height + spacing))

        value.bind(self._on_state_update)

        self._font: Optional[pygame.font.Font] = None
        self._font_bold: Optional[pygame.font.Font] = None
        self._font_px: int = 0

    # ------------------------------------------------------------------
    def _index_for(self, val: Any) -> int:
        for i, (_, choice) in enumerate(self.options):
            if choice == val:
                return i
        return 0

    def _on_state_update(self, val: Any):
        self._selected_idx = self._index_for(val)

    def _on_scale_changed(self):
        self._font = self._font_bold = None
        self._font_px = 0

    def _get_font(self, bold: bool = False) -> pygame.font.Font:
        px = scaled_font_size(self.font_size)
        if px != self._font_px:
            self._font = self._font_bold = None
            self._font_px = px
        if bold:
            if self._font_bold is None:
                self._font_bold = pygame.font.SysFont("Arial", px, bold=True)
            return self._font_bold
        if self._font is None:
            self._font = pygame.font.SysFont("Arial", px)
        return self._font

    # ------------------------------------------------------------------
    def update(self, dt: float):
        stride = self.row_height + self.spacing
        self.animate_to("pill_y", float(self._selected_idx * stride),
                        response=0.28, damping_fraction=0.85)
        super().update(dt)

    def on_event(self, event: pygame.event.Event) -> bool:
        if not self.enabled or not self.visible:
            return False
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return False
        if not self.rect.collidepoint(event.pos):
            return False
        stride = self.row_height + self.spacing
        idx = int((event.pos[1] - self.rect.top) / stride)
        idx = max(0, min(len(self.options) - 1, idx))
        _, choice = self.options[idx]
        if self.value.value != choice:
            self.value.value = choice
            self._selected_idx = idx
            if self.on_change:
                self.on_change(choice)
        return True

    # ------------------------------------------------------------------
    def render(self, surface: pygame.Surface):
        if self.rect.width <= 4:
            return

        stride      = self.row_height + self.spacing
        accent      = ColorPalette.BLUE
        bar_w       = 3
        bar_pad     = 6   # vertical inset from row edges
        bar_inset   = 3   # horizontal inset so bar clears the rounded corner
        font_normal = self._get_font(bold=False)
        font_bold   = self._get_font(bold=True)

        # Pass 1 — row backgrounds and labels
        for i, (label, _) in enumerate(self.options):
            row_top  = self.rect.top + i * stride
            row_rect = pygame.Rect(self.rect.left, row_top, self.rect.width, self.row_height)
            selected = (i == self._selected_idx)

            pygame.draw.rect(surface, iOSTheme.secondary_background,
                             row_rect, border_radius=_RADIUS)

            font      = font_bold if selected else font_normal
            col       = iOSTheme.label if selected else iOSTheme.secondary_label
            text_surf = font.render(label, True, col)
            text_x    = row_rect.left + bar_inset + bar_w + _PAD_X
            surface.blit(text_surf,
                         text_surf.get_rect(midleft=(text_x, row_rect.centery)))

            if selected:
                pygame.draw.circle(surface, accent,
                                   (row_rect.right - _PAD_X, row_rect.centery),
                                   _DOT_R)

        # Pass 2 — animated accent bar drawn on top of all backgrounds
        bar_y = self.rect.top + int(self.pill_y) + bar_pad
        bar_h = max(1, self.row_height - bar_pad * 2)
        pygame.draw.rect(surface, accent,
                         pygame.Rect(self.rect.left + bar_inset, bar_y, bar_w, bar_h),
                         border_radius=bar_w)
