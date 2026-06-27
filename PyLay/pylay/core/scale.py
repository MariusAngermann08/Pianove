REF_WIDTH = 1024
REF_HEIGHT = 768
UI_SCALE = 1.0


def set_window_size(width: int, height: int, ref_w: int = REF_WIDTH, ref_h: int = REF_HEIGHT):
    global UI_SCALE
    if ref_w <= 0 or ref_h <= 0:
        UI_SCALE = 1.0
        return
    UI_SCALE = min(width / ref_w, height / ref_h)


def scaled_font_size(base_size: int) -> int:
    return max(1, int(base_size * UI_SCALE))


def scaled_px(base_px: int) -> int:
    return max(1, int(base_px * UI_SCALE))
