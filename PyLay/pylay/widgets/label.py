import pygame
from pylay.core.element import UIElement
from pylay.core.theme import iOSTheme
from pylay.core.scale import scaled_font_size, scaled_px
from typing import Optional, List, Union

class Label(UIElement):
    """
    A premium iOS-styled text Label.
    Supports single-line text and automatic multiline word wrapping (using wrap_width),
    recalculating exact layout constraints and anchors dynamically.
    """
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
        
        # State binding
        self._state = None
        if hasattr(text, "bind"):
            self._state = text
            self.text = str(text.value)
            text.bind(self._on_state_update)
        else:
            self.text = str(text)

    def _on_state_update(self, val):
        self.text = str(val)
        # Recalculate layout from the topmost root container downward to keep all widgets in perfect sync
        self.get_root().layout()



    def _on_scale_changed(self):
        self._font = None
        self._font_px = 0

    def _get_font(self) -> pygame.font.Font:
        px = scaled_font_size(self.font_size)
        if self._font is None or self._font_px != px:
            if not pygame.font.get_init():
                pygame.font.init()
            fonts_to_try = [self.font_name, "Segoe UI", "SF Pro Text", "Helvetica Neue", "Helvetica", "Arial"]
            for f in fonts_to_try:
                try:
                    self._font = pygame.font.SysFont(f, px, bold=self.bold)
                    break
                except Exception:
                    continue
            if self._font is None:
                self._font = pygame.font.Font(None, px)
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
            text_surf = font.render(line, True, color)
            # Offset vertical position of each line sequentially
            dest_pos = (self.rect.left, self.rect.top + idx * line_height)
            surface.blit(text_surf, dest_pos)
