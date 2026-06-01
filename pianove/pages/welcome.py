from pylay import Label
from pianove.i18n import t
from pianove.state import welcome_greeting, _sync_welcome_greeting, name_state
from pianove.ui_utils import page_shell, ui_dims


def build():
    U = ui_dims()
    _sync_welcome_greeting(name_state.value)
    root, card, content, _ = page_shell(
        "",
        t("welcome_subtitle"),
        page_id="welcome",
        show_back=True,
    )
    card.children.insert(
        0, Label(text=welcome_greeting, font_size=U["title_size"], bold=True)
    )
    return root
