from pylay import OptionSelector
from pianove.i18n import t
from pianove.state import experience_state
from pianove.ui_utils import page_shell, ui_dims


def build():
    U = ui_dims()
    root, card, content, _ = page_shell(
        t("exp_title"),
        t("exp_subtitle"),
        page_id="experience",
        show_back=True,
    )
    content.add_child(
        OptionSelector(
            options=[
                (t("exp_none"), "none"),
                (t("exp_basics"), "basics"),
                (t("exp_simple"), "simple"),
                (t("exp_advanced"), "advanced"),
            ],
            value=experience_state,
            width=0.98,
            row_height=U["option_row_h"],
            spacing=U["option_spacing"],
            font_size=U["option_font"],
        )
    )
    return root
