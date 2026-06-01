from pylay import OptionSelector
from pianove.i18n import t, language_state
from pianove.ui_utils import page_shell, ui_dims


def build():
    U = ui_dims()
    root, card, content, _ = page_shell(
        t("lang_title"),
        t("lang_subtitle"),
        page_id="language",
        show_back=False,
    )
    content.add_child(
        OptionSelector(
            options=[
                (t("lang_english"), "en"),
                (t("lang_german"), "de"),
            ],
            value=language_state,
            width=0.98,
            row_height=U["option_row_h"],
            spacing=U["option_spacing"],
            font_size=U["option_font"],
        )
    )
    return root
