import pygame
from pylay.layouts.float_layout import FloatLayout
from pylay.core.theme import iOSTheme
from pianove.home.ui_logo import PianoveLogoWidget

_HOLD_SECS = 2.8   # how long to hold at full visibility before fading out


class BootPage(FloatLayout):
    """
    Full-screen splash. Phases:
      "in"   — overlay springs 255→0  (logo + tagline fade in)
      "hold" — fully visible for _HOLD_SECS
      "out"  — overlay springs 0→255  (fade to black then navigate)
      "done" — navigated
    Vignette drawn under children (render override).
    Tagline drawn between children and overlay (draw override).
    """

    def __init__(self, next_page: str, **kwargs):
        super().__init__(**kwargs)
        self._next          = next_page
        self._phase         = "in"
        self._hold_timer    = 0.0
        self._fade          = 255.0
        self._tagline_alpha = 0.0
        self._ov: pygame.Surface | None       = None
        self._vignette: pygame.Surface | None = None
        self._font      = None
        self._font_pt   = 0

    # ── animation ─────────────────────────────────────────────────────────────

    def update(self, dt: float):
        if self._phase == "in":
            self.animate_to("_fade", 0.0, response=0.28, damping_fraction=0.90)
            # Start tagline when overlay is mostly dissolved
            if self._fade < 80.0:
                self.animate_to("_tagline_alpha", 255.0, response=0.20, damping_fraction=0.85)
            if self._fade < 6.0:
                self._phase = "hold"

        elif self._phase == "hold":
            self.animate_to("_tagline_alpha", 255.0, response=0.20, damping_fraction=0.85)
            self._hold_timer += dt
            if self._hold_timer >= _HOLD_SECS:
                self._phase = "out"

        elif self._phase == "out":
            self.animate_to("_fade", 255.0, response=0.40, damping_fraction=0.88)
            if self._fade > 248.0:
                self._phase = "done"
                import pianove.context as ctx
                ctx.router.navigate(self._next)

        super().update(dt)

    # ── vignette (rendered under children) ────────────────────────────────────

    def render(self, surface: pygame.Surface):
        super().render(surface)
        w, h = self.rect.width, self.rect.height
        if w <= 0 or h <= 0:
            return
        if self._vignette is None or self._vignette.get_size() != (w, h):
            self._vignette = _make_vignette(w, h)
        surface.blit(self._vignette, self.rect.topleft)

    # ── tagline + fade overlay (drawn over children) ───────────────────────────

    def draw(self, surface: pygame.Surface):
        super().draw(surface)   # background + vignette + logo children

        # Tagline
        t_alpha = max(0, min(255, int(self._tagline_alpha)))
        if t_alpha > 0 and self.children:
            font = self._get_font(self.rect.height)
            text_surf = font.render("Piano. Reimagined.", True, (170, 170, 185))
            text_surf.set_alpha(t_alpha)
            logo = self.children[0]
            tx = self.rect.left + (self.rect.width - text_surf.get_width()) // 2
            ty = logo.rect.bottom + int(self.rect.height * 0.035)
            surface.blit(text_surf, (tx, ty))

        # Fade overlay
        alpha = max(0, min(255, int(self._fade)))
        if alpha > 0:
            w, h = self.rect.width, self.rect.height
            if self._ov is None or self._ov.get_size() != (w, h):
                self._ov = pygame.Surface((w, h), pygame.SRCALPHA)
            bg = iOSTheme.background
            self._ov.fill((bg.r, bg.g, bg.b, alpha))
            surface.blit(self._ov, self.rect.topleft)

    # ── font ──────────────────────────────────────────────────────────────────

    def _get_font(self, h: int):
        pt = max(10, h // 38)
        if self._font is None or self._font_pt != pt:
            pygame.font.get_init() or pygame.font.init()
            self._font   = pygame.font.SysFont("Arial", pt)
            self._font_pt = pt
        return self._font


# ── vignette helper ───────────────────────────────────────────────────────────

def _make_vignette(w: int, h: int) -> pygame.Surface:
    """Radial-ish vignette: dark edges, transparent center."""
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    steps = 50
    for i in range(steps):
        t = 1.0 - i / steps          # 1.0 at outermost, ~0 at innermost
        alpha = int(88 * t * t)      # quadratic: 88 at edge, 0 at center
        inset_x = int(w * 0.5 * i / steps)
        inset_y = int(h * 0.5 * i / steps)
        pygame.draw.rect(surf, (0, 0, 0, alpha),
                         (inset_x, inset_y, w - 2 * inset_x, h - 2 * inset_y))
    return surf


# ── builder ───────────────────────────────────────────────────────────────────

def build(next_page: str = "home"):
    import pianove.context as ctx

    w = ctx.ui.width
    h = ctx.ui.height

    page = BootPage(
        next_page=next_page,
        width=1.0, height=1.0,
        background_color=iOSTheme.background,
    )

    logo_w = int(w * 0.45)
    logo_h = int(h * 0.22)
    logo_x = (w - logo_w) // 2
    logo_y = (h - logo_h) // 2 - int(h * 0.06)

    # C major → D major → E major, root key lights up for each chord
    _BOOT_SEQ    = [0, 1, 2]
    _BOOT_CHORDS = {
        0: [48, 60, 64, 67],   # C major — C3 C4 E4 G4
        1: [50, 62, 66, 69],   # D major — D3 D4 F#4 A4
        2: [52, 64, 68, 71],   # E major — E3 E4 G#4 B4
    }

    page.add_child(PianoveLogoWidget(
        key_scale=2.8,
        play_notes=True,
        seq=_BOOT_SEQ,
        chords=_BOOT_CHORDS,
        interval=0.75,
        anchor="top_left",
        x=logo_x, y=logo_y,
        width=logo_w, height=logo_h,
    ))

    return page
