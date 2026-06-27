import pygame
from pylay.core.element import UIElement
from pylay.core.theme import iOSTheme
from pylay.core.scale import scaled_font_size, scaled_px
from pylay.core import font_loader
from typing import Optional, List, Union

class Label(UIElement):
    def __init__(self,
                 text: Union[str, 'State'],
                 font_size: int = 16,
                 font_name: str = "Arial",
                 color: Optional[pygame.Color] = None,
                 bold: bool = False,
                 wrap_width: Optional[int] = None,
                 anchor: str = "top_left",
                 **kwargs):
        super().__init__(anchor=anchor, **kwargs)
        
        self.font_size = font_size
        self.font_name = font_name
        self.color = color
        self.bold = bold
        self.wrap_width = wrap_width
        self._font: Optional[pygame.font.Font] = None
        self._font_px: int = 0
        self._wrapped_lines: List[str] = []
        # Text surface cache: (line_text, color_rgba, font_px) -> Surface
        self._text_surf_cache: dict = {}
        
        # State binding
        self._state = None
        if hasattr(text, "bind"):
            self._state = text
            self.text = str(text.value)
            text.bind(self._on_state_update)
        else:
            self.text = str(text)

    def _on_state_update(self, val):
        new_text = str(val)
        if new_text == self.text:
            return
        self.text = new_text
        # Only trigger a full root re-layout when the label's rendered size actually changes.
        # Labels with explicit int/float size specs (set by the user) keep the same rect regardless
        # of text content, so no re-layout is needed for those — just a redraw.
        font = self._get_font()
        if self.wrap_width is not None:
            # Wrapped label: line count can change, so always re-layout
            self.get_root().layout()
        else:
            new_w, new_h = font.size(new_text)
            if new_w != self.rect.width or new_h != self.rect.height:
                self.get_root().layout()



    def _on_scale_changed(self):
        self._font = None
        self._font_px = 0
        self._text_surf_cache.clear()

    def _on_theme_changed(self):
        self._text_surf_cache.clear()

    def _get_font(self) -> pygame.font.Font:
        px = scaled_font_size(self.font_size)
        if self._font is None or self._font_px != px:
            override = self.font_name if self.font_name != "Arial" else None
            self._font = font_loader.load_font(self.font_size, bold=self.bold, override_name=override)
            self._font_px = px
        return self._font

    def _perform_word_wrap(self, font: pygame.font.Font, max_width: int) -> List[str]:
        # Split into explicit paragraphs first
        paragraphs = self.text.split('\n')
        wrapped_lines = []
        
        for para in paragraphs:
            if not para:
                # Retain empty lines for paragraph gaps
                wrapped_lines.append("")
                continue
                
            words = para.split(' ')
            current_line = []
            
            for word in words:
                test_line = ' '.join(current_line + [word]) if current_line else word
                if font.size(test_line)[0] <= max_width:
                    current_line.append(word)
                else:
                    if current_line:
                        wrapped_lines.append(' '.join(current_line))
                    current_line = [word]
                    
            if current_line:
                wrapped_lines.append(' '.join(current_line))
                
        return wrapped_lines

    def layout(self, parent_rect: Optional[pygame.Rect] = None, skip_self: bool = False):
        if not skip_self:
            font = self._get_font()
            
            # If wrap width is set, compute multiline wrapping
            wrap = self.wrap_width
            if wrap is not None and wrap > 0:
                wrap = scaled_px(int(wrap))
                self._wrapped_lines = self._perform_word_wrap(font, wrap)
                
                # Solve bounds based on lines
                line_height = font.get_linesize()
                total_h = len(self._wrapped_lines) * line_height
                
                self.width_spec = wrap
                self.height_spec = total_h
            else:
                self._wrapped_lines = [self.text]
                w, h = font.size(self.text)
                self.width_spec = w
                self.height_spec = h
            
        super().layout(parent_rect, skip_self=skip_self)

    def render(self, surface: pygame.Surface):
        if not self.visible:
            return
            
        color = self.color if self.color is not None else iOSTheme.label
        font = self._get_font()
        line_height = font.get_linesize()
        
        for idx, line in enumerate(self._wrapped_lines):
            if not line:
                continue
            # Cache rendered text surfaces — avoids rasterization on unchanged frames
            col_key = color.r, color.g, color.b, color.a if hasattr(color, 'a') else 255
            cache_key = (line, col_key, self._font_px)
            text_surf = self._text_surf_cache.get(cache_key)
            if text_surf is None:
                text_surf = font.render(line, True, color)
                self._text_surf_cache[cache_key] = text_surf
            dest_pos = (self.rect.left, self.rect.top + idx * line_height)
            surface.blit(text_surf, dest_pos)
