from pylay.layouts.float_layout import FloatLayout
from pylay.layouts.list_layout import VStack
from pylay.core.theme import iOSTheme
from pylay.widgets.label import Label
from pylay.widgets.emoji_icon import EmojiIcon


class EmptyState(FloatLayout):
    def __init__(
        self,
        icon: str,
        title: str,
        subtitle: str = "",
        icon_size: int = 48,
        **kwargs,
    ):
        kwargs.setdefault("width", 1.0)
        kwargs.setdefault("height", 1.0)
        super().__init__(**kwargs)

        content_h = icon_size + 28 + (22 if subtitle else 0) + 16
        col = VStack(
            spacing=10, padding=0,
            anchor="center", x=0, y=0,
            width=0.7, height=content_h,
        )
        col.add_child(EmojiIcon(icon, size=icon_size,
                                color=iOSTheme.secondary_label))
        col.add_child(Label(
            text=title,
            font_size=15, bold=True,
            color=iOSTheme.label,
            width=1.0, height=24,
        ))
        if subtitle:
            col.add_child(Label(
                text=subtitle,
                font_size=13,
                color=iOSTheme.secondary_label,
                width=1.0, height=20,
            ))

        self.add_child(col)
