from pylay.layouts.list_layout import VStack
from pylay.core.theme import iOSTheme


class Card(VStack):
    """
    A themed card container. Defaults to the secondary background color and a
    standard border radius so call sites don't repeat the same four styling params.
    All VStack / FloatLayout kwargs (width, height, anchor, x, y, …) pass through.
    """
    def __init__(self, spacing: int = 8, padding: int = 14,
                 border_radius: int = 12, **kwargs):
        kwargs.setdefault("background_color", iOSTheme.secondary_background)
        super().__init__(spacing=spacing, padding=padding,
                         border_radius=border_radius, **kwargs)
