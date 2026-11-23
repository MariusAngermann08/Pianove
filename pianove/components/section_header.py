from pylay import FloatLayout, Label, iOSTheme


def section_header(text: str, U: dict) -> FloatLayout:
    """A heading above a group of cards, aligned with their left edge."""
    h = U["subtitle_size"] + 12
    row = FloatLayout(width=1.0, height=h)
    row.add_child(Label(
        text=text,
        font_size=U["subtitle_size"],
        bold=True,
        color=iOSTheme.label,
        anchor="bottom_left", x=4, y=0,
    ))
    return row


def section_subheader(text: str) -> FloatLayout:
    row = FloatLayout(width=1.0, height=22)
    row.add_child(Label(
        text=text,
        font_size=13,
        bold=True,
        color=iOSTheme.secondary_label,
        anchor="left", x=4, y=0,
    ))
    return row
