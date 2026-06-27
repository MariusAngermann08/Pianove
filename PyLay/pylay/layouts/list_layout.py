import pygame
from pylay.layouts.float_layout import FloatLayout
from typing import Optional

class VStack(FloatLayout):
    def __init__(self, spacing: int = 10, padding: int = 15, **kwargs):
        super().__init__(**kwargs)
        self.spacing = spacing
        self.padding = padding

    def layout(self, parent_rect: Optional[pygame.Rect] = None, skip_self: bool = False):
        # 1. Resolve our own rect first; skip premature bounds refresh — we do it after placing children
        super().layout(parent_rect, skip_self=skip_self, _skip_bounds_refresh=True)

        # 2. Place children sequentially — override rect directly
        inner_w  = self.rect.width - self.padding * 2
        current_y = self.rect.top + self.padding

        for child in self.children:
            if not child.visible:
                continue

            child_w = int(inner_w * child.width_spec)  if isinstance(child.width_spec,  float) else int(child.width_spec)
            child_h = int(self.rect.height * child.height_spec) if isinstance(child.height_spec, float) else int(child.height_spec)
            child_w = max(1, child_w)
            child_h = max(1, child_h)

            child.rect.x      = self.rect.left + self.padding + (inner_w - child_w) // 2
            child.rect.y      = current_y
            child.rect.width  = child_w
            child.rect.height = child_h

            # Recurse so the child's own children are laid out correctly
            child.layout(skip_self=True)

            current_y += child.rect.height + self.spacing

        # 3. Check scroll overflow after all children are placed
        self._refresh_scroll_bounds()
