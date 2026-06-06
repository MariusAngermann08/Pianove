import pygame
from pylay.layouts.float_layout import FloatLayout
from pylay.layouts.list_layout import VStack
from pylay.core.theme import iOSTheme
from pylay.core.state import State
from pylay.widgets.button import Button
from pylay.widgets.label import Label
from typing import Optional, Union, Any, List

class SidebarDrawer(FloatLayout):
    """
    A slide-out side menu navigation drawer.
    Slides in from the left edge using smooth spring translation and
    fades in a touch-intercepting backdrop overlay to focus interaction.
    Unloads event handling when closed to optimize performance.
    """
    def __init__(self,
                 open_state: State,
                 width: Union[int, float] = 280,
                 active_tab_state: Optional[State] = None,
                 tabs: Optional[List[str]] = None,
                 anchor: str = "top_left",
                 **kwargs):
        # We start aligned left off-screen by default (x = -width)
        super().__init__(anchor=anchor, x=-width, y=0, width=width, height=1.0, 
                         background_color=iOSTheme.secondary_background, 
                         border_radius=0, **kwargs)
        
        self.open_state = open_state
        self.active_tab_state = active_tab_state
        self.drawer_width = width
        
        self.open_state.bind(self._on_state_update)
        self.is_open = bool(self.open_state.value)

        if tabs and active_tab_state is not None:
            menu = VStack(spacing=14, padding=20, anchor="top_left", x=0, y=64, width=1.0, height=0.8)
            menu.add_child(Label(text="NAVIGATION MENU", font_size=12, bold=True, color=iOSTheme.secondary_label))
            for i, title in enumerate(tabs):
                def make_handler(tab_index: int):
                    def handler():
                        self.slide_progress = 0.0
                        self.visible = False
                        self.open_state.value = False
                        self.active_tab_state.value = tab_index
                    return handler
                menu.add_child(Button(text=title, on_click=make_handler(i), width=0.9, height=42))
            self.add_child(menu)
        
        # Animatable slide offset (0.0 = fully closed/offscreen, 1.0 = fully open/onscreen)
        self.slide_progress = 1.0 if self.is_open else 0.0
        self._last_open = self.is_open
        self.visible = self.is_open
        self._last_layout_x: int = int(-self.drawer_width * (0 if self.is_open else 1))
        
    def _on_state_update(self, val: Any):
        self.is_open = bool(val)
        # Make visible immediately on open so update() isn't skipped due to
        # the "invisible + no active animations" early-out in element.py.
        if self.is_open:
            self.visible = True
        
    def update(self, dt: float):
        if self.is_open != self._last_open:
            target = 1.0 if self.is_open else 0.0
            self.animate_to("slide_progress", target, response=0.28, damping_fraction=0.82)
            self._last_open = self.is_open
            
        super().update(dt)

        # Update self position based on slide spring progress
        # x_spec maps: 0.0 (closed) -> -drawer_width, 1.0 (open) -> 0
        t = self.slide_progress
        new_x = int(-self.drawer_width * (1.0 - t))
        self.x_spec = new_x

        # Make drawer invisible when completely closed to skip draw ticks
        self.visible = (t > 0.001)

        # Only trigger a layout when the integer pixel position actually changes
        if new_x != self._last_layout_x:
            self._last_layout_x = new_x
            self.request_layout()
        
    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self.visible:
            return False
            
        # If open, the semi-translucent dimming backdrop covers the rest of the screen.
        # Clicking outside the sidebar rect will close the drawer reactively!
        if self.is_open and event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if not self.rect.collidepoint(event.pos):
                self.open_state.value = False
                return True # Intercept click
                
        # Delegate event to children inside the drawer
        return super().handle_event(event)
        
    def draw(self, surface: pygame.Surface):
        if not self.visible:
            return
            
        # 1. Draw dimming backdrop overlay on the rest of the screen (behind drawer)
        t = self.slide_progress
        if t > 0.01:
            dim_alpha = int(t * 110) # Max 43% dimming opacity
            backdrop_col = pygame.Color(0, 0, 0, dim_alpha)
            
            # Temporary full-screen surface for alpha dimming
            scr_rect = surface.get_rect()
            backdrop = pygame.Surface(scr_rect.size, pygame.SRCALPHA)
            backdrop.fill(backdrop_col)
            
            # Clip drawing to exclude the drawer rect itself
            surface.blit(backdrop, (0, 0))
            
        # 2. Draw sidebar itself
        super().draw(surface)
