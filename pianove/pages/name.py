from pylay import TextField
from pianove.i18n import t
from pianove.state import name_state
from pianove.ui_utils import page_shell, ui_dims, set_continue_enabled

_continue_btn = None


def _sync(_=None):
    if _continue_btn:
        set_continue_enabled(_continue_btn, bool(name_state.value.strip()))


name_state.bind(_sync)


def build():
    global _continue_btn
    U = ui_dims()
    root, card, content, next_btn = page_shell(
        t("name_title"),
        t("name_subtitle"),
        page_id="name",
        show_back=True,
        continue_enabled=False,
    )
    content.add_child(
        TextField(
            text=name_state,
            placeholder=t("name_placeholder"),
            width=0.98,
            height=U["field_h_frac"],
            font_size=U["option_font"],
        )
    )
    _continue_btn = next_btn
    _sync()
    return root
