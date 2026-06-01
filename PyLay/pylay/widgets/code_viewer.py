import pygame
from pylay.layouts.layout import Layout
from pylay.core.state import State
from typing import Union, List, Tuple, Optional

class CodeViewer(Layout):
    """
    A premium CodeViewer widget for OpenUI.
    Includes:
    - Real-time Lexical Syntax Highlighting for Python (Keywords, Strings, Comments, Numbers).
    - Left-hand side gutter for line numbering.
    - Inertia momentum scrolling and a sleek draggable scrollbar.
    - Rounded glass container box.
    """
    def __init__(self,
                 code_text: Union[str, State],
                 anchor: str = "top_left",
                 x: Union[int, float] = 0,
                 y: Union[int, float] = 0,
                 width: Union[int, float] = 500,
                 height: Union[int, float] = 300,
                 **kwargs):
        super().__init__(anchor=anchor, x=x, y=y, width=width, height=height, **kwargs)
        if isinstance(code_text, State):
            self.raw_code = str(code_text.value)
            code_text.bind(self._on_code_change)
        else:
            self.raw_code = str(code_text)
            
        self.lines = self.raw_code.splitlines()
        
        self.line_height = 20
        self._font = None
        self._font_gutter = None

        self.KEYWORDS = {
            "class", "def", "import", "from", "return", "self",
            "if", "else", "elif", "for", "while", "in", "and",
            "or", "not", "as", "try", "except", "lambda", "pass",
            "True", "False", "None", "global", "nonlocal", "with",
        }
        
    def _on_code_change(self, new_val):
        self.raw_code = str(new_val)
        self.lines = self.raw_code.splitlines()
        self.scroll_offset = 0.0
        self.scroll_target = 0.0
        self.layout()
        
    def _get_fonts(self) -> Tuple[pygame.font.Font, pygame.font.Font]:
        if self._font is None or self._font_gutter is None:
            if not pygame.font.get_init():
                pygame.font.init()
            # Use monospaced fonts for clean alignment
            monospace_fonts = ["Consolas", "Courier New", "Fira Code", "DejaVu Sans Mono", "Monospace", "Courier"]
            for f in monospace_fonts:
                try:
                    self._font = pygame.font.SysFont(f, 12, bold=False)
                    self._font_gutter = pygame.font.SysFont(f, 11, bold=True)
                    break
                except:
                    pass
            if self._font is None:
                self._font = pygame.font.Font(None, 12)
                self._font_gutter = pygame.font.Font(None, 11)
        return self._font, self._font_gutter

    def _tokenize_line(self, line: str) -> List[Tuple[str, pygame.Color]]:
        """
        Custom high-fidelity lexical parser for Python source code highlighting.
        Returns a list of (text_segment, color) tuples.
        """
        tokens = []
        i = 0
        n = len(line)
        
        # Color palette definitions for high-fidelity code theme
        color_normal = pygame.Color(220, 220, 225)
        color_keyword = pygame.Color(255, 117, 181) # Premium Magenta / Pink
        color_string = pygame.Color(166, 226, 46)   # Vivid Lime Green
        color_number = pygame.Color(253, 151, 31)   # Vibrant Orange
        color_comment = pygame.Color(117, 113, 94)  # Muted Sage/Gray
        color_builtin = pygame.Color(102, 217, 239) # Ice Blue for library types/names
        
        while i < n:
            # 1. Skip spaces but preserve them as normal tokens
            if line[i].isspace():
                spaces = ""
                while i < n and line[i].isspace():
                    spaces += line[i]
                    i += 1
                tokens.append((spaces, color_normal))
                continue
                
            # 2. Check for comments
            if line[i] == '#':
                tokens.append((line[i:], color_comment))
                break
                
            # 3. Check for string literals (double/single quotes)
            if line[i] in ("'", '"'):
                quote_char = line[i]
                str_lit = quote_char
                i += 1
                while i < n:
                    str_lit += line[i]
                    if line[i] == quote_char and line[i-1] != '\\':
                        i += 1
                        break
                    i += 1
                tokens.append((str_lit, color_string))
                continue
                
            # 4. Check for words (keywords, identifiers)
            if line[i].isalpha() or line[i] == '_':
                word = ""
                while i < n and (line[i].isalnum() or line[i] == '_'):
                    word += line[i]
                    i += 1
                
                # Highlight based on word content
                if word in self.KEYWORDS:
                    tokens.append((word, color_keyword))
                elif word[0].isupper() or word in ("print", "len", "max", "min", "int", "float", "str", "list", "dict", "set", "range", "abs", "round"):
                    tokens.append((word, color_builtin))
                else:
                    tokens.append((word, color_normal))
                continue
                
            # 5. Check for digits/numbers
            if line[i].isdigit():
                num = ""
                while i < n and (line[i].isdigit() or line[i] == '.'):
                    num += line[i]
                    i += 1
                tokens.append((num, color_number))
                continue
                
            # 6. Any other symbols (operators, brackets)
            tokens.append((line[i], color_normal))
            i += 1
            
        return tokens

    def _refresh_scroll_bounds(self):
        """Setup Layout boundaries for vertical scroll tracking."""
        total_h = len(self.lines) * self.line_height
        self.scroll_max = max(0.0, float(total_h - (self.rect.height - 24)))
        self.scroll_active = (self.scroll_max > 0.0)

    def layout(self, parent_rect: Optional[pygame.Rect] = None, skip_self: bool = False):
        super().layout(parent_rect, skip_self=skip_self)
        self._refresh_scroll_bounds()

    def render(self, surface: pygame.Surface):
        w, h = self.rect.width, self.rect.height
        if w <= 10 or h <= 10:
            return
            
        rx, ry = self.rect.left, self.rect.top
        
        # 1. Dark Glassmorphic Card Container Background
        bg_col = pygame.Color(30, 30, 35)
        pygame.draw.rect(surface, bg_col, self.rect, border_radius=12)
        
        # Accent glowing border
        border_col = pygame.Color(60, 60, 70)
        pygame.draw.rect(surface, border_col, self.rect, width=1, border_radius=12)
        
        # 2. Setup Font & Render Loops with clipping
        font_code, font_gutter = self._get_fonts()
        
        # Restrict drawing clips strictly to within the code container frame
        old_clip = surface.get_clip()
        inner_rect = pygame.Rect(rx + 2, ry + 12, w - 4, h - 24)
        new_clip = inner_rect.clip(old_clip) if old_clip.width > 0 else inner_rect
        surface.set_clip(new_clip)
        
        gutter_w = 34
        content_x = rx + gutter_w + 12
        
        # Draw background divider for Gutter line numbers
        pygame.draw.line(surface, pygame.Color(45, 45, 52), (rx + gutter_w, ry + 4), (rx + gutter_w, ry + h - 4), width=1)
        
        # Calculate viewport visible lines
        start_y = ry + 12
        line_offset = int(self.scroll_offset)
        
        for idx, line in enumerate(self.lines):
            ly = start_y + (idx * self.line_height) - line_offset
            
            # Skip drawing if lines reside completely outside our container viewport
            if ly + self.line_height < ry or ly > ry + h:
                continue
                
            # Draw Gutter line number
            num_text = f"{idx + 1:02d}"
            num_surf = font_gutter.render(num_text, True, pygame.Color(85, 85, 100))
            num_rect = num_surf.get_rect(right=rx + gutter_w - 8, centery=ly + self.line_height // 2)
            surface.blit(num_surf, num_rect)
            
            # Highlight and draw the source line
            tokens = self._tokenize_line(line)
            cx = content_x
            
            for text, color in tokens:
                if not text:
                    continue
                # Render token fragment
                token_surf = font_code.render(text, True, color)
                surface.blit(token_surf, (cx, ly + (self.line_height - token_surf.get_height()) // 2))
                cx += token_surf.get_width()
                
        # Restore outer canvas clipping rectangle
        surface.set_clip(old_clip)
        
        # 3. Draw animated Scrollbar track overlay
        if self.scroll_active:
            track_h = h - 24
            scrollbar_w = 6
            
            # Ratio of viewport vs full content
            total_content_h = len(self.lines) * self.line_height
            bar_h = max(20, int(track_h * (h / total_content_h)))
            
            # Bar placement
            bar_y = ry + 12 + int((self.scroll_offset / self.scroll_max) * (track_h - bar_h))
            bar_x = rx + w - scrollbar_w - 4
            
            # Drawing rounded indicator
            pygame.draw.rect(surface, pygame.Color(90, 90, 110, 150), (bar_x, bar_y, scrollbar_w, bar_h), border_radius=3)
