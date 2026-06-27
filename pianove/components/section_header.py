from pylay import Label, iOSTheme


def section_header(text: str, U: dict) -> Label:
    return Label(
        text=text,
        font_size=U["subtitle_size"],
        bold=True,
        color=iOSTheme.label,
        width=1.0,
        height=U["subtitle_size"] + 10,
    )


def section_subheader(text: str) -> Label:
    return Label(
        text=text,
        font_size=13,
        bold=True,
        color=iOSTheme.secondary_label,
        width=1.0,
        height=22,
    )
