import pygame
from typing import Tuple, Optional

# Shadow blur constant used for layout offset calculations
SHADOW_BLUR = 6


def make_aa_rect(w: int, h: int, color: pygame.Color, border_radius: int) -> pygame.Surface:
    """
    Render a rounded rect at 2× resolution then smoothscale to 1×.
    The bilinear downscale approximates anti-aliased edges at zero runtime cost.
    Returns a pygame.SRCALPHA surface sized (w, h).
    """
    surf2 = pygame.Surface((w * 2, h * 2), pygame.SRCALPHA)
    pygame.draw.rect(surf2, color, (0, 0, w * 2, h * 2), border_radius=border_radius * 2)
    return pygame.transform.smoothscale(surf2, (w, h))


def make_shadow(w: int, h: int, border_radius: int, blur: int = SHADOW_BLUR) -> pygame.Surface:
    """
    Pre-bake a multi-layer fake drop shadow.
    Returns a SRCALPHA surface sized (w + blur*2, h + blur*2).
    Blit it at (widget_x - blur, widget_y - blur) before drawing the widget.
    """
    pad = blur
    surf = pygame.Surface((w + pad * 2, h + pad * 2), pygame.SRCALPHA)
    for i in range(blur, 0, -1):
        alpha = int(72 * (i / blur) ** 1.6)
        pygame.draw.rect(
            surf,
            (0, 0, 0, alpha),
            (pad - i, pad - i + 2, w + i * 2, h + i * 2),
            border_radius=border_radius + i,
        )
    return surf
