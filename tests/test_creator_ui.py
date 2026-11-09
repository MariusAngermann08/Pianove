"""The editors' own scale for phones: bigger on an upright window, untouched when the
platform sizes the UI itself (a phone build pins PyLay's scale)."""
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "PyLay"))

import pylay.core.scale as scale  # noqa: E402
import pianove.context as ctx  # noqa: E402
from pianove import creator_ui as ui  # noqa: E402


def test_upright_window_gets_a_bigger_scale(monkeypatch):
    monkeypatch.setattr(ctx, "ui", SimpleNamespace(width=1080, height=2340))
    assert ui.apply_page_scale()
    assert abs(scale.UI_SCALE - 1080 / 560) < 1e-6 and ui.is_touch_layout()
    ui.restore_scale()
    assert abs(scale.UI_SCALE - 1080 / 1024) < 1e-6 and not ui.is_touch_layout()


def test_a_desktop_window_keeps_the_app_scale(monkeypatch):
    monkeypatch.setattr(ctx, "ui", SimpleNamespace(width=1280, height=800))
    assert not ui.apply_page_scale()
    assert abs(scale.UI_SCALE - 1.0) < 1e-6


def test_a_pinned_scale_is_left_alone(monkeypatch):
    monkeypatch.setattr(ctx, "ui", SimpleNamespace(width=1100, height=520))
    monkeypatch.setattr(scale, "_FIXED_SCALE", 1.0, raising=False)
    monkeypatch.setattr(scale, "UI_SCALE", 1.0)
    assert not ui.apply_page_scale()
    assert scale.UI_SCALE == 1.0 and ui.is_touch_layout()     # still laid out for touch
    ui.restore_scale()
    assert scale.UI_SCALE == 1.0
