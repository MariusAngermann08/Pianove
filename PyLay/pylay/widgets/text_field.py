import pygame
from pylay.core.element import UIElement
from pylay.core.theme import iOSTheme, ColorPalette
from pylay.core.scale import scaled_font_size
from pylay.core.state import State
from pylay.core import font_loader, _dirty
from typing import Optional, Union, Callable, Any

class TextField(UIElement):
    def __init__(self,
                 text: Union[str, State] = "",
                 placeholder: str = "Enter text...",
                 on_change: Optional[Callable[[str], None]] = None,
                 anchor: str = "top_left",
                 x: Union[int, float] = 0,
                 y: Union[int, float] = 0,
                 width: Union[int, float] = 200,
                 height: Union[int, float] = 44,
                 font_size: int = 15,
                 **kwargs):
        super().__init__(anchor=anchor, x=x, y=y, width=width, height=height, **kwargs)
        
        self.placeholder = placeholder
        self.on_change = on_change
        self.font_size = font_size
        
        # State Binding
        self._state: Optional[State] = None
        if isinstance(text, State):
            self._state = text
            self.text_val = str(text.value)
            text.bind(self._on_state_update)
        else:
            self.text_val = str(text)
            
        # Focus & Cursor states
        self.is_focused = False
        self.focus_ring = 0.0  # Spring-driven border focus scale

        # Cursor blink timer
        self.cursor_visible = True
        self.cursor_timer = 0.0

        # Horizontal scroll offset — keeps cursor in view when text overflows
        self._scroll_x: int = 0

        self._font: Optional[pygame.font.Font] = None
        self._font_px: int = 0

    def _on_scale_changed(self):
        self._font = None
        self._font_px = 0

    def _on_state_update(self, val: Any):
        self.text_val = str(val)
        
    def _get_font(self) -> pygame.font.Font:
        px = scaled_font_size(self.font_size)
        if self._font is None or self._font_px != px:
            self._font = font_loader.load_font(self.font_size, bold=False)
            self._font_px = px
        return self._font
        
    def update(self, dt: float):
        # Smoothly animate the focus ring border expansion/color shift
        target_focus = 1.0 if self.is_focused else 0.0
        self.animate_to("focus_ring", target_focus, response=0.18, damping_fraction=0.8)
        
        # Blinking cursor ticker
        if self.is_focused:
            self.cursor_timer += dt
            if self.cursor_timer >= 0.5:
                self.cursor_visible = not self.cursor_visible
                self.cursor_timer = 0.0
                _dirty.mark()
        else:
            self.cursor_visible = False
            
        super().update(dt)
        
    def on_event(self, event: pygame.event.Event) -> bool:
        if not self.enabled or not self.visible:
            return False
            
        mouse_pos = pygame.mouse.get_pos()
        hovered = self.rect.collidepoint(mouse_pos)
        
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if hovered:
                if not self.is_focused:
                    self.is_focused = True
                    pygame.key.start_text_input()
                return True
            else:
                if self.is_focused:
                    self.is_focused = False
                    pygame.key.stop_text_input()
                
        elif self.is_focused:
            if event.type == pygame.TEXTINPUT:
                self.text_val += event.text
                self._notify_change()
                return True
                
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_BACKSPACE:
                    self.text_val = self.text_val[:-1]
                    self._notify_change()
                    return True
                elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_ESCAPE):
                    self.is_focused = False
                    pygame.key.stop_text_input()
                    return True
                    
        return False
        
    def _update_scroll_x(self):
        font = self._get_font()
        avail_w = self.rect.width - 24
        text_w = font.size(self.text_val)[0]
        if text_w > avail_w:
            self._scroll_x = text_w - avail_w
        else:
            self._scroll_x = 0

    def _notify_change(self):
        if self._state:
            self._state.value = self.text_val
        if self.on_change:
            self.on_change(self.text_val)
        self._update_scroll_x()
            
    def render(self, surface: pygame.Surface):
        rx, ry = self.rect.left, self.rect.top
        w, h = self.rect.width, self.rect.height
        
        # Determine background color and borders based on theme
        bg_col = iOSTheme.secondary_background
        border_col = iOSTheme.fill_tertiary
        
        # Draw dynamic focused border using focus_ring spring
        t = self.focus_ring
        if t > 0.01:
            # Interpolate focus color towards primary accent
            focus_col = iOSTheme.accent
            r = int(border_col.r + (focus_col.r - border_col.r) * t)
            g = int(border_col.g + (focus_col.g - border_col.g) * t)
            b = int(border_col.b + (focus_col.b - border_col.b) * t)
            border_col = pygame.Color(
                max(0, min(255, r)),
                max(0, min(255, g)),
                max(0, min(255, b))
            )
            
        # Draw background and base border
        pygame.draw.rect(surface, bg_col, self.rect, border_radius=8)
        pygame.draw.rect(surface, border_col, self.rect, width=2 if t > 0.1 else 1, border_radius=8)
        
        # Render Text or Placeholder
        font = self._get_font()
        if len(self.text_val) == 0 and not self.is_focused:
            text_surf = font.render(self.placeholder, True, iOSTheme.secondary_label)
        else:
            text_surf = font.render(self.text_val, True, iOSTheme.label)
            
        # Clip text to the inner field area so it never bleeds past the border
        pad = 12
        text_clip = pygame.Rect(rx + pad, ry, w - pad * 2, h)
        old_clip = surface.get_clip()
        surface.set_clip(text_clip.clip(old_clip) if old_clip.width > 0 else text_clip)

        # Apply horizontal scroll offset so cursor stays in view
        text_x = rx + pad - self._scroll_x
        text_rect = text_surf.get_rect(left=text_x, centery=ry + h // 2)
        surface.blit(text_surf, text_rect)

        # Draw cursor if focused and blink state is visible
        if self.is_focused and self.cursor_visible:
            cursor_x = rx + pad + text_surf.get_width() - self._scroll_x
            if len(self.text_val) == 0:
                cursor_x = rx + pad
            cursor_y1 = ry + h // 2 - 10
            cursor_y2 = ry + h // 2 + 10
            pygame.draw.line(surface, iOSTheme.accent, (cursor_x, cursor_y1), (cursor_x, cursor_y2), 2)

        surface.set_clip(old_clip)
