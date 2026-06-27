import pygame
from pylay.layouts.float_layout import FloatLayout
from pylay.core.element import UIElement
from typing import Dict, Callable, Optional, Union

class PageRouter(FloatLayout):
    def __init__(self,
                 pages: Optional[Dict[str, Callable[[], UIElement]]] = None,
                 pages_registry: Optional[Dict[str, Callable[[], UIElement]]] = None,
                 initial_page: str = "",
                 anchor: str = "top_left",
                 x: Union[int, float] = 0,
                 y: Union[int, float] = 0,
                 width: Union[int, float] = 1.0,
                 height: Union[int, float] = 1.0,
                 **kwargs):
        super().__init__(anchor=anchor, x=x, y=y, width=width, height=height,
                         background_color=pygame.Color(0,0,0,0), **kwargs)
        self.manages_own_scroll = True

        registry = pages if pages is not None else pages_registry
        if registry is None:
            raise TypeError("PageRouter requires 'pages' or 'pages_registry'")
        self.pages_registry = registry
        self.active_page_name: Optional[str] = None
        self.active_page: Optional[UIElement] = None
        self.exiting_page: Optional[UIElement] = None

        # Slide-transition alpha springs (used by navigate)
        self.entering_fade = 1.0
        self.exiting_fade  = 0.0

        # Morphic-transition state (used by refresh)
        self._refresh_mode   = False
        self._enter_scale    = 1.0   # animated 0.95 → 1.0 on refresh enter
        self._exit_alpha     = 1.0   # animated 1.0 → 0.0 on refresh exit

        self._deferred_reload = 0.0  # countdown in seconds; fires reload when it hits 0

        self.navigate(initial_page, animated=False)

    def reload_current_page(self, delay: float = 0.0):
        if delay > 0.0:
            self._deferred_reload = max(self._deferred_reload, delay)
            return
        if not self.active_page_name:
            return
        if self.exiting_page:
            self.remove_child(self.exiting_page)
            self.exiting_page = None
        if self.active_page:
            self.remove_child(self.active_page)
        builder = self.pages_registry[self.active_page_name]
        self.active_page = builder()
        self.active_page.x_spec    = 0.0
        self.active_page.y_spec    = 0.0
        self.active_page.width_spec  = 1.0
        self.active_page.height_spec = 1.0
        self.add_child(self.active_page)
        # Kill any in-flight transition springs so the page appears instantly
        for key in ("entering_fade", "exiting_fade", "_enter_scale", "_exit_alpha"):
            self._active_animations.pop(key, None)
        self.entering_fade = 1.0
        self.exiting_fade  = 0.0
        self._refresh_mode = False
        self._enter_scale  = 1.0
        self._exit_alpha   = 1.0
        self.get_root().layout()

    def refresh(self):
        if not self.active_page_name:
            self.reload_current_page()
            return

        # Abort any pending slide transition
        if self.exiting_page:
            self.remove_child(self.exiting_page)
            self.exiting_page = None

        # Park the current page as exiting; fade it out in place (no slide)
        if self.active_page:
            self.exiting_page = self.active_page
            self._exit_alpha  = 1.0
            self.animate_to("_exit_alpha", 0.0, response=0.28, damping_fraction=0.90)

        # Build fresh page
        builder = self.pages_registry[self.active_page_name]
        self.active_page = builder()
        self.active_page.x_spec    = 0.0
        self.active_page.y_spec    = 0.0
        self.active_page.width_spec  = 1.0
        self.active_page.height_spec = 1.0
        self.add_child(self.active_page)

        # Enter: scale 0.95 → 1.0 with a lively underdamped spring + fade in
        self._enter_scale  = 0.95
        self.entering_fade = 0.0
        self.animate_to("_enter_scale",  1.0, response=0.40, damping_fraction=0.72)
        self.animate_to("entering_fade", 1.0, response=0.28, damping_fraction=0.90)

        self._refresh_mode = True
        self.get_root().layout()

    def navigate(self, page_name: str, direction: str = "auto", animated: bool = True):
        if page_name not in self.pages_registry:
            print(f"[PageRouter] Warning: Page '{page_name}' not found in registry.")
            return
        if page_name == self.active_page_name:
            return

        if self.exiting_page:
            self.remove_child(self.exiting_page)
            self.exiting_page = None

        if not animated:
            if self.active_page:
                self.remove_child(self.active_page)
            self.active_page_name = page_name
            self.active_page = self.pages_registry[page_name]()
            self.active_page.x_spec     = 0.0
            self.active_page.y_spec     = 0.0
            self.active_page.width_spec  = 1.0
            self.active_page.height_spec = 1.0
            self.add_child(self.active_page)
            for key in ("entering_fade", "exiting_fade", "_enter_scale", "_exit_alpha"):
                self._active_animations.pop(key, None)
            self.entering_fade = 1.0
            self.exiting_fade  = 0.0
            self._refresh_mode = False
            self._enter_scale  = 1.0
            self._exit_alpha   = 1.0
            return

        if direction == "auto":
            if self.active_page_name in self.pages_registry and page_name in self.pages_registry:
                keys = list(self.pages_registry.keys())
                direction = "right" if keys.index(page_name) >= keys.index(self.active_page_name) else "left"
            else:
                direction = "right"

        if self.active_page:
            self.exiting_page = self.active_page
            exit_target_x = -0.3 if direction == "right" else 1.0
            self.exiting_page.animate_to("x_spec", exit_target_x, response=0.35, damping_fraction=0.85)
            self.exiting_fade = 1.0
            self.animate_to("exiting_fade", 0.0, response=0.35, damping_fraction=0.85)

        self.active_page_name = page_name
        self.active_page = self.pages_registry[page_name]()

        entry_start_x = 1.0 if direction == "right" else -0.3
        self.active_page.x_spec     = entry_start_x
        self.active_page.y_spec     = 0.0
        self.active_page.width_spec  = 1.0
        self.active_page.height_spec = 1.0
        self.add_child(self.active_page)

        self.active_page.animate_to("x_spec", 0.0, response=0.35, damping_fraction=0.85)
        self.entering_fade = 0.0
        self.animate_to("entering_fade", 1.0, response=0.35, damping_fraction=0.85)

        self._refresh_mode = False
        self._enter_scale  = 1.0
        self._exit_alpha   = 1.0

    def update(self, dt: float):
        if self._deferred_reload > 0.0:
            self._deferred_reload -= dt
            if self._deferred_reload <= 0.0:
                self._deferred_reload = 0.0
                self.reload_current_page()  # delay=0, fires immediately
                return  # tree was rebuilt; skip stale super().update

        super().update(dt)

        if self.exiting_page:
            if self._refresh_mode:
                # Refresh mode: GC when exit fade has fully dissolved
                if self._exit_alpha < 0.02 and "_exit_alpha" not in self._active_animations:
                    self.remove_child(self.exiting_page)
                    self.exiting_page = None
            else:
                # Slide mode: GC when x_spec spring has settled
                self.exiting_page.update(dt)
                spring = self.exiting_page._active_animations.get("x_spec")
                if spring is None or abs(self.exiting_page.x_spec - spring.target) < 0.01:
                    self.remove_child(self.exiting_page)
                    self.exiting_page = None

    def _draw_page_with_alpha(self, surface: pygame.Surface, page: UIElement, alpha_factor: float):
        alpha = max(0, min(255, int(255 * alpha_factor)))
        if alpha <= 1:
            return
        if alpha >= 254:
            page.draw(surface)
            return
        sw, sh = surface.get_size()
        if not hasattr(self, "_temp_surf") or self._temp_surf.get_size() != (sw, sh):
            self._temp_surf = pygame.Surface((sw, sh), pygame.SRCALPHA)
        temp = self._temp_surf
        temp.fill((0, 0, 0, 0))
        page.draw(temp)
        temp.set_alpha(alpha)
        surface.blit(temp, (0, 0))

    def _draw_page_morphic(self, surface: pygame.Surface, page: UIElement,
                           alpha_factor: float, scale: float):
        alpha = max(0, min(255, int(255 * alpha_factor)))
        if alpha <= 1:
            return
        rw, rh = self.rect.width, self.rect.height
        if rw <= 0 or rh <= 0:
            return

        # Fast path — no transform
        if alpha >= 254 and abs(scale - 1.0) < 0.003:
            page.draw(surface)
            return

        sw, sh = surface.get_size()
        if not hasattr(self, "_temp_surf") or self._temp_surf.get_size() != (sw, sh):
            self._temp_surf = pygame.Surface((sw, sh), pygame.SRCALPHA)
        temp = self._temp_surf
        temp.fill((0, 0, 0, 0))
        page.draw(temp)

        if abs(scale - 1.0) < 0.003:
            temp.set_alpha(alpha)
            surface.blit(temp, (0, 0))
            return

        # Scale the router's region around its centre
        clip = self.rect.clip(temp.get_rect())
        if clip.width <= 0 or clip.height <= 0:
            return
        new_w = max(1, int(rw * scale))
        new_h = max(1, int(rh * scale))
        scaled_surf = pygame.transform.smoothscale(temp.subsurface(clip), (new_w, new_h))
        scaled_surf.set_alpha(alpha)
        cx, cy = self.rect.centerx, self.rect.centery
        surface.blit(scaled_surf, (cx - new_w // 2, cy - new_h // 2))

    def draw(self, surface: pygame.Surface):
        old_clip = surface.get_clip()
        new_clip = self.rect.clip(old_clip) if old_clip.width > 0 else self.rect
        surface.set_clip(new_clip)

        if self._refresh_mode:
            # Morphic: exiting dissolves in place, entering scales+fades in
            if self.exiting_page and self.exiting_page.visible:
                self._draw_page_with_alpha(surface, self.exiting_page, self._exit_alpha)
            if self.active_page and self.active_page.visible:
                self._draw_page_morphic(surface, self.active_page,
                                        self.entering_fade, self._enter_scale)
        else:
            # Slide: parallax exit then enter
            if self.exiting_page and self.exiting_page.visible:
                self._draw_page_with_alpha(surface, self.exiting_page, self.exiting_fade)
            if self.active_page and self.active_page.visible:
                self._draw_page_with_alpha(surface, self.active_page, self.entering_fade)

        surface.set_clip(old_clip)
