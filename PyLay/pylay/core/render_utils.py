import pygame
from typing import Tuple, Optional

# Shadow blur constant used for layout offset calculations
SHADOW_BLUR = 6


def make_aa_rect(w: int, h: int, color: pygame.Color, border_radius: int) -> pygame.Surface:
    surf2 = pygame.Surface((w * 2, h * 2), pygame.SRCALPHA)
    pygame.draw.rect(surf2, color, (0, 0, w * 2, h * 2), border_radius=border_radius * 2)
    return pygame.transform.smoothscale(surf2, (w, h))


def make_shadow(w: int, h: int, border_radius: int, blur: int = SHADOW_BLUR) -> pygame.Surface:
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
