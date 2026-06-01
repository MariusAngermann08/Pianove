import pygame
import sys
import time
from typing import Optional, Union, List, Tuple

# Import our brand new UI library
from pylay import FloatLayout, Button, Spring, iOSTheme, ColorPalette, UIElement, Label, Switch, Slider


# Application state
class DemoApp:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("OpenUI iOS Settings Dashboard")
        
        self.screen_width = 960
        self.screen_height = 680
        self.screen = pygame.display.set_mode(
            (self.screen_width, self.screen_height),
            pygame.RESIZABLE | pygame.HWSURFACE | pygame.DOUBLEBUF
        )
        self.clock = pygame.time.Clock()
        
        # Window Resize Debouncing (prevents context cancellation on Linux/X11)
        self.pending_resize_size = None
        self.resize_event_time = 0.0
        
        # Dashboard interactive states
        self.wifi_connected = True
        self.dnd_active = False
        self.is_playing = False
        self.music_volume = 0.5
        self.sheet_target_y = 0.5  # offscreen bottom offset
        
        # Establish Root layout (fills entire window)
        self.root = FloatLayout(
            anchor="top_left",
            x=0, y=0,
            width=1.0, height=1.0,
            background_color=iOSTheme.background
        )
        
        self.setup_ui()
        
    def setup_ui(self):
        self.root.children.clear()
        
        # 1. Main Header Title block
        title_container = FloatLayout(
            anchor="top",
            x=0, y=25,
            width=0.9, height=60,
            background_color=pygame.Color(0,0,0,0)
        )
        self.root.add_child(title_container)
        
        title_container.add_child(Label(
            text="Control Center",
            font_size=28,
            bold=True,
            color=iOSTheme.label,
            anchor="top_left",
            x=0, y=5
        ))
        
        title_container.add_child(Label(
            text="OpenUI • Premium Physics-Animated Interface",
            font_size=13,
            color=iOSTheme.secondary_label,
            anchor="top_left",
            x=0, y=40
        ))
        
        # 2. Left Panel: Preferences & Toggles
        left_card = FloatLayout(
            anchor="top_left",
            x=0.05, y=100,
            width=0.42, height=0.78,
            border_radius=18,
            border_width=1
        )
        self.root.add_child(left_card)
        
        left_card.add_child(Label(
            text="System Status",
            font_size=18,
            bold=True,
            anchor="top_left",
            x=20, y=20
        ))
        
        # Wi-Fi Row Card
        wifi_card = FloatLayout(
            anchor="top",
            x=0, y=55,
            width=0.9, height=80,
            border_radius=12,
            border_width=1,
            background_color=iOSTheme.secondary_background
        )
        left_card.add_child(wifi_card)
        
        # Custom Indicator circle for Wi-Fi status
        # Since we don't have custom shape primitives, we will use a small FloatLayout as a dot!
        wifi_dot_color = ColorPalette.BLUE if self.wifi_connected else ColorPalette.DARK_GRAY_2
        wifi_card.add_child(FloatLayout(
            anchor="left",
            x=15, y=0,
            width=12, height=12,
            border_radius=6,
            background_color=wifi_dot_color
        ))
        
        wifi_card.add_child(Label(
            text="Wi-Fi Network",
            font_size=15,
            bold=True,
            anchor="top_left",
            x=45, y=20
        ))
        
        wifi_status_text = "Status: Connected" if self.wifi_connected else "Status: Disconnected"
        self.wifi_status_label = Label(
            text=wifi_status_text,
            font_size=12,
            color=iOSTheme.secondary_label,
            anchor="top_left",
            x=45, y=44
        )
        wifi_card.add_child(self.wifi_status_label)
        
        # iOS Switch inside Wi-Fi Row (changes accent tint depending on Wi-Fi state)
        wifi_card.add_child(Switch(
            value=self.wifi_connected,
            on_change=self.toggle_wifi,
            anchor="right",
            x=-20, y=0,
            active_color=ColorPalette.BLUE
        ))
        
        # Do Not Disturb Card (Interactive expanding card!)
        dnd_bg = pygame.Color(120, 30, 200, 70) if self.dnd_active else iOSTheme.secondary_background
        dnd_border = pygame.Color(175, 82, 222, 180) if self.dnd_active else iOSTheme.fill_tertiary
        dnd_card = FloatLayout(
            anchor="top",
            x=0, y=150,
            width=0.9, height=80,
            border_radius=12,
            border_width=1,
            border_color=dnd_border,
            background_color=dnd_bg
        )
        left_card.add_child(dnd_card)
        
        dnd_card.add_child(Label(
            text="Do Not Disturb",
            font_size=15,
            bold=True,
            anchor="top_left",
            x=20, y=20
        ))
        
        dnd_status_text = "Silence calls & notifications" if not self.dnd_active else "All alerts are silenced"
        self.dnd_status_label = Label(
            text=dnd_status_text,
            font_size=12,
            color=iOSTheme.secondary_label if not self.dnd_active else pygame.Color(230, 200, 255),
            anchor="top_left",
            x=20, y=44
        )
        dnd_card.add_child(self.dnd_status_label)
        
        # iOS Switch inside Do Not Disturb Row
        dnd_card.add_child(Switch(
            value=self.dnd_active,
            on_change=self.toggle_dnd,
            anchor="right",
            x=-20, y=0,
            active_color=ColorPalette.PURPLE
        ))
        
        # General Help/Information Info Card
        info_card = FloatLayout(
            anchor="top",
            x=0, y=245,
            width=0.9, height=130,
            border_radius=12,
            border_width=1,
            background_color=iOSTheme.secondary_background
        )
        left_card.add_child(info_card)
        
        info_card.add_child(Label(
            text="Interactive Showcase Guidance",
            font_size=14,
            bold=True,
            anchor="top_left",
            x=15, y=15
        ))
        
        info_card.add_child(Label(
            text="1. Click 'Play/Pause' to watch the Album Art spring scale.",
            font_size=12,
            color=iOSTheme.secondary_label,
            anchor="top_left",
            x=15, y=42
        ))
        info_card.add_child(Label(
            text="2. Tap settings toggles to observe dynamic color swaps.",
            font_size=12,
            color=iOSTheme.secondary_label,
            anchor="top_left",
            x=15, y=64
        ))
        info_card.add_child(Label(
            text="3. Open the Modal Sheet and resize the window to feel",
            font_size=12,
            color=iOSTheme.secondary_label,
            anchor="top_left",
            x=15, y=86
        ))
        info_card.add_child(Label(
            text="   the responsive underdamped layout constraint solver.",
            font_size=12,
            color=iOSTheme.secondary_label,
            anchor="top_left",
            x=15, y=104
        ))
        
        # Dark/Light Mode Theme Toggle anchored at the bottom
        left_card.add_child(Button(
            text="Toggle Styling Theme (Dark/Light)",
            on_click=self.toggle_theme,
            anchor="bottom",
            x=0, y=-20,
            width=0.9, height=44,
            background_color=ColorPalette.DARK_GRAY_4,
            text_color=pygame.Color(255,255,255)
        ))
        
        # 3. Right Panel: Dynamic Music Player controls
        right_panel = FloatLayout(
            anchor="top_right",
            x=-0.05, y=100,
            width=0.46, height=0.78,
            border_radius=18,
            border_width=1
        )
        self.root.add_child(right_panel)
        
        # Music Player Container Card
        self.player_card = FloatLayout(
            anchor="top",
            x=0, y=20,
            width=0.9, height=0.68,
            border_radius=14,
            border_width=1,
            background_color=iOSTheme.secondary_background
        )
        right_panel.add_child(self.player_card)
        
        self.player_card.add_child(Label(
            text="Now Playing",
            font_size=15,
            bold=True,
            anchor="top",
            x=0, y=15
        ))
        
        # Album Art Card sleeve
        # When music is playing vs paused, we will animate its width_spec and height_spec using spring animations!
        album_size = 0.44 if self.is_playing else 0.32
        album_grad_bg = ColorPalette.PINK
        self.album_art = FloatLayout(
            anchor="center",
            x=0, y=-30,
            width=album_size, height=album_size,
            border_radius=16,
            background_color=album_grad_bg
        )
        self.player_card.add_child(self.album_art)
        
        # Add a subtle glossy record label inside album art
        self.album_art.add_child(FloatLayout(
            anchor="center",
            x=0, y=0,
            width=0.3, height=0.3,
            border_radius=12,
            background_color=pygame.Color(255, 255, 255, 60)
        ))
        
        # Song Meta labels
        self.player_card.add_child(Label(
            text="Bouncy Echoes",
            font_size=16,
            bold=True,
            anchor="bottom",
            x=0, y=-95
        ))
        
        self.player_card.add_child(Label(
            text="The Spring Decays",
            font_size=12,
            color=iOSTheme.secondary_label,
            anchor="bottom",
            x=0, y=-75
        ))
        
        # Media Player Control button bar
        play_btn_text = "Pause" if self.is_playing else "Play"
        self.play_button = Button(
            text=play_btn_text,
            on_click=self.toggle_play,
            anchor="bottom",
            x=0, y=-20,
            width=110, height=36,
            background_color=ColorPalette.BLUE
        )
        self.player_card.add_child(self.play_button)
        
        self.player_card.add_child(Button(
            text="⏮",
            on_click=self.skip_prev,
            anchor="bottom_left",
            x=40, y=-21,
            width=40, height=34,
            background_color=iOSTheme.fill
        ))
        
        self.player_card.add_child(Button(
            text="⏭",
            on_click=self.skip_next,
            anchor="bottom_right",
            x=-40, y=-21,
            width=40, height=34,
            background_color=iOSTheme.fill
        ))
        
        # iOS Volume Slider (adjusts volume state on tap/drag)
        self.player_card.add_child(Slider(
            value=self.music_volume,
            on_change=self.set_volume,
            anchor="bottom",
            x=0, y=-52,
            width=0.8, height=20,
            active_color=ColorPalette.BLUE
        ))
        
        # Button at the bottom of Right Panel to launch Slide-over Modal Sheet
        right_panel.add_child(Button(
            text="Device Specifications (Modal)",
            on_click=self.open_sheet,
            anchor="bottom",
            x=0, y=-20,
            width=0.9, height=44,
            background_color=ColorPalette.BLUE
        ))
        
        # 4. Showcase FloatLayout & Animations: iOS Slide-over Sheet (floating over layout!)
        self.sheet = FloatLayout(
            anchor="bottom",
            x=0, y=self.sheet_target_y, # Offscreen or open state based on self.sheet_target_y
            width=0.55, height=0.38,
            border_radius=24,
            border_width=1,
            background_color=iOSTheme.secondary_background
        )
        self.root.add_child(self.sheet)
        
        # iOS Capsule Drag Handle
        self.sheet.add_child(FloatLayout(
            anchor="top",
            x=0, y=10,
            width=40, height=5,
            border_radius=2,
            background_color=iOSTheme.fill
        ))
        
        # Title of the modal
        self.sheet.add_child(Label(
            text="Device Specifications",
            font_size=20,
            bold=True,
            anchor="top",
            x=0, y=32
        ))
        
        # Multi-line spec descriptions
        self.sheet.add_child(Label(
            text="OpenUI Layout Core: Version 1.0.0 (Alpha)",
            font_size=13,
            color=iOSTheme.secondary_label,
            anchor="top",
            x=0, y=72
        ))
        self.sheet.add_child(Label(
            text="Physics Engine: Frame-Rate Independent Analytical Spring-Mass-Damper Solver",
            font_size=13,
            color=iOSTheme.secondary_label,
            anchor="top",
            x=0, y=94
        ))
        self.sheet.add_child(Label(
            text="Target Refresh Rate: Up to 120Hz (Responsive double-buffered redraw)",
            font_size=13,
            color=iOSTheme.secondary_label,
            anchor="top",
            x=0, y=116
        ))
        
        # Close Button inside sheet
        self.sheet.add_child(Button(
            text="Dismiss Panel",
            on_click=self.close_sheet,
            anchor="bottom",
            x=0, y=-25,
            width=200, height=40,
            background_color=iOSTheme.fill
        ))
        
        # Execute initial layout solve
        self.root.layout()

    # Dashboard Control Callbacks
    def toggle_wifi(self, val: bool):
        self.wifi_connected = val
        self.setup_ui()
        
    def toggle_dnd(self, val: bool):
        self.dnd_active = val
        self.setup_ui()
        
    def set_volume(self, val: float):
        self.music_volume = val

    def toggle_play(self):
        self.is_playing = not self.is_playing
        self.setup_ui()
        
        # Animate the Album Art size!
        # If playing, the sleeve card sizes up dynamically with a satisfying underdamped bounce (response=0.42s, damping=0.62)
        # If paused, it collapses down smoothly.
        target_size = 0.44 if self.is_playing else 0.32
        self.album_art.animate_to("width_spec", target_size, response=0.42, damping_fraction=0.62)
        self.album_art.animate_to("height_spec", target_size, response=0.42, damping_fraction=0.62)

    def skip_prev(self):
        # Trigger elastic bounce scale flash on album art
        self.album_art.animate_to("width_spec", 0.28, response=0.15, damping_fraction=0.5)
        self.album_art.animate_to("height_spec", 0.28, response=0.15, damping_fraction=0.5)
        # Force return to normal player size right after
        target_size = 0.44 if self.is_playing else 0.32
        pygame.time.set_timer(pygame.USEREVENT + 1, 150, loops=1)
        
    def skip_next(self):
        # Trigger elastic bounce scale flash on album art
        self.album_art.animate_to("width_spec", 0.48 if self.is_playing else 0.38, response=0.15, damping_fraction=0.5)
        self.album_art.animate_to("height_spec", 0.48 if self.is_playing else 0.38, response=0.15, damping_fraction=0.5)
        pygame.time.set_timer(pygame.USEREVENT + 1, 150, loops=1)

    def open_sheet(self):
        self.sheet_target_y = -0.04
        self.sheet.animate_to("y_spec", self.sheet_target_y, response=0.48, damping_fraction=0.62)
        
    def close_sheet(self):
        self.sheet_target_y = 0.5
        self.sheet.animate_to("y_spec", self.sheet_target_y, response=0.35, damping_fraction=0.85)
        
    def toggle_theme(self):
        # Toggle iOS global theme state
        iOSTheme.dark = not iOSTheme.dark
        iOSTheme.update_theme()
        
        # Re-initialize theme background for root
        self.root.background_color = iOSTheme.background
        self.setup_ui()
        
    def run(self):
        running = True
        while running:
            dt = min(self.clock.tick(60) / 1000.0, 0.05)

            # Advance all spring physics
            self.root.update(dt)

            # Debounced resize
            if self.pending_resize_size is not None and (time.time() - self.resize_event_time) > 0.15:
                w, h = self.pending_resize_size
                self.screen_width, self.screen_height = w, h
                self.screen = pygame.display.set_mode(
                    (w, h), pygame.RESIZABLE | pygame.HWSURFACE | pygame.DOUBLEBUF)
                self.root.layout(self.screen.get_rect())
                self.pending_resize_size = None

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.VIDEORESIZE:
                    self.pending_resize_size = (event.w, event.h)
                    self.resize_event_time = time.time()
                elif event.type == (pygame.USEREVENT + 1):
                    target_size = 0.44 if self.is_playing else 0.32
                    self.album_art.animate_to("width_spec", target_size, response=0.4, damping_fraction=0.6)
                else:
                    self.root.handle_event(event)

            self.screen.fill(iOSTheme.background)
            self.root.draw(self.screen)
            pygame.display.flip()

        pygame.quit()
        sys.exit()

if __name__ == "__main__":
    app = DemoApp()
    app.run()
