"""Widgets shared by the lesson and course editors: a text box that wraps, a list that
scrolls by dragging (for touch screens), a keyboard to tap keys on, rows of buttons that
wrap onto a new line on a narrow screen, and form helpers. Every size goes through px(),
so the editors grow and shrink with the window like the rest of Pianove."""
from __future__ import annotations

import time

import pygame
from pylay import FloatLayout, VStack, Label, Button, iOSTheme, ColorPalette
from pylay.core.element import UIElement
from pylay.core import font_loader, _dirty
import pylay.core.scale as _scale

WHITE = pygame.Color(255, 255, 255)
RED = pygame.Color(255, 69, 58)
GREEN = pygame.Color(48, 209, 88)


def scale() -> float:
    return _scale.UI_SCALE


def px(v: float) -> int:
    return max(1, int(round(v * _scale.UI_SCALE)))


def is_narrow(w: int, h: int) -> bool:
    """One column instead of two: a portrait window (a phone or tablet held upright), or a
    window too small for a side panel. Pianove scales its whole UI by min(w/1024, h/768),
    so a portrait window is always 1024 units wide: width alone can't tell."""
    return h > w * 1.1 or unpx(w) < 760


def tn(key: str, n: int, **kw) -> str:
    """A text with a count in it: key_one for 1 ("1 bar"), key for the rest ("3 bars")."""
    from pianove.i18n import t, _load, language_state
    one = f"{key}_one"
    if n == 1 and (one in _load(language_state.value) or one in _load("en")):
        return t(one, n=n, **kw)
    return t(key, n=n, **kw)


def unpx(v: float) -> float:
    """A length on screen in unscaled units (what the layout breakpoints compare)."""
    return v / max(0.05, _scale.UI_SCALE)


def font(size: int, bold: bool = False) -> pygame.font.Font:
    return font_loader.load_font(size, bold=bold)


def text_w(text: str, size: int, bold: bool = True) -> int:
    return font(size, bold).size(text)[0]


# ── buttons ───────────────────────────────────────────────────────────────────────────

def button(text: str, on_click, kind: str = "plain", size: int = 13, height: int = 34,
           min_w: int = 0, **kw) -> Button:
    """A button just wide enough for its text. kind: plain, primary, danger, good."""
    bg, fg = {
        "plain":   (iOSTheme.fill, iOSTheme.label),
        "primary": (ColorPalette.BLUE, WHITE),
        "danger":  (RED, WHITE),
        "good":    (GREEN, WHITE),
    }[kind]
    w = max(px(min_w), text_w(text, size) + px(26))
    return Button(text=text, on_click=on_click, width=w, height=px(height), font_size=size,
                  background_color=bg, text_color=fg, border_radius=px(9), **kw)


class Flow(UIElement):
    """Children laid out left to right, wrapping onto a new line when the row is full
    (a row of buttons on a phone). Its height follows its content."""

    def __init__(self, gap: int = 8, line_gap: int = 8, align: str = "left", **kw):
        kw.setdefault("width", 1.0)
        kw.setdefault("height", px(34))
        super().__init__(**kw)
        self.gap, self.line_gap, self.align = gap, line_gap, align

    def layout(self, parent_rect=None, skip_self: bool = False):
        if not skip_self:
            super().layout(parent_rect, skip_self=False)
        gap, lgap = px(self.gap), px(self.line_gap)
        x0, y = self.rect.left, self.rect.top
        lines: list[list[UIElement]] = [[]]
        used = 0
        for c in self.children:
            if not c.visible:
                continue
            w = int(c.width_spec * self.rect.width) if isinstance(c.width_spec, float) else int(c.width_spec)
            w = min(max(1, w), self.rect.width)
            if lines[-1] and used + gap + w > self.rect.width:
                lines.append([])
                used = 0
            used += (gap if lines[-1] else 0) + w
            c.rect.width = w
            lines[-1].append(c)
        for line in lines:
            if not line:
                continue
            line_h = max(int(c.height_spec) for c in line)
            total = sum(c.rect.width for c in line) + gap * (len(line) - 1)
            x = x0 + (self.rect.width - total if self.align == "right" else 0)
            for c in line:
                c.rect.height = int(c.height_spec)
                c.rect.x, c.rect.y = x, y + (line_h - c.rect.height) // 2
                c.layout(skip_self=True)
                x += c.rect.width + gap
            y += line_h + lgap
        need = max(1, y - lgap - self.rect.top) if any(lines) else 1
        if need != self.rect.height:
            self.height_spec = need
            self.rect.height = need
            self.request_layout()


# ── a list that scrolls by dragging ───────────────────────────────────────────────────

class DragScroll(VStack):
    """A VStack that also scrolls by dragging with a finger or the mouse. A drag that
    starts on a button doesn't press it."""

    def __init__(self, **kw):
        super().__init__(**kw)
        self._down = None
        self._dragging = False

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self.visible or not self.enabled:
            return False
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.rect.collidepoint(event.pos):
            self._down = (event.pos[1], self.scroll_target)
            self._dragging = False
        elif event.type == pygame.MOUSEMOTION and self._down is not None:
            held = getattr(event, "buttons", (1, 0, 0))[0]
            if not held:
                self._down = None
            else:
                dy = event.pos[1] - self._down[0]
                if not self._dragging and self.scroll_active and abs(dy) > px(10):
                    self._dragging = True
                    off = pygame.event.Event(pygame.MOUSEMOTION, pos=(-99999, -99999),
                                             rel=(0, 0), buttons=(0, 0, 0))
                    super().handle_event(off)          # let go of whatever was pressed
                if self._dragging:
                    t = max(0.0, min(self.scroll_max, self._down[1] - dy))
                    self.scroll_target = self.scroll_offset = t
                    _dirty.mark()
                    return True
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            was = self._dragging
            self._down, self._dragging = None, False
            if was:
                return True
        return super().handle_event(event)

    def scroll_to_show(self, el: UIElement):
        if not self.scroll_active:
            return
        top = el.rect.top - self.rect.top
        if top < self.scroll_target:
            self.scroll_target = max(0.0, top - px(12))
        elif el.rect.bottom - self.rect.top > self.scroll_target + self.rect.height:
            self.scroll_target = min(self.scroll_max, el.rect.bottom - self.rect.top - self.rect.height + px(12))


# ── a text box that wraps ─────────────────────────────────────────────────────────────

class TextBox(UIElement):
    """An editable text that wraps onto as many lines as it needs (at least min_lines).
    Typing adds at the end, Backspace removes (held: repeats), Ctrl+V pastes, Enter or a
    tap elsewhere finishes."""

    _focused: "TextBox | None" = None

    def __init__(self, text: str = "", placeholder: str = "", on_change=None,
                 min_lines: int = 1, font_size: int = 14, mono: bool = False, **kw):
        kw.setdefault("width", 1.0)
        kw.setdefault("height", px(40))
        super().__init__(**kw)
        self.text = str(text or "")
        self.placeholder = placeholder
        self.on_change = on_change
        self.min_lines = min_lines
        self.font_size = font_size
        self.focused = False
        self._blink = 0.0
        self._bs_held = 0.0
        self._lines: list[str] = [""]
        self.error = False

    def _font(self):
        return font(self.font_size)

    def _wrap(self, width: int) -> list[str]:
        f = self._font()
        out = []
        for para in (self.text or "").split("\n"):
            line = ""
            for word in para.split(" "):
                test = f"{line} {word}" if line else word
                if f.size(test)[0] <= width or not line:
                    while f.size(test)[0] > width and len(test) > 1 and not line:
                        cut = len(test)                    # one long word: break it
                        while cut > 1 and f.size(test[:cut])[0] > width:
                            cut -= 1
                        out.append(test[:cut])
                        test = test[cut:]
                    line = test
                else:
                    out.append(line)
                    line = word
            out.append(line)
        return out or [""]

    def _needed_h(self) -> int:
        f = self._font()
        pad = px(10)
        self._lines = self._wrap(max(10, self.rect.width - 2 * px(12)))
        return max(len(self._lines), self.min_lines) * f.get_linesize() + 2 * pad

    def layout(self, parent_rect=None, skip_self: bool = False):
        super().layout(parent_rect, skip_self=skip_self)
        need = self._needed_h()
        if need != self.rect.height:
            self.height_spec = need
            self.rect.height = need
            self.request_layout()

    def _changed(self):
        need = self._needed_h()
        if need != self.rect.height:
            self.height_spec = need
            self.request_layout()
        if self.on_change:
            self.on_change(self.text)
        _dirty.mark()

    def focus(self, on: bool):
        if on == self.focused:
            return
        self.focused = on
        if on:
            if TextBox._focused is not None and TextBox._focused is not self:
                TextBox._focused.focus(False)
            TextBox._focused = self
            pygame.key.start_text_input()
            r = self.rect
            try:
                pygame.key.set_text_input_rect(r)
            except Exception:
                pass
        else:
            if TextBox._focused is self:
                TextBox._focused = None
                pygame.key.stop_text_input()
        _dirty.mark()

    def on_event(self, event) -> bool:
        if not self.visible or not self.enabled:
            return False
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self.focus(True)
                return True
            if self.focused:
                self.focus(False)
            return False
        if not self.focused:
            return False
        if event.type == pygame.TEXTINPUT:
            self.text += event.text
            self._changed()
            return True
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
                self._bs_held = 0.0
                self._changed()
                return True
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_ESCAPE, pygame.K_TAB):
                self.focus(False)
                return True
            if event.key == pygame.K_v and (event.mod & (pygame.KMOD_CTRL | pygame.KMOD_META)):
                pasted = _clipboard_text()
                if pasted:
                    self.text += " ".join(pasted.split()) if self.min_lines == 1 else pasted
                    self._changed()
                return True
            return True                      # other keys: typing goes through TEXTINPUT
        return False

    def update(self, dt: float):
        if self.focused:
            self._blink += dt
            if self._blink > 0.5:
                self._blink = 0.0
                _dirty.mark()
            if pygame.key.get_pressed()[pygame.K_BACKSPACE]:
                self._bs_held += dt
                if self._bs_held > 0.45 and self.text:
                    self._bs_held -= 0.04
                    self.text = self.text[:-1]
                    self._changed()
            else:
                self._bs_held = 0.0
        super().update(dt)

    def render(self, surface):
        r = self.rect
        rad = px(8)
        pygame.draw.rect(surface, iOSTheme.secondary_background, r, border_radius=rad)
        border = RED if self.error else (iOSTheme.accent if self.focused else iOSTheme.fill_tertiary)
        pygame.draw.rect(surface, border, r, width=2 if (self.focused or self.error) else 1,
                         border_radius=rad)
        f = self._font()
        lh = f.get_linesize()
        x, y = r.left + px(12), r.top + px(10)
        if not self.text and not self.focused:
            surface.blit(f.render(self.placeholder, True, iOSTheme.secondary_label), (x, y))
            return
        for i, line in enumerate(self._lines):
            surface.blit(f.render(line, True, iOSTheme.label), (x, y + i * lh))
        if self.focused and self._blink < 0.25:
            last = self._lines[-1] if self._lines else ""
            cx = x + f.size(last)[0] + 1
            cy = y + (len(self._lines) - 1) * lh
            pygame.draw.line(surface, iOSTheme.accent, (cx, cy + 2), (cx, cy + lh - 2), 2)


def _clipboard_text() -> str:
    try:
        if hasattr(pygame.scrap, "get_text"):
            return pygame.scrap.get_text() or ""
        if not pygame.scrap.get_init():
            pygame.scrap.init()
        raw = pygame.scrap.get(pygame.SCRAP_TEXT)
        return raw.decode("utf-8", "ignore").rstrip("\x00") if raw else ""
    except Exception:
        return ""


# ── a keyboard to tap keys on ─────────────────────────────────────────────────────────

_WHITE_PCS = (0, 2, 4, 5, 7, 9, 11)
_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


class KeyPicker:
    """A piano keyboard for a PygameCanvas: tapping a key calls on_key(midi) (and sounds
    it). decorate(midi) → (fill colour or None, text or None) marks keys."""

    def __init__(self, on_key, decorate=None, lo: int = 48, octaves: int = 3, sound: bool = True):
        self.on_key = on_key
        self.decorate = decorate or (lambda m: (None, None))
        self.lo = lo - lo % 12
        self.octaves = octaves
        self.sound = sound
        self.held: set[int] = set()
        self.live: set[int] = set()            # keys held on the MIDI keyboard
        self._rects: list[tuple[pygame.Rect, int, bool]] = []
        self._down: int | None = None

    @property
    def hi(self) -> int:
        return self.lo + 12 * self.octaves

    def shift(self, octaves: int):
        self.lo = max(12, min(96, self.lo + 12 * octaves))
        _dirty.mark()

    def fit(self, notes):
        """Show the octaves around these keys."""
        notes = [m for m in notes if m is not None]
        if not notes:
            return
        lo, hi = min(notes), max(notes)
        mid = (lo + hi) / 2 - 6 * self.octaves        # the keys in the middle of the view
        start = int(round(mid / 12)) * 12
        start = min(start, lo - lo % 12)               # never cut the lowest key off
        if start + 12 * self.octaves < hi:
            start = lo - lo % 12
        self.lo = max(12, min(96, start))

    def update(self, dt, rect):
        pass

    def _layout(self, rect: pygame.Rect):
        whites = [m for m in range(self.lo, self.hi + 1) if m % 12 in _WHITE_PCS]
        ww = rect.width / len(whites)
        out_w, out_b = [], []
        for i, m in enumerate(whites):
            out_w.append((pygame.Rect(int(rect.left + i * ww), rect.top,
                                      int(rect.left + (i + 1) * ww) - int(rect.left + i * ww), rect.height), m, False))
            if m % 12 in (0, 2, 5, 7, 9) and m + 1 < self.hi:
                bw = ww * 0.6
                out_b.append((pygame.Rect(int(rect.left + (i + 1) * ww - bw / 2), rect.top,
                                          int(bw), int(rect.height * 0.6)), m + 1, True))
        self._rects = out_b + out_w           # black keys first: they lie on top
        return out_w, out_b

    def draw(self, surface, rect):
        whites, blacks = self._layout(rect)
        dark = iOSTheme.dark
        label_f = font(11, bold=True)
        for kr, m, _ in whites:
            fill, txt = self.decorate(m)
            col = fill or pygame.Color(236, 236, 240)
            if m in self.held or m in self.live:
                col = ColorPalette.BLUE
            pygame.draw.rect(surface, col, kr.inflate(-2, 0), border_radius=px(4))
            if txt is None and m % 12 == 0:
                txt, tcol = f"C{m // 12 - 1}", pygame.Color(120, 120, 128)
            else:
                tcol = WHITE if (fill or m in self.held or m in self.live) else pygame.Color(40, 40, 46)
            if txt:
                ts = label_f.render(str(txt), True, tcol)
                surface.blit(ts, ts.get_rect(midbottom=(kr.centerx, kr.bottom - px(6))))
        for kr, m, _ in blacks:
            fill, txt = self.decorate(m)
            col = fill or (pygame.Color(30, 30, 34) if dark else pygame.Color(28, 28, 32))
            if m in self.held or m in self.live:
                col = ColorPalette.BLUE
            pygame.draw.rect(surface, col, kr, border_radius=px(3))
            if txt:
                ts = label_f.render(str(txt), True, WHITE)
                surface.blit(ts, ts.get_rect(midbottom=(kr.centerx, kr.bottom - px(4))))

    def key_at(self, pos):
        for kr, m, _ in self._rects:
            if kr.collidepoint(pos):
                return m
        return None

    def handle_event(self, event, rect) -> bool:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and rect.collidepoint(event.pos):
            m = self.key_at(event.pos)
            if m is not None:
                self._down = m
                self.held.add(m)
                if self.sound:
                    _sound(m, True)
                self.on_key(m)
                _dirty.mark()
                return True
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1 and self._down is not None:
            m, self._down = self._down, None
            self.held.discard(m)
            if self.sound:
                _sound(m, False)
            _dirty.mark()
            return True
        return False


def _sound(m: int, on: bool):
    try:
        from pianove import sound_engine_fs as se
        se.play(m, 80) if on else se.stop(m)
    except Exception:
        pass


class ItemRow(UIElement):
    """A lesson in a list: its title and a line under it, and buttons on the right (or
    under it when the window is narrow)."""

    def __init__(self, title: str, sub: str, buttons: list, width: int, warn: bool = False):
        self.title, self.sub, self.warn = title, sub, warn
        self.flow = Flow(gap=6, align="right")
        for b in buttons:
            self.flow.add_child(b)
        btn_w = sum(int(b.width_spec) for b in buttons) + px(6) * max(0, len(buttons) - 1)
        self.stacked = btn_w > width * 0.5
        h = px(56) + (px(40) if self.stacked else 0)
        super().__init__(width=1.0, height=h)
        self.btn_w = btn_w
        self.add_child(self.flow)

    def layout(self, parent_rect=None, skip_self: bool = False):
        super().layout(parent_rect, skip_self=skip_self)
        r = self.rect
        if self.stacked:
            self.flow.rect = pygame.Rect(r.left + px(12), r.bottom - px(44), r.width - px(24), px(34))
        else:
            self.flow.rect = pygame.Rect(r.right - px(12) - self.btn_w, r.top + (px(56) - px(34)) // 2,
                                         self.btn_w, px(34))
        self.flow.width_spec = self.flow.rect.width
        self.flow.layout(skip_self=True)

    def render(self, surface):
        r = self.rect
        pygame.draw.rect(surface, iOSTheme.secondary_background, r, border_radius=px(12))
        room = (r.width - px(24)) if self.stacked else (r.width - px(36) - self.btn_w)
        for k, (text, f, col) in enumerate((
                (self.title, font(14, bold=True), iOSTheme.label),
                (self.sub, font(12), RED if self.warn else iOSTheme.secondary_label))):
            while len(text) > 1 and f.size(text)[0] > room:
                text = text[:-2] + "…"
            ts = f.render(text, True, col)
            surface.blit(ts, (r.left + px(14), r.top + px(10) + k * px(20)))


# ── form pieces ───────────────────────────────────────────────────────────────────────

def _left(label: Label, h: int) -> FloatLayout:
    """A label on its own full-width line, at the left (a VStack would centre it)."""
    row = FloatLayout(width=1.0, height=px(h), border_radius=0)
    label.anchor, label.x_spec, label.y_spec = "bottom_left", 0, 0
    row.add_child(label)
    return row


def heading(text: str, size: int = 13) -> FloatLayout:
    return _left(Label(text=text.upper(), font_size=size - 1, bold=True,
                       color=iOSTheme.secondary_label), 26)


def field_label(text: str) -> FloatLayout:
    return _left(Label(text=text, font_size=13, bold=True, color=iOSTheme.label), 20)


def hint(text: str, wrap: int, color=None, size: int = 12) -> Label:
    return Label(text=text, font_size=size, color=color or iOSTheme.secondary_label,
                 wrap_width=max(60, int(unpx(wrap))))


def left(widget) -> "Flow":
    """A fixed-width widget at the left of its line (a VStack would centre it)."""
    row = Flow()
    row.height_spec = widget.height_spec
    row.add_child(widget)
    return row


def spacer(h: int = 6) -> FloatLayout:
    return FloatLayout(width=1.0, height=px(h))


def divider() -> FloatLayout:
    return FloatLayout(width=1.0, height=1, background_color=pygame.Color(120, 120, 128, 60),
                       border_radius=0)


class Ticker(UIElement):
    """Calls fn(dt) every frame (an invisible element at the page's root)."""

    def __init__(self, fn):
        super().__init__(width=1, height=1)
        self.fn = fn

    def update(self, dt):
        self.fn(dt)
        super().update(dt)


class Toast:
    """A message shown for a few seconds in a Label."""

    def __init__(self, label: Label):
        self.label = label
        self.until = 0.0

    def show(self, text: str, seconds: float = 4.0, color=None):
        self.label.text = text
        self.label.color = color or iOSTheme.secondary_label
        self.label._text_surf_cache.clear()
        self.label.request_layout()
        self.until = time.monotonic() + seconds
        _dirty.mark()

    def tick(self):
        if self.until and time.monotonic() > self.until:
            self.until = 0.0
            self.label.text = ""
            self.label.request_layout()
            _dirty.mark()


def export_dir():
    from pathlib import Path
    d = Path.home() / "Downloads"
    return d if d.is_dir() else Path.home()
