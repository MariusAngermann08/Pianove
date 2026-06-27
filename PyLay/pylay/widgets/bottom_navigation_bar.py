import pygame
from pylay.layouts.float_layout import FloatLayout
from pylay.core.theme import iOSTheme
from pylay.core.state import State
from pylay.core.physics import Spring
from pylay.core.scale import scaled_font_size, scaled_px
from pylay.core import font_loader
from typing import List, Dict, Union, Any, Optional, Callable

class BottomNavigationBar(FloatLayout):
    def __init__(self,
                 active_tab_state: State,
                 items: List[Dict[str, Any]],
                 on_change: Optional[Callable[[int], None]] = None,
                 height: int = 64,
                 **kwargs):
        super().__init__(anchor="bottom", x=0, y=0, width=1.0, height=height,
                         background_color=iOSTheme.secondary_background,
                         border_radius=0, **kwargs)

        self.active_tab = active_tab_state
        self.items = items
        self.on_change = on_change

        self._last_selected = int(self.active_tab.value)

        # Direct Spring objects per tab — no __getattr__ / __setattr__ hacks needed
        self.tab_scales: List[float] = [1.0] * len(items)
        self._tab_springs: List[Spring] = []
        for i in range(len(items)):
            val = 1.1 if i == self._last_selected else 1.0
            sp = Spring(value=val, response=0.18, damping_fraction=0.55)
            sp.target = val
            self.tab_scales[i] = val
            self._tab_springs.append(sp)

        self.active_tab.bind(self._on_state_update)

        self._font: Optional[pygame.font.Font] = None
        self._font_px: int = 0

    def _on_scale_changed(self):
        self._font = None
        self._font_px = 0

    def _on_theme_changed(self):
        self._font = None
        self._font_px = 0

    def _on_state_update(self, val: Any):
        new_sel = int(val)
        if new_sel != self._last_selected and 0 <= new_sel < len(self._tab_springs):
            # Bounce the new tab up
            sp_new = self._tab_springs[new_sel]
            sp_new.response = 0.18
            sp_new.damping_fraction = 0.55
            sp_new.target = 1.1

            # Settle the old tab back
            sp_old = self._tab_springs[self._last_selected]
            sp_old.response = 0.20
            sp_old.damping_fraction = 0.80
            sp_old.target = 1.0

            self._last_selected = new_sel

    def _get_font(self) -> pygame.font.Font:
        px = scaled_font_size(11)
        if self._font is None or self._font_px != px:
            self._font = font_loader.load_font(11, bold=True)
            self._font_px = px
        return self._font

    def update(self, dt: float):
        # Tick each tab spring directly — no property-name indirection needed
        for i, sp in enumerate(self._tab_springs):
            sp.update(dt)
            self.tab_scales[i] = sp.value
        super().update(dt)
            
    def on_event(self, event: pygame.event.Event) -> bool:
        if not self.enabled or not self.visible:
            return False
            
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                # Determine which tab column was clicked
                col_w = self.rect.width / max(1, len(self.items))
                click_x = event.pos[0] - self.rect.left
                clicked_idx = int(click_x // col_w)
                clicked_idx = max(0, min(len(self.items) - 1, clicked_idx))
                
                if clicked_idx != self.active_tab.value:
                    self.active_tab.value = clicked_idx
                    if self.on_change:
                        self.on_change(clicked_idx)
                    return True
                    
        return False
        
    def render(self, surface: pygame.Surface):
        # Draw base bar background and top border line
        super().render(surface)
        
        rx, ry = self.rect.left, self.rect.top
        w, h = self.rect.width, self.rect.height
        cols = len(self.items)
        col_w = w / max(1, cols)
        
        font = self._get_font()
        border_col = iOSTheme.fill_tertiary
        pygame.draw.line(surface, border_col, (rx, ry), (rx + w, ry), 1)
        
        for i, item in enumerate(self.items):
            cx = rx + int(i * col_w + col_w / 2.0)
            cy = ry + h // 2
            
            is_active = (i == self.active_tab.value)
            scale = self.tab_scales[i]
            
            # Active color vs inactive gray color
            color = iOSTheme.accent if is_active else iOSTheme.secondary_label
            
            # Text rendering
            label_surf = font.render(item["title"], True, color)
            
            # Position active items with a spring-bouncing vertical offset
            vertical_bounce_offset = int((scale - 1.0) * -scaled_px(16))

            # Draw tab text centered at bottom of tab
            lbl_rect = label_surf.get_rect(
                centerx=cx, centery=ry + h - scaled_px(14) + vertical_bounce_offset)
            surface.blit(label_surf, lbl_rect)

            # Render vector icons or shapes
            icon_y = ry + h // 2 - scaled_px(8) + vertical_bounce_offset
            icon_r = int(scaled_px(7) * scale)
            
            if "icon_fn" in item and item["icon_fn"]:
                item["icon_fn"](surface, cx, icon_y, scale, color)
            else:
                # Default elegant dot/ring icon
                if is_active:
                    pygame.draw.circle(surface, color, (cx, icon_y), icon_r)
                else:
                    pygame.draw.circle(surface, color, (cx, icon_y), icon_r, 2)
