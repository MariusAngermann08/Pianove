# PyLay — Performance & Scaling Audit

This document catalogues every known bottleneck in PyLay, explains why it happens, and lists the concrete fixes needed to reach stable 60 fps with smooth resizing and proper UI zoom.

---

## 1. Resize is laggy (40 ms debounce + synchronous full-tree work)

**Where:** `App.frame()` lines 159–168

```python
if self._pending_resize and (time.time() - self._resize_time) > 0.04:
    set_window_size(w, h, ...)
    self.root.invalidate_scale_caches()   # full tree traversal
    self.root.layout(self.screen.get_rect())  # full tree traversal
```

**Why it's slow:**
- The 40 ms debounce means the UI visibly freezes for one or two frames after the user stops dragging the window edge.
- `invalidate_scale_caches()` and `layout()` each walk every node in the tree synchronously on the same frame. For a deep page tree this can easily take 4–8 ms.
- The display surface is also re-created (`set_mode`) on the same frame.

**Fix:**
- Reduce debounce to ≤ 16 ms (one frame at 60 fps) or drop it entirely and handle `WINDOWRESIZED` immediately.
- Run `invalidate_scale_caches()` + `layout()` as a single combined traversal so the tree is only walked once, not twice.
- Mark a `_layout_dirty` flag rather than re-laying out immediately; the actual layout pass runs at the top of the next frame before drawing.

---

## 2. Full tree relayout triggered by almost everything

**Where:** `UIElement.add_child()`, `UIElement._on_state_update()` (Label), `UIElement.update()` (animated `height_spec`/`width_spec`), `PageRouter.refresh()`, `PageRouter.reload_current_page()`

Every one of these calls `self.get_root().layout()`, which crawls the **entire** tree from root downward regardless of what actually changed.

**Why it matters:**
Building Pianove's home page adds ~60 children across nested VStacks and FloatLayouts. Each `add_child()` triggers a full layout → 60 full traversals just to construct the page. During a navigation transition, two pages are live simultaneously, doubling the cost.

**Fix (three-level approach):**
1. **Batch flag** — `UIElement.add_child()` sets `_layout_dirty = True` instead of calling `layout()`. A single pass runs before drawing.
2. **Subtree-local layout** — widgets that only change their own content (Label text, State update) should call `self.layout()`, not `self.get_root().layout()`. Only changes that affect sibling geometry (size change, visibility toggle) escalate to the parent.
3. **Dirty propagation** — each node sets `_layout_dirty` on its parent; the draw pass re-layouts dirty subtrees bottom-up rather than re-running the whole tree.

---

## 3. Width does not participate in UI scaling

**Where:** Every widget constructor that takes `width: int`

`UI_SCALE` was designed to be used everywhere, but `width_spec` stored as an integer is treated as fixed pixels — it never changes when `UI_SCALE` changes. The layout system distinguishes `float` (fraction of parent) from `int` (exact pixels), but has no concept of "scaled pixels."

This is why the SideNav `width=200` stays at 200 px on a 2× window: `scaled_px(200)` is evaluated once at construction time and is never re-evaluated on resize.

**Fix — introduce a `ScaledPx` sentinel type:**
```python
# scale.py
class ScaledPx:
    """Marks a pixel value that should be multiplied by UI_SCALE at layout time."""
    def __init__(self, base: int): self.base = base

def sp(base: int) -> ScaledPx:
    return ScaledPx(base)
```

In `UIElement.layout()`, resolve size:
```python
w = int(self.width_spec.base * UI_SCALE)  if isinstance(self.width_spec,  ScaledPx) else \
    int(self.width_spec * pw)              if isinstance(self.width_spec,  float)    else \
    int(self.width_spec)
```

Widget constructors that currently hardcode default widths (`SideNav(width=200)`, `BottomNavigationBar(height=64)`, `Switch(width=51, height=31)`) should default to `sp(200)`, `sp(64)`, `sp(51)` so they automatically re-evaluate on every layout pass after resize.

---

## 4. Per-frame surface allocations

Several widgets allocate new `pygame.Surface` objects on **every draw call**:

| Widget | Allocation | Frequency |
|--------|-----------|-----------|
| `LineChart.render()` | `Surface((w, h), SRCALPHA)` for gradient fill polygon | Every frame while visible |
| `SideNav.render()` | `Surface((ir.w, ir.h), SRCALPHA)` for hover highlight | Every frame when hovering |
| `PageRouter._draw_page_morphic()` | `smoothscale` creates a new surface | Every frame during refresh transition |
| `PageRouter._draw_page_with_alpha()` | Uses cached `_temp_surf` but refills it with zeros each frame | Every frame during slide transition |

`pygame.Surface()` allocation triggers Python GC pressure and can cause frame-time spikes of 1–3 ms each.

**Fix:**
- `LineChart`: cache the gradient `Surface` keyed on `(w, h, active_color)`. Invalidate only when size or color changes, not every frame.
- `SideNav`: cache one `Surface` per item slot at the item's size; only reallocate when `rect` changes.
- `PageRouter`: the `_temp_surf` cache is already there — extend the same pattern to `_draw_page_morphic`.

---

## 5. `State.bind()` fires the callback immediately at bind time

**Where:** `State.bind()` line 33–37

```python
def bind(self, callback):
    self._listeners.append(callback)
    callback(self._value)   # immediate fire
```

This is intentional (initialise the widget with the current value), but `Label._on_state_update` calls `self.get_root().layout()`. So binding a label to a state during page construction triggers a full relayout **at bind time**, even though the page tree is not yet fully constructed and the result is immediately invalidated by the next `add_child()`.

**Fix:** Delay the initial fire until after `add_child()` has finished, or use the batch-layout flag from Fix 2 so the full relayout is deferred.

---

## 6. `UIElement.update()` walks the entire tree unconditionally every frame

**Where:** `UIElement.update()` lines 116–156

Even when no springs are running and nothing changed, `update()` recurses to every child every frame. For a 200-node page tree at 60 fps this is 12 000 function calls per second doing nothing.

**Fix:**
```python
def update(self, dt):
    has_work = bool(self._active_animations)
    for child in self.children:
        if child.visible:
            child.update(dt)
            # propagate "has_work" upward if needed
    if not has_work:
        return   # skip own animation processing
    ...
```

Short-circuit invisible subtrees entirely (`if not child.visible: continue`).

---

## 7. No dirty-region draw pass — every pixel redrawn every frame

**Where:** `App.frame()` → `self.root.draw(self.screen)`

The entire screen is cleared and fully redrawn every frame even when nothing moved. At 390×768 this is ~300 K pixels cleared and repainted at 60 fps.

**Fix (long-term):** Implement a `_dirty_rect` accumulation system:
- Widgets mark their rect as dirty when visual state changes (spring settled at new value, text changed, theme toggled).
- `App.frame()` calls `pygame.display.update(dirty_rects)` instead of `pygame.display.flip()`.
- Unchanged areas of the screen are never touched.

This is the highest-ROI fix for idle-frame CPU usage.

---

## 8. `PageRouter` morphic transition allocates + `smoothscale`s the full window surface

**Where:** `PageRouter._draw_page_morphic()` lines 278–287

```python
scaled_surf = pygame.transform.smoothscale(temp.subsurface(clip), (new_w, new_h))
```

`smoothscale` on a full phone-screen surface (390×768) takes ~3–5 ms per call in software rendering. During the morphic refresh transition this runs every frame for ~400 ms.

**Fix:** Use `pygame.transform.scale` (nearest-neighbour, ~10× faster) since the scale range is narrow (0.95–1.0) and the difference is imperceptible at that delta. Alternatively, skip the scale transform entirely and only animate the alpha — the scale-in is a nice-to-have, not critical.

---

## 9. `VStack.layout()` re-runs on every `add_child()` call during page construction

**Where:** `UIElement.add_child()` → `self.layout()`

Building a VStack with 7 children calls `layout()` 7 times. Each layout recurses into all already-added children, so total layout work is `O(n²)` in the number of children during construction.

**Fix:** Suppress layout during a "construction batch":
```python
with vstack.batch():
    vstack.add_child(nav)
    vstack.add_child(sep)
    vstack.add_child(controls)
    ...
# layout() called exactly once when the context exits
```

Or simpler: `add_children(*items)` method that adds all items and calls `layout()` once at the end.

---

## 10. `Label.layout()` runs the full font measurement and word-wrap on every layout pass

**Where:** `Label.layout()` lines 98–120

`_perform_word_wrap` splits strings and measures word widths using `font.size()` every time `layout()` is called. With the current architecture this happens dozens of times per page construction.

**Fix:** Cache the wrap result keyed on `(text, font_px, wrap_width)`. Only recompute when one of these three values changes.

---

## Priority order

| # | Fix | Impact | Effort |
|---|-----|--------|--------|
| 1 | `ScaledPx` sentinel — width/height scale with `UI_SCALE` | High | Low |
| 2 | Batch-layout flag — stop `O(n²)` construction cost | High | Medium |
| 3 | Reduce/remove resize debounce | Medium | Low |
| 4 | Combine `invalidate_scale_caches` + `layout` into one pass on resize | Medium | Low |
| 5 | `LineChart` / `SideNav` gradient surface caching | Medium | Low |
| 6 | `update()` short-circuit for idle subtrees | Medium | Medium |
| 7 | `smoothscale` → `scale` in morphic transition | Low–Medium | Low |
| 8 | Label layout cache (wrap result) | Low | Low |
| 9 | Dirty-rect draw pass | High (long-term) | High |
