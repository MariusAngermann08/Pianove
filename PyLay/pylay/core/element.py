import pygame
from typing import List, Optional, Tuple, Union
from pylay.core.physics import Spring

class UIElement:
    """
    Base UI Element for OpenUI.
    Handles hierarchy, responsive layout solving, event dispatching,
    and physics-based property animations.
    """
    def __init__(self,
                 anchor: str = "top_left",
                 x: Union[int, float] = 0,
                 y: Union[int, float] = 0,
                 width: Union[int, float] = 100,
                 height: Union[int, float] = 100,
                 visible: bool = True,
                 enabled: bool = True):
        self.parent: Optional['UIElement'] = None
        self.children: List['UIElement'] = []

        self.anchor = anchor.lower()
        self.x_spec = x
        self.y_spec = y
        self.width_spec = width
        self.height_spec = height

        self.rect = pygame.Rect(0, 0, 100, 100)

        self.visible = visible
        self.enabled = enabled

        # {property_name: Spring}
        self._active_animations: dict = {}

        # Clip children to self.rect during draw
        self.clips_to_bounds = False

    # ------------------------------------------------------------------
    # Hierarchy
    # ------------------------------------------------------------------
    def add_child(self, child: 'UIElement'):
        if child.parent:
            child.parent.remove_child(child)
        child.parent = self
        self.children.append(child)
        self.layout()

    def remove_child(self, child: 'UIElement'):
        if child in self.children:
            self.children.remove(child)
            child.parent = None
            self.layout()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------
    def get_root(self) -> 'UIElement':
        curr = self
        while curr.parent is not None:
            curr = curr.parent
        return curr

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------
    def layout(self, parent_rect: Optional[pygame.Rect] = None, skip_self: bool = False):
        """Solve constraints → self.rect, then propagate to children."""
        if not skip_self:
            if parent_rect is not None:
                p_rect = parent_rect
            elif self.parent is not None:
                p_rect = self.parent.rect
            else:
                surface = pygame.display.get_surface()
                p_rect = surface.get_rect() if surface else pygame.Rect(0, 0, 800, 600)

            # Resolve size
            pw, ph = p_rect.width, p_rect.height
            w = int(self.width_spec  * pw) if isinstance(self.width_spec,  float) else int(self.width_spec)
            h = int(self.height_spec * ph) if isinstance(self.height_spec, float) else int(self.height_spec)
            # Clamp to sane minimum to avoid zero-size surface crashes
            w = max(1, w)
            h = max(1, h)

            # Resolve anchor point
            a = self.anchor
            if "center" in a:
                anchor_x = p_rect.left + pw // 2
                anchor_y = p_rect.top  + ph // 2
            else:
                anchor_x = p_rect.right  if "right"  in a else (p_rect.left + pw // 2 if "left"   not in a else p_rect.left)
                anchor_y = p_rect.bottom if "bottom" in a else (p_rect.top  + ph // 2 if "top"    not in a else p_rect.top)

            # Resolve offset
            ox = int(self.x_spec * pw) if isinstance(self.x_spec, float) else int(self.x_spec)
            oy = int(self.y_spec * ph) if isinstance(self.y_spec, float) else int(self.y_spec)

            fx = anchor_x + ox
            fy = anchor_y + oy

            if "center" in a:
                self.rect.update(fx - w // 2, fy - h // 2, w, h)
            else:
                lx = fx - w if "right"  in a else (fx - w // 2 if "left"   not in a else fx)
                ty = fy - h if "bottom" in a else (fy - h // 2 if "top"    not in a else fy)
                self.rect.update(lx, ty, w, h)

        # Propagate to children
        for child in self.children:
            child.layout(self.rect)

    # ------------------------------------------------------------------
    # Update / Animation
    # ------------------------------------------------------------------
    def update(self, dt: float):
        """Advance spring animations, then update children."""
        if not self.visible:
            if not self._active_animations:
                return

        layout_needed = False

        if self._active_animations:
            for prop in list(self._active_animations.keys()):
                spring = self._active_animations[prop]
                old_val = getattr(self, prop)

                spring.update(dt)
                new_val = spring.value
                setattr(self, prop, new_val)

                # Trigger layout solving if layout specs move
                if prop in ("x_spec", "y_spec", "width_spec", "height_spec"):
                    val_diff = abs(new_val - old_val)
                    if isinstance(old_val, float) or isinstance(new_val, float):
                        if val_diff > 1e-4:
                            layout_needed = True
                    elif val_diff > 0.5:
                        layout_needed = True

                # Snap and clean up settled springs
                if abs(spring.value - spring.target) < 1e-4 and abs(spring.velocity) < 1e-3:
                    setattr(self, prop, spring.target)
                    del self._active_animations[prop]
                    # Only layout-spec snaps need a reflow; visual springs (slider_index,
                    # scroll_offset, pill_y, etc.) settling must not trigger full layout.
                    if prop in ("x_spec", "y_spec", "width_spec", "height_spec"):
                        layout_needed = True

        if layout_needed:
            # Re-solve from the topmost root element downward to keep layout trees in perfect sync
            self.get_root().layout()

        for child in self.children:
            child.update(dt)

    def animate_to(self, property_name: str, target: float,
                   response: float = 0.35, damping_fraction: float = 0.7):
        """
        Animate a numeric property to a target using spring physics.
        Guards against no-op calls. Preserves momentum on retarget.
        """
        current_val = getattr(self, property_name, None)
        if current_val is None:
            setattr(self, property_name, target)
            return

        if property_name in self._active_animations:
            spring = self._active_animations[property_name]
            if spring.target == target:
                return   # Already heading there — no work needed
            spring.target = target
            spring.response = response
            spring.damping_fraction = damping_fraction
        else:
            if abs(current_val - target) < 1e-6:
                return   # Already at target — skip entirely
            spring = Spring(value=current_val, response=response,
                            damping_fraction=damping_fraction)
            spring.target = target
            self._active_animations[property_name] = spring

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------
    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self.visible or not self.enabled:
            return False
        for child in reversed(self.children):
            if child.handle_event(event):
                return True
        return self.on_event(event)

    def on_event(self, event: pygame.event.Event) -> bool:
        return False

    # ------------------------------------------------------------------
    # Draw
    # ------------------------------------------------------------------
    def draw(self, surface: pygame.Surface):
        if not self.visible:
            return
        self.render(surface)

        if self.clips_to_bounds:
            old_clip = surface.get_clip()
            new_clip = self.rect.clip(old_clip) if old_clip.width > 0 else self.rect
            surface.set_clip(new_clip)
            for child in self.children:
                child.draw(surface)
            surface.set_clip(old_clip)
        else:
            for child in self.children:
                child.draw(surface)

    def render(self, surface: pygame.Surface):
        pass

    def _on_theme_changed(self):
        """Clear widget-local caches after a global theme switch (override in subclasses)."""
        pass

    def invalidate_theme_caches(self):
        """Propagate theme invalidation through the element tree."""
        self._on_theme_changed()
        for child in self.children:
            child.invalidate_theme_caches()

    def _on_scale_changed(self):
        """Clear font/metric caches after window resize (override in subclasses)."""
        pass

    def invalidate_scale_caches(self):
        """Propagate scale invalidation so widgets rebuild fonts at new UI_SCALE."""
        self._on_scale_changed()
        for child in self.children:
            child.invalidate_scale_caches()

    def get_absolute_pos(self) -> Tuple[int, int]:
        return (self.rect.x, self.rect.y)
