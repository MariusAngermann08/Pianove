from pylay import Label, iOSTheme


def section_header(text: str, U: dict) -> Label:
    """Large section header for main content areas (home, stats)."""
    return Label(
        text=text,
        font_size=U["subtitle_size"],
        bold=True,
        color=iOSTheme.label,
        width=1.0,
        height=U["subtitle_size"] + 10,
    )


def section_subheader(text: str) -> Label:
    """Small muted section header for grouped settings-style lists."""
    return Label(
        text=text,
        font_size=13,
        bold=True,
        color=iOSTheme.secondary_label,
        width=1.0,
        height=22,
    )
