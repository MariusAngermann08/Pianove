import pygame
from pylay.core.element import UIElement
from pylay.core.theme import iOSTheme
from pylay.core.scale import scaled_px, scaled_font_size
from pylay.core import font_loader

_N_WHITE     = 4
_BLACK_SLOTS = [0, 1]       # C# between C-D, D# between D-E
_N_BLACK     = len(_BLACK_SLOTS)
_ACCENT_IDX  = 2            # E — starting highlight

_WW  = 10
_WH  = 36
_BW  = 7
_BH  = 22
_RAD = 3

# White key → MIDI note (C4, D4, E4, F4)
_KEY_NOTES = [60, 62, 64, 65]

# Reveal responses — left keys first
_WHITE_RESP = [0.40, 0.30, 0.21, 0.14]
_BLACK_RESP = [0.27, 0.17]
_TEXT_RESP  = 0.11

# Idle highlight sequence (white key indices)
_IDLE_SEQ      = [0, 2, 1, 3, 2, 0, 3, 1, 2, 3, 0, 2]
_IDLE_INTERVAL = 0.42   # seconds between steps


class PianoveLogoWidget(UIElement):

    def __init__(self, key_scale: float = 1.0, play_notes: bool = False,
                 seq: list[int] | None = None, interval: float = _IDLE_INTERVAL,
                 chords: dict | None = None, **kwargs):
        super().__init__(**kwargs)
        self._key_scale      = key_scale
        self._play_notes     = play_notes
        self._seq            = seq if seq is not None else _IDLE_SEQ
        self._interval       = interval
        self._chords         = chords        # {key_idx: [midi, midi, ...]}
        self._playing_notes: list[int] = []
        self._font       = None
        self._font_px    = 0
        self._seq_idx    = 0
        self._lit_k      = self._seq[0]
        self._idle_timer = 0.0
        self._init_springs()

    def _init_springs(self):
        for i in range(_N_WHITE):
            setattr(self, f"_wh{i}", 0.0)
            setattr(self, f"_hl{i}", 1.0 if i == self._lit_k else 0.0)
        for i in range(_N_BLACK):
            setattr(self, f"_bh{i}", 0.0)
        self._text_off = float(scaled_px(int(22 * self._key_scale)))

    def _on_scale_changed(self):
        self._font    = None
        self._font_px = 0
        self._init_springs()

    def _on_theme_changed(self):
        self._font    = None
        self._font_px = 0

    def _get_font(self):
        pt = max(8, int(17 * self._key_scale))
        px = scaled_font_size(pt)
        if self._font is None or self._font_px != px:
            self._font   = font_loader.load_font(pt, bold=True)
            self._font_px = px
        return self._font

    def _dims(self):
        s = self._key_scale
        return (scaled_px(int(_WW * s)), scaled_px(int(_WH * s)),
                scaled_px(int(_BW * s)), scaled_px(int(_BH * s)))

    def _origin(self):
        ww, wh, bw, bh = self._dims()
        ox = self.rect.left + scaled_px(int(14 * self._key_scale))
        oy = self.rect.top  + (self.rect.height - wh) // 2
        return ox, oy

    def update(self, dt: float):
        ww, wh, bw, bh = self._dims()
        full_wh = float(wh)
        full_bh = float(bh)

        # Reveal keys
        for i, resp in enumerate(_WHITE_RESP):
            self.animate_to(f"_wh{i}", full_wh, response=resp, damping_fraction=0.76)
        for i, resp in enumerate(_BLACK_RESP):
            self.animate_to(f"_bh{i}", full_bh, response=resp, damping_fraction=0.76)

        # Wordmark slides in only after the slowest (rightmost) key is 75% revealed
        if getattr(self, "_wh3") >= full_wh * 0.75:
            self.animate_to("_text_off", 0.0, response=_TEXT_RESP, damping_fraction=0.82)

        # Idle highlight cycle
        self._idle_timer += dt
        if self._idle_timer >= self._interval:
            self._idle_timer = 0.0
            prev_k           = self._lit_k
            self._seq_idx    = (self._seq_idx + 1) % len(self._seq)
            self._lit_k      = self._seq[self._seq_idx]

            if self._play_notes and self._lit_k != prev_k:
                try:
                    from pianove.sound_engine_fs import play_raw, stop
                    for n in self._playing_notes:
                        stop(n)
                    notes = (self._chords or {}).get(self._lit_k,
                                                     [_KEY_NOTES[self._lit_k]])
                    for n in notes:
                        play_raw(n, velocity=74)
                    self._playing_notes = list(notes)
                except Exception:
                    pass

        for i in range(_N_WHITE):
            target = 1.0 if i == self._lit_k else 0.0
            self.animate_to(f"_hl{i}", target, response=0.32, damping_fraction=0.78)

        super().update(dt)

    def on_event(self, event: pygame.event.Event) -> bool:
        return False

    def render(self, surface: pygame.Surface):
        if self.rect.width < 60:
            return

        ww, wh, bw, bh = self._dims()
        ox, oy          = self._origin()
        rad             = max(1, scaled_px(int(_RAD * self._key_scale)))
        strip_w         = _N_WHITE * ww

        white_col  = pygame.Color(238, 238, 244) if iOSTheme.dark else pygame.Color(255, 255, 255)
        divider    = pygame.Color(100, 100, 112) if iOSTheme.dark else pygame.Color(185, 185, 198)
        black_col  = pygame.Color(22, 22, 24)
        accent_col = iOSTheme.accent

        for i in range(_N_WHITE):
            kh = int(getattr(self, f"_wh{i}"))
            hl = getattr(self, f"_hl{i}")
            rx = ox + i * ww
            if kh <= 0:
                continue

            r = max(0, min(255, int(white_col.r + hl * (accent_col.r - white_col.r))))
            g = max(0, min(255, int(white_col.g + hl * (accent_col.g - white_col.g))))
            b = max(0, min(255, int(white_col.b + hl * (accent_col.b - white_col.b))))
            fill = pygame.Color(r, g, b)

            pygame.draw.rect(surface, fill,
                             pygame.Rect(rx, oy, ww, kh),
                             border_bottom_left_radius=rad,
                             border_bottom_right_radius=rad)

            if kh > 4:
                shine_a = int(80 + (1.0 - hl) * 140)
                shine = pygame.Surface((ww - 2, 1), pygame.SRCALPHA)
                shine.fill((255, 255, 255, shine_a))
                surface.blit(shine, (rx + 1, oy + 1))

        tallest = int(getattr(self, f"_wh{_N_WHITE - 1}"))
        if tallest > 0 and not iOSTheme.dark:
            for i in range(1, _N_WHITE):
                pygame.draw.line(surface, divider,
                                 (ox + i * ww, oy),
                                 (ox + i * ww, oy + tallest), 1)
            pygame.draw.line(surface, divider, (ox, oy), (ox + strip_w, oy), 1)
            pygame.draw.line(surface, divider, (ox, oy), (ox, oy + tallest), 1)
            pygame.draw.line(surface, divider, (ox + strip_w, oy), (ox + strip_w, oy + tallest), 1)

        for j, slot in enumerate(_BLACK_SLOTS):
            bh_cur = int(getattr(self, f"_bh{j}"))
            if bh_cur <= 0:
                continue
            bx = ox + (slot + 1) * ww - bw // 2
            pygame.draw.rect(surface, black_col,
                             pygame.Rect(bx, oy, bw, bh_cur),
                             border_bottom_left_radius=rad,
                             border_bottom_right_radius=rad)
            pygame.draw.line(surface, pygame.Color(58, 58, 64),
                             (bx + bw - 1, oy + 2),
                             (bx + bw - 1, oy + bh_cur - 4), 1)

        font   = self._get_font()
        keys_r = ox + strip_w
        gap    = scaled_px(10)
        tx     = keys_r + gap + int(self._text_off)

        old_clip = surface.get_clip()
        surface.set_clip(pygame.Rect(
            keys_r + gap, self.rect.top,
            max(0, self.rect.right - keys_r - gap), self.rect.height,
        ).clip(old_clip))

        p_surf    = font.render("P", True, accent_col)
        rest_surf = font.render("ianove", True, iOSTheme.label)
        ty        = self.rect.centery - p_surf.get_height() // 2
        surface.blit(p_surf,    (tx, ty))
        surface.blit(rest_surf, (tx + p_surf.get_width(), ty))

        surface.set_clip(old_clip)
