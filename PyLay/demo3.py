"""
demo3.py — OpenUI Component Showcase
A single-file demo proving every widget's spring-physics animations work correctly.
Run with: python demo3.py
"""
import pygame
import sys
import time

from pylay import (
    FloatLayout, VStack,
    Button, Label, Switch, Slider, SegmentedControl,
    iOSTheme, ColorPalette,
)

# ---------------------------------------------------------------------------
# Tiny helper — horizontal separator line
# ---------------------------------------------------------------------------
class Divider(FloatLayout):
    def __init__(self, **kw):
        kw.setdefault("height", 1)
        kw.setdefault("width", 1.0)
        kw.setdefault("background_color", pygame.Color(80, 80, 90))
        super().__init__(**kw)

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
class Demo3:
    W, H = 1100, 740

    def __init__(self):
        pygame.init()
        pygame.display.set_caption("OpenUI — Component Showcase")
        self.screen = pygame.display.set_mode(
            (self.W, self.H),
            pygame.RESIZABLE | pygame.HWSURFACE | pygame.DOUBLEBUF,
        )
        self.clock = pygame.time.Clock()

        # Resize debounce
        self._pending_resize = None
        self._resize_time    = 0.0

        # Widget states kept outside setup_ui so theme-toggle survives rebuild
        self.wifi    = True
        self.dnd     = False
        self.vol     = 0.65
        self.bright  = 0.80
        self.tab_idx = 0

        self.setup_ui()

    # -----------------------------------------------------------------------
    # Build the whole UI tree
    # -----------------------------------------------------------------------
    def setup_ui(self):
        # ── Root ────────────────────────────────────────────────────────────
        self.root = FloatLayout(
            anchor="top_left", x=0, y=0, width=1.0, height=1.0,
            background_color=iOSTheme.background,
        )

        # ── Title bar ───────────────────────────────────────────────────────
        title_bar = FloatLayout(
            anchor="top", x=0, y=0, width=1.0, height=60,
            background_color=iOSTheme.secondary_background,
        )
        self.root.add_child(title_bar)

        title_bar.add_child(Label(
            text="OpenUI  ·  Spring-Physics Component Showcase",
            font_size=18, bold=True,
            anchor="top_left", x=24, y=18,
        ))

        # Theme toggle lives in the title bar
        title_bar.add_child(Button(
            text="Toggle Dark / Light",
            on_click=self.toggle_theme,
            anchor="top_right", x=-16, y=10,
            width=180, height=40,
            background_color=ColorPalette.DARK_GRAY_3,
            text_color=pygame.Color(255, 255, 255),
        ))

        # ── Tab selector ────────────────────────────────────────────────────
        self.tabs = SegmentedControl(
            segments=["Buttons", "Toggles & Sliders"],
            selected_index=self.tab_idx,
            on_change=self._switch_tab,
            anchor="top", x=0, y=68,
            width=0.45, height=36,
        )
        self.root.add_child(self.tabs)

        # ── Content area ────────────────────────────────────────────────────
        self.content = FloatLayout(
            anchor="top", x=0, y=116,
            width=1.0, height=0.83,
            background_color=pygame.Color(0, 0, 0, 0),
        )
        self.root.add_child(self.content)

        self._build_buttons_tab()
        self._build_toggles_tab()
        self._apply_tab(self.tab_idx)

        self.root.layout(self.screen.get_rect())

    # -----------------------------------------------------------------------
    # Tab 0 — Buttons
    # -----------------------------------------------------------------------
    def _build_buttons_tab(self):
        self.tab0 = FloatLayout(
            anchor="top_left", x=0, y=0, width=1.0, height=1.0,
            background_color=pygame.Color(0, 0, 0, 0),
        )
        self.content.add_child(self.tab0)

        # Left card
        left = FloatLayout(
            anchor="top_left", x=20, y=10,
            width=0.44, height=0.92,
            border_radius=18, border_width=1,
            background_color=iOSTheme.secondary_background,
        )
        self.tab0.add_child(left)

        left.add_child(Label(
            text="Interactive Buttons",
            font_size=17, bold=True,
            anchor="top_left", x=22, y=20,
        ))
        left.add_child(Label(
            text="Hover to highlight  ·  Press for spring scale-down",
            font_size=12,
            color=iOSTheme.secondary_label,
            anchor="top_left", x=22, y=46,
        ))

        btn_specs = [
            ("Primary Action",      ColorPalette.BLUE,   pygame.Color(255,255,255)),
            ("Success / Confirm",   ColorPalette.GREEN,  pygame.Color(255,255,255)),
            ("Destructive / Danger",ColorPalette.RED,    pygame.Color(255,255,255)),
            ("Warning",             ColorPalette.ORANGE, pygame.Color(255,255,255)),
            ("Neutral Fill",        iOSTheme.fill,       iOSTheme.label),
        ]
        for i, (txt, bg, fg) in enumerate(btn_specs):
            left.add_child(Button(
                text=txt,
                anchor="top", x=0, y=85 + i * 68,
                width=0.82, height=46,
                background_color=bg, text_color=fg,
            ))

        # Right card — explainer
        right = FloatLayout(
            anchor="top_right", x=-20, y=10,
            width=0.44, height=0.92,
            border_radius=18, border_width=1,
            background_color=iOSTheme.secondary_background,
        )
        self.tab0.add_child(right)

        right.add_child(Label(
            text="Spring Physics Model",
            font_size=17, bold=True,
            anchor="top_left", x=22, y=20,
        ))

        lines = [
            ("Scale spring",     "response=0.12s  ·  damping=0.55  (bouncy)"),
            ("Hover highlight",  "response=0.25s  ·  damping=1.00  (smooth)"),
            ("Analytical solver","frame-rate independent exact solution"),
            ("Zero allocations", "no Surface created per-frame"),
            ("Cached base surf", "re-renders only when colors/text change"),
        ]
        for i, (label, desc) in enumerate(lines):
            right.add_child(Label(
                text=label, font_size=13, bold=True,
                anchor="top_left", x=22, y=60 + i * 72,
            ))
            right.add_child(Label(
                text=desc, font_size=12,
                color=iOSTheme.secondary_label,
                anchor="top_left", x=22, y=80 + i * 72,
            ))

    # -----------------------------------------------------------------------
    # Tab 1 — Toggles & Sliders
    # -----------------------------------------------------------------------
    def _build_toggles_tab(self):
        self.tab1 = FloatLayout(
            anchor="top_left", x=0, y=0, width=1.0, height=1.0,
            background_color=pygame.Color(0, 0, 0, 0),
        )
        self.content.add_child(self.tab1)

        # Left — switches
        sw_card = FloatLayout(
            anchor="top_left", x=20, y=10,
            width=0.44, height=0.92,
            border_radius=18, border_width=1,
            background_color=iOSTheme.secondary_background,
        )
        self.tab1.add_child(sw_card)

        sw_card.add_child(Label(
            text="Toggle Switches",
            font_size=17, bold=True,
            anchor="top_left", x=22, y=20,
        ))
        sw_card.add_child(Label(
            text="Tap to toggle  ·  Knob slides with spring physics",
            font_size=12, color=iOSTheme.secondary_label,
            anchor="top_left", x=22, y=46,
        ))

        switch_rows = [
            ("Wi-Fi",           ColorPalette.BLUE,   "wifi"),
            ("Do Not Disturb",  ColorPalette.PURPLE, "dnd"),
        ]
        self._sw_labels = {}
        for i, (name, color, attr) in enumerate(switch_rows):
            y = 90 + i * 90
            sw_card.add_child(Label(
                text=name, font_size=14, bold=True,
                anchor="top_left", x=22, y=y,
            ))
            val = getattr(self, attr)
            lbl = Label(
                text="ON" if val else "OFF",
                font_size=12, color=iOSTheme.secondary_label,
                anchor="top_left", x=22, y=y + 22,
            )
            self._sw_labels[attr] = lbl
            sw_card.add_child(lbl)

            def make_cb(a, l):
                def cb(v):
                    setattr(self, a, v)
                    l.text = "ON" if v else "OFF"
                return cb

            sw_card.add_child(Switch(
                value=val,
                on_change=make_cb(attr, lbl),
                active_color=color,
                anchor="top_right", x=-22, y=y,
            ))

        # Right — sliders
        sl_card = FloatLayout(
            anchor="top_right", x=-20, y=10,
            width=0.44, height=0.92,
            border_radius=18, border_width=1,
            background_color=iOSTheme.secondary_background,
        )
        self.tab1.add_child(sl_card)

        sl_card.add_child(Label(
            text="Sliders",
            font_size=17, bold=True,
            anchor="top_left", x=22, y=20,
        ))
        sl_card.add_child(Label(
            text="Drag to adjust  ·  Track & knob grow on hover",
            font_size=12, color=iOSTheme.secondary_label,
            anchor="top_left", x=22, y=46,
        ))

        slider_rows = [
            ("Volume",     "vol",    ColorPalette.BLUE),
            ("Brightness", "bright", ColorPalette.ORANGE),
        ]
        self._sl_labels = {}
        for i, (name, attr, color) in enumerate(slider_rows):
            y = 90 + i * 100
            sl_card.add_child(Label(
                text=name, font_size=14, bold=True,
                anchor="top_left", x=22, y=y,
            ))
            val = getattr(self, attr)
            lbl = Label(
                text=f"{int(val*100)}%",
                font_size=12, color=iOSTheme.secondary_label,
                anchor="top_right", x=-22, y=y,
            )
            self._sl_labels[attr] = lbl
            sl_card.add_child(lbl)

            def make_sl_cb(a, l):
                def cb(v):
                    setattr(self, a, v)
                    l.text = f"{int(v*100)}%"
                return cb

            sl_card.add_child(Slider(
                value=val,
                on_change=make_sl_cb(attr, lbl),
                active_color=color,
                anchor="top", x=0, y=y + 28,
                width=0.88, height=28,
            ))

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------
    def _switch_tab(self, idx: int):
        self.tab_idx = idx
        self._apply_tab(idx)

    def _apply_tab(self, idx: int):
        self.tab0.visible = (idx == 0)
        self.tab1.visible = (idx == 1)

    def toggle_theme(self):
        iOSTheme.dark = not iOSTheme.dark
        iOSTheme.update_theme()
        self.setup_ui()

    # -----------------------------------------------------------------------
    # Main loop
    # -----------------------------------------------------------------------
    def run(self):
        running = True
        while running:
            dt = min(self.clock.tick(60) / 1000.0, 0.05)

            # Advance all spring animations
            self.root.update(dt)

            # Debounced resize
            if self._pending_resize and (time.time() - self._resize_time) > 0.12:
                w, h = self._pending_resize
                self.screen = pygame.display.set_mode(
                    (w, h), pygame.RESIZABLE | pygame.HWSURFACE | pygame.DOUBLEBUF)
                self.root.layout(self.screen.get_rect())
                self._pending_resize = None

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.VIDEORESIZE:
                    self._pending_resize = (event.w, event.h)
                    self._resize_time    = time.time()
                else:
                    self.root.handle_event(event)

            self.screen.fill(iOSTheme.background)
            self.root.draw(self.screen)
            pygame.display.flip()

        pygame.quit()
        sys.exit()


if __name__ == "__main__":
    Demo3().run()
