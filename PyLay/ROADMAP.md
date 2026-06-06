# PyLay — Road to Community-Ready

A full analysis of what's needed to make PyLay look better than it does today, perform at its ceiling, and be shippable as a community library. Organized by impact.

---

## Visual Quality

### 1. Anti-aliased rounded rectangles
pygame's `draw.rect(..., border_radius=...)` is not anti-aliased. Every rounded corner has staircase edges — the most visible difference between PyLay and native UI.

**Fix:** Pre-render shapes at 2× resolution, then `smoothscale` down. `smoothscale` does bilinear filtering which approximates AA on edges. Cost: one extra surface per widget at creation time, zero per frame.

```python
# In Button._get_base_surf — render at 2x, scale to 1x
surf_2x = pygame.Surface((w*2, h*2), pygame.SRCALPHA)
pygame.draw.rect(surf_2x, bg, (0, 0, w*2, h*2), border_radius=rad*2)
surf = pygame.transform.smoothscale(surf_2x, (w, h))
```

---

### 2. Drop shadows
Apple uses Gaussian-blurred shadows on cards, buttons, slider knobs, and segmented control pills. pygame has no blur primitive.

**Fix:** Multi-layered fake shadow — 4–5 stacked rects at increasing offsets with decreasing alpha. Pre-rendered at widget construction into a shadow surface, cached, and blitted 2px behind the widget.

```python
def make_shadow(w, h, radius, blur=6, color=(0, 0, 0)):
    surf = pygame.Surface((w + blur*2, h + blur*2), pygame.SRCALPHA)
    for i in range(blur, 0, -1):
        alpha = int(80 * (i / blur) ** 1.5)
        pygame.draw.rect(surf, (*color, alpha),
            (blur - i, blur - i + 2, w + i*2, h + i*2),
            border_radius=radius + i)
    return surf
```

Cache this at construction. The result reads as a real soft shadow.

---

### 3. Bundle Inter font
SF Pro is on macOS only. Arial looks noticeably different — especially at small sizes. Bundling **Inter** (open-source, designed to match SF Pro's metrics) guarantees identical rendering on every platform.

```python
# Load from package assets instead of SysFont:
self._font = pygame.font.Font("assets/Inter-Regular.ttf", px)
```

Platform fallback alternative: SF Pro on macOS, Segoe UI on Windows, Ubuntu/Noto on Linux.

---

### 4. Button press scale too aggressive
`target_scale = 0.92` reads as cartoony. Apple's UIKit press scale is `0.97` — barely perceptible, just enough to feel responsive.

**Fix:** Change `0.92` → `0.96` in `button.py`.

---

### 5. Slider knob shadow
The knob currently has a 1px `(180,180,180)` border. Apple's knob has a drop shadow giving it a lifted feel.

**Fix:** Draw a slightly larger dark circle 1px below before drawing the white circle:

```python
pygame.draw.circle(surface, pygame.Color(160, 160, 160), (knob_cx, knob_cy + 1), knob_r + 1)
pygame.draw.circle(surface, pygame.Color(255, 255, 255), (knob_cx, knob_cy), knob_r)
```

---

### 6. Gradient fills
Apple buttons and surfaces use very subtle top-to-bottom gradients (~4% lightness shift). Not visible at first glance but adds perceived depth.

**Fix:** Pre-generate gradient surfaces at widget construction using numpy. Cache them.

```python
import numpy as np

def make_gradient_surf(w, h, color_top, color_bot):
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    for y in range(h):
        t = y / max(1, h - 1)
        arr[y, :] = [int(color_top[i] + (color_bot[i] - color_top[i]) * t) for i in range(4)]
    return pygame.surfarray.make_surface(arr.swapaxes(0, 1))
```

---

### 7. Icon system
The bottom bar fallback is a dot/ring. Real apps need icons. Best option: bundle **Ionicons** or **Feather Icons** as a TTF font and render icon glyphs exactly like text — scalable, AA-rendered, zero extra surface allocations.

```python
icon_font = pygame.font.Font("assets/ionicons.ttf", 24)
icon_surf = icon_font.render("", True, color)  # home icon
```

---

## Performance

### 8. Dirty rect rendering — biggest available win
Every frame does `screen.fill(bg)` + full tree redraw + `pygame.display.flip()`. On a 1080p window at 60fps you're pushing megabytes of pixel data even when nothing changes.

**Fix:** Track a `_dirty` flag on `UIElement`. Set it when any visual property changes. Collect dirty rects during draw. Call `pygame.display.update(dirty_rects)` instead of `flip()`.

```python
# In App.frame():
dirty_rects = []
self.root.draw(self.screen, dirty_rects)
if dirty_rects:
    pygame.display.update(dirty_rects)
# else: skip flip entirely — nothing changed
```

For a settings page where nothing is animating, this drops GPU/CPU to near zero.

---

### 9. Layer caching for static subtrees
A `VStack` of `Label`s that never change re-renders every frame. Add a `cache_as_layer = True` parameter to layouts — the layout renders children to a private `pygame.Surface` once, then just blits that surface every subsequent frame until a child sets `_dirty = True`.

---

### 10. `_shift_tree` — O(n) rect mutation per frame for scrolling
`layout.py` currently shifts every child rect by the scroll offset before drawing and shifts it back afterward. For a list with 50 items that is 100 rect mutations per frame, every frame, even when the user is not scrolling.

**Fix:** Pass a draw offset through the draw call chain instead of mutating rects. Children draw at `(rect.x, rect.y - scroll_offset)` without ever moving their canonical rects.

---

### 11. Full root re-layout on every settling spring
When a layout-spec spring snaps to its target, `element.py` calls `self.get_root().layout()` — walking the entire tree from root. If multiple springs settle in the same frame, you get multiple full re-layouts.

**Fix:** Collect a `_layout_dirty` flag during `update()`, then do one layout pass at the end of `App.frame()`:

```python
# In App.frame(), after root.update(dt):
if self._layout_dirty:
    self.root.layout(self.screen.get_rect())
    self._layout_dirty = False
```

---

### 12. `update()` recurses invisible subtrees
Children are updated unconditionally even if invisible and have no active animations. Add early-out: if a subtree has no active animations and is invisible, skip it. A `_subtree_has_animations` flag that bubbles up from children makes entire branches prunable.

---

### 13. Label/TextField font surface cached per frame
Widgets that render the same text every frame re-call `font.render()` every frame. Add a `(text, color_tuple, font_px)` → `Surface` cache on the widget instance. One dict lookup per frame vs. a full glyph rasterization pass.

---

### 14. `list(self._active_animations.keys())` allocation per frame
`element.py` creates a new list every frame for every animated element. Replace with a staged delete:

```python
to_delete = []
for prop, spring in self._active_animations.items():
    spring.update(dt)
    setattr(self, prop, spring.value)
    if abs(spring.value - spring.target) < 1e-4 and abs(spring.velocity) < 1e-3:
        to_delete.append(prop)
for prop in to_delete:
    del self._active_animations[prop]
```

---

### 15. Event dispatch is a linear full scan
Every mouse event walks `reversed(self.children)` at every level. Add a fast path: skip children whose rect doesn't intersect the event position before recursing.

---

## Correctness / Architecture

### 16. TextField text overflow
When typed text is wider than the field it bleeds past the border — no clipping, no horizontal scroll. Fix: clip the rendered text surface to `(w - 24)px` and implement a `scroll_x` offset that tracks the cursor position.

---

### 17. `BottomNavigationBar` spring hack is fragile
`animate_to(f"tab_scales[{n}]")` with `__getattr__`/`__setattr__` works but is a landmine — any attribute access matching `tab_scale_*` silently misbehaves. Replace with a proper list of `Spring` objects driven directly in `update()`.

---

### 18. No Modal/Dialog widget
Every real-world app needs modals. Should be a `FloatLayout` that renders on top of everything with a darkened overlay background, centered on screen, with `clips_to_bounds = False` to exceed parent bounds.

---

### 19. No Image widget
Wrapping `pygame.image.load()` + `pygame.transform.smoothscale()` with caching into a proper `Image(path, width, height)` widget is table stakes for community use.

---

## Packaging

### 20. Not pip-installable
The library is a bare folder. Needs a `pyproject.toml` with `[build-system]` and `[project]` sections so users can `pip install pylay`.

### 21. No `py.typed` marker
Without a zero-byte `py.typed` file in the package root, mypy and IDEs won't offer autocomplete for library users. Add it.

### 22. Semver + CHANGELOG + README
- `__version__ = "0.1.0"` in `__init__.py`
- A README with installation instructions and 3–5 code examples
- A CHANGELOG for tracking releases

### 23. No test suite
Even basic tests covering layout math, spring physics convergence, and event routing let you catch regressions before releases. `pytest` + `pygame` headless mode works fine.

---

## Priority Stack

| # | Task | Effort | Impact |
|---|---|---|---|
| 1 | Bundle Inter font, load via `Font(path)` | 30 min | High visual |
| 2 | Button press scale `0.92` → `0.96` | 2 min | Medium feel |
| 3 | Fake shadow surfaces (cards, slider knob) | 2 hrs | High visual |
| 4 | 2× smoothscale AA for rounded rects | 3 hrs | High visual |
| 5 | Dirty rect rendering in `App.frame()` | 4 hrs | Huge perf |
| 6 | Fix `_shift_tree` scroll rendering | 2 hrs | Medium perf |
| 7 | Label text surface cache | 1 hr | Medium perf |
| 8 | TextField overflow clip + cursor scroll | 3 hrs | Correctness |
| 9 | Layer caching for static layouts | 4 hrs | Large perf |
| 10 | Icon font system (Ionicons TTF) | 2 hrs | High visual |
| 11 | `pyproject.toml` + `py.typed` + README | 1 hr | Community |
| 12 | Modal widget | 3 hrs | Feature gap |
| 13 | Gradient surfaces via numpy | 2 hrs | Polish |
| 14 | Single-layout-pass on spring settle | 2 hrs | Perf |
| 15 | Prune invisible/idle subtrees in `update()` | 2 hrs | Perf |

Items 1–5 alone bring the visuals and performance to a noticeably different level. Items 1–11 constitute a shippable v0.1.
