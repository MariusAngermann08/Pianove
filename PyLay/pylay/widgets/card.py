from pylay.layouts.list_layout import VStack
from pylay.core.theme import iOSTheme


class Card(VStack):
    def __init__(self, spacing: int = 8, padding: int = 14,
                 border_radius: int = 12, **kwargs):
        kwargs.setdefault("background_color", iOSTheme.secondary_background)
        super().__init__(spacing=spacing, padding=padding,
                         border_radius=border_radius, **kwargs)
