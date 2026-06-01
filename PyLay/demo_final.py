"""
demo_final.py — The Ultimate OpenGUI Showcase & Live Code Playground
An interactive split-screen experience featuring:
- Dual-Pane Layout: Live Interactive Component (Left) vs. Syntax-Highlighted Source Code (Right).
- Reactive SegmentedControl filters which dynamically swap showcased widgets and their code text.
- Full Runtime Theme Swapping: An iOS toggle switch dynamically morphs the entire system between Dark Mode and Light Mode instantly!
- Kinetic Momentum-Scroll Gutter CodeViewer.
- Physics-based slide drawers and bounce-tab bottom navigations.
- PygameCanvas slot for embedding existing pygame classes (mini piano demo).
- App works standalone (app.run()) or inside your own pygame loop (app.frame()).

Run with: python demo_final.py
"""
import pygame
from pylay import (
    App, State, FloatLayout, VStack, Label, Button,
    TextField, ProgressBar, PageRouter,
    HamburgerButton, SidebarDrawer, BottomNavigationBar, Switch, Slider,
    SegmentedControl, LineChart, CodeViewer, PygameCanvas, iOSTheme, ColorPalette
)


# ---------------------------------------------------------------------------
# Example: a plain pygame class you can drop into PygameCanvas unchanged
# ---------------------------------------------------------------------------
class MiniPiano:
    """Tiny 8-key piano — native pygame logic, hosted inside OpenGUI."""

    NOTE_NAMES = ["C", "D", "E", "F", "G", "A", "B", "C²"]
    NOTE_COLORS = [
        (255, 99, 99), (255, 170, 70), (255, 230, 80), (120, 220, 120),
        (80, 180, 255), (160, 120, 255), (255, 120, 200), (200, 200, 210),
    ]

    def __init__(self):
        self.pressed: set[int] = set()
        self.last_note = "—"

    def _key_index(self, event: pygame.event.Event, rect: pygame.Rect) -> int | None:
        if not rect.collidepoint(event.pos):
            return None
        key_w = rect.width / len(self.NOTE_NAMES)
        return max(0, min(len(self.NOTE_NAMES) - 1, int((event.pos[0] - rect.left) / key_w)))

    def handle_event(self, event: pygame.event.Event, rect: pygame.Rect) -> bool:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            idx = self._key_index(event, rect)
            if idx is not None:
                self.pressed.add(idx)
                self.last_note = self.NOTE_NAMES[idx]
                return True
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            idx = self._key_index(event, rect)
            if idx is not None:
                self.pressed.discard(idx)
                return True
        return False

    def draw(self, surface: pygame.Surface, rect: pygame.Rect):
        key_count = len(self.NOTE_NAMES)
        key_w = max(1, rect.width // key_count)
        key_h = max(1, rect.height - 28)
        base = iOSTheme.secondary_background
        pygame.draw.rect(surface, base, rect, border_radius=8)

        for i, name in enumerate(self.NOTE_NAMES):
            kr = pygame.Rect(rect.left + i * key_w + 2, rect.top + 4, key_w - 4, key_h)
            col = self.NOTE_COLORS[i]
            if i in self.pressed:
                shade = pygame.Color(max(0, col[0] - 40), max(0, col[1] - 40), max(0, col[2] - 40))
            else:
                shade = pygame.Color(*col)
            pygame.draw.rect(surface, shade, kr, border_radius=6)
            pygame.draw.rect(surface, iOSTheme.fill_tertiary, kr, width=1, border_radius=6)
            font = pygame.font.SysFont("Arial", 11, bold=True)
            label = font.render(name, True, iOSTheme.label)
            surface.blit(label, label.get_rect(center=kr.center))

        hint = pygame.font.SysFont("Arial", 12).render(
            f"Last note: {self.last_note}  •  click keys to play", True, iOSTheme.secondary_label
        )
        surface.blit(hint, (rect.left + 8, rect.bottom - 22))

# 1. Initialize Application
app = App(title="OpenGUI Ultimate Showcase & Code Playground", width=1024, height=768, dark_mode=True)

# 2. Shared Reactive States
active_tab = State(0)
sidebar_open = State(False)
dark_mode_state = State(True)

# 3. Source Code Snippets for CodeViewer Showcase
SEGMENTED_CONTROL_CODE = """# 1. Instantiate selected index state
selected_tab = State(0)

# 2. Build the iOS Segmented Control
segmented = SegmentedControl(
    segments=["Overview", "Analytics", "Settings"],
    selected_index=selected_tab,
    on_change=lambda idx: print(f"Active tab: {idx}"),
    width=0.8, height=36
)"""

LINE_CHART_CODE = """# 1. Define vector data points and X-labels
cpu_data = [12.0, 19.5, 8.4, 27.0, 15.2, 33.1, 45.0]
days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

# 2. Instantiate the LineChart widget
chart = LineChart(
    data=cpu_data,
    labels=days,
    active_color=ColorPalette.BLUE,
    title="Weekly Server CPU Load (%)",
    width=0.9, height=180
)"""

SWITCHES_CODE = """# 1. Toggle switch state value
switch_val = State(True)

# 2. Create the toggle switch widget
toggle = Switch(
    value=switch_val,
    active_color=ColorPalette.GREEN,
    width=51, height=31
)"""

PROGRESS_BAR_CODE = """# 1. Numeric progress state (0.0 to 1.0)
progress_val = State(0.65)

# 2. Build linear Progress Bar
progress_bar = ProgressBar(
    progress=progress_val,
    active_color=ColorPalette.PURPLE,
    width=0.9, height=10
)"""

BUTTONS_CODE = """# 1. Counter state binding
counter = State(0)

# 2. Add an interactive Action Button
btn = Button(
    text="Increment Counter",
    on_click=lambda: counter.set(counter.value + 1),
    width=200, height=44,
    background_color=ColorPalette.BLUE
)"""

PYGAME_CANVAS_CODE = """# Your existing pygame class (draw / handle_event / update)
class MiniPiano:
    def handle_event(self, event, rect): ...
    def draw(self, surface, rect): ...

piano = MiniPiano()

# Mount it inside the OpenGUI layout tree
canvas = PygameCanvas(
    target=piano,
    width=0.92, height=200,
    anchor="center", x=0, y=0
)

# Or use callbacks instead of a class:
canvas = PygameCanvas(
    on_draw=lambda surf, rect: my_draw(surf, rect),
    on_event=lambda ev, rect: my_input(ev, rect),
    width=400, height=180
)

# Embedded pygame loop (you own the window):
# app = App(managed_display=False)
# app.attach(screen)
# while running:
#     app.process_events(pygame.event.get())
#     app.frame(dt)
#     pygame.display.flip()"""

# Reactive state holding the active code snippet text
active_code_snippet = State(SEGMENTED_CONTROL_CODE)

# ----------------------------------------------------------------------
# Page Builder 1: Split-Screen Code Playground
# ----------------------------------------------------------------------
def build_playground_page() -> FloatLayout:
    view = FloatLayout(width=1.0, height=1.0)
    
    # Top Headline Banner
    header = VStack(spacing=6, padding=12, anchor="top", x=0, y=0, width=0.95, height=80)
    header.add_child(Label(text="OpenGUI Widget Interactive Playground", font_size=22, bold=True))
    header.add_child(Label(text="Select a segment below to test components live and explore their source code with highlighting!", font_size=12, color=iOSTheme.secondary_label))
    view.add_child(header)
    
    # Showcase selector control
    showcase_segments = [
        "Segmented Control", "Line Chart", "Interactive Switches",
        "Progress Bars", "Buttons & States", "Native Pygame",
    ]
    selector_state = State(0)
    
    def on_showcase_change(index: int):
        # Update the CodeViewer snippet text reactively!
        snippets = [
            SEGMENTED_CONTROL_CODE,
            LINE_CHART_CODE,
            SWITCHES_CODE,
            PROGRESS_BAR_CODE,
            BUTTONS_CODE,
            PYGAME_CANVAS_CODE,
        ]
        active_code_snippet.value = snippets[index]
        
    selector = SegmentedControl(
        segments=showcase_segments,
        selected_index=selector_state,
        on_change=on_showcase_change,
        anchor="top", x=0, y=82, width=0.9, height=36
    )
    view.add_child(selector)
    
    # Main split-screen container holding Left (Preview) and Right (Code) cards
    split_container = FloatLayout(anchor="top", x=0, y=134, width=0.92, height=440)
    view.add_child(split_container)
    
    # --- LEFT PANE: Live Interactive Preview ---
    preview_card = VStack(
        spacing=16, padding=20, anchor="left", x=0, y=0, width=0.48, height=1.0,
        border_radius=16, background_color=iOSTheme.secondary_background
    )
    split_container.add_child(preview_card)
    preview_card.add_child(Label(text="Interactive Live Render", font_size=15, bold=True))
    
    # Interactive placeholders based on selected segment
    preview_stack = FloatLayout(width=1.0, height=0.8)
    preview_card.add_child(preview_stack)
    
    # Segment 1: Segmented Control Showcase
    seg_showcase_state = State(0)
    seg_widget = SegmentedControl(
        segments=["Apples", "Bananas", "Cherries"],
        selected_index=seg_showcase_state,
        anchor="center", x=0, y=-40, width=280, height=36
    )
    seg_label = Label(text="Selected Fruit: Apples", font_size=14, bold=True, anchor="center", x=0, y=20)
    seg_showcase_state.bind(lambda v: setattr(seg_label, "text", f"Selected Fruit: {['Apples', 'Bananas', 'Cherries'][v]}"))
    
    preview_stack.add_child(seg_widget)
    preview_stack.add_child(seg_label)
    
    # Segment 2: Line Chart Showcase
    chart_widget = LineChart(
        data=[12.0, 19.5, 8.4, 27.0, 15.2, 33.1, 45.0],
        labels=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        active_color=ColorPalette.BLUE,
        title="Server CPU Metrics (%)",
        anchor="center", x=0, y=0, width=0.96, height=220
    )
    preview_stack.add_child(chart_widget)
    
    # Segment 3: Interactive Switches Showcase
    switch_grid = VStack(spacing=14, padding=16, anchor="center", x=0, y=0, width=0.92, height=180)
    sw1_val = State(True)
    sw1_row = FloatLayout(width=0.9, height=36)
    sw1_row.add_child(Label(text="Wi-Fi Network Connection", font_size=13, anchor="left", x=0, y=10))
    sw1_row.add_child(Switch(value=sw1_val, active_color=ColorPalette.GREEN, anchor="right", x=0, y=2))
    
    sw2_val = State(False)
    sw2_row = FloatLayout(width=0.9, height=36)
    sw2_row.add_child(Label(text="Bluetooth Accessories", font_size=13, anchor="left", x=0, y=10))
    sw2_row.add_child(Switch(value=sw2_val, active_color=ColorPalette.BLUE, anchor="right", x=0, y=2))
    
    sw3_val = State(True)
    sw3_row = FloatLayout(width=0.9, height=36)
    sw3_row.add_child(Label(text="Airdrop Sharing", font_size=13, anchor="left", x=0, y=10))
    sw3_row.add_child(Switch(value=sw3_val, active_color=ColorPalette.PURPLE, anchor="right", x=0, y=2))
    
    switch_grid.add_child(sw1_row)
    switch_grid.add_child(sw2_row)
    switch_grid.add_child(sw3_row)
    preview_stack.add_child(switch_grid)
    
    # Segment 4: Progress Bar Showcase
    prog_showcase_val = State(0.4)
    prog_container = VStack(spacing=18, padding=16, anchor="center", x=0, y=0, width=0.92, height=180)
    prog_container.add_child(Label(text="Dynamic System Loading Progress:", font_size=13, bold=True))
    
    pbar = ProgressBar(progress=prog_showcase_val, active_color=ColorPalette.PURPLE, width=0.9, height=10)
    prog_container.add_child(pbar)
    
    prog_slider = Slider(value=prog_showcase_val, min_val=0.0, max_val=1.0, active_color=ColorPalette.PURPLE, width=0.9, height=20)
    prog_container.add_child(prog_slider)
    
    prog_pct_lbl = Label(text="Progress: 40%", font_size=13, color=iOSTheme.secondary_label)
    prog_showcase_val.bind(lambda v: setattr(prog_pct_lbl, "text", f"Progress: {int(v * 100)}%"))
    prog_container.add_child(prog_pct_lbl)
    
    preview_stack.add_child(prog_container)
    
    # Segment 5: Buttons & Counter Showcase
    counter_val = State(0)
    btn_container = VStack(spacing=16, padding=16, anchor="center", x=0, y=0, width=0.92, height=180)
    counter_lbl = Label(text="Action Counter Value: 0", font_size=16, bold=True)
    counter_val.bind(lambda v: setattr(counter_lbl, "text", f"Action Counter Value: {v}"))
    btn_container.add_child(counter_lbl)
    
    action_btn = Button(
        text="Increment State Counter",
        on_click=lambda: counter_val.set(counter_val.value + 1),
        width=0.8, height=44,
        background_color=ColorPalette.BLUE
    )
    reset_btn = Button(
        text="Reset Counter to Zero",
        on_click=lambda: counter_val.set(0),
        width=0.8, height=36,
        background_color=ColorPalette.DARK_GRAY_3
    )
    btn_container.add_child(action_btn)
    btn_container.add_child(reset_btn)
    preview_stack.add_child(btn_container)

    # Segment 6: Native pygame integration (mini piano)
    piano = MiniPiano()
    piano_container = VStack(
        spacing=8, padding=8, anchor="center", x=0, y=0, width=0.96, height=0.88,
    )
    piano_container.add_child(
        Label(text="PygameCanvas — embed your own draw/event code", font_size=12, color=iOSTheme.secondary_label)
    )
    piano_canvas = PygameCanvas(target=piano, width=0.98, height=200, anchor="center", x=0, y=0)
    piano_container.add_child(piano_canvas)
    preview_stack.add_child(piano_container)
    
    # Helper callback to handle dynamic layout swaps in Split View
    def refresh_preview_visibility(index: int):
        # Set visibility on appropriate preview containers
        seg_widget.visible = (index == 0)
        seg_label.visible = (index == 0)
        chart_widget.visible = (index == 1)
        switch_grid.visible = (index == 2)
        prog_container.visible = (index == 3)
        btn_container.visible = (index == 4)
        piano_container.visible = (index == 5)
        
    selector_state.bind(refresh_preview_visibility)
    refresh_preview_visibility(0) # Trigger initial
    
    # --- RIGHT PANE: Syntax-Highlighted CodeViewer ---
    code_card = VStack(
        spacing=10, padding=20, anchor="right", x=0, y=0, width=0.48, height=1.0,
        border_radius=16, background_color=iOSTheme.secondary_background
    )
    split_container.add_child(code_card)
    code_card.add_child(Label(text="Live Source Code (Syntax Highlighted)", font_size=15, bold=True))
    
    viewer = CodeViewer(
        code_text=active_code_snippet,
        width=0.96, height=0.82
    )
    code_card.add_child(viewer)
    
    return view

# ----------------------------------------------------------------------
# Page Builder 2: Dashboard System Settings
# ----------------------------------------------------------------------
def build_settings_page() -> FloatLayout:
    view = FloatLayout(width=1.0, height=1.0)
    
    card = VStack(
        spacing=18, padding=24, anchor="center", width=0.82, height=0.85,
        border_radius=18, background_color=iOSTheme.secondary_background
    )
    view.add_child(card)
    
    card.add_child(Label(text="System Settings", font_size=24, bold=True))
    card.add_child(Label(text="Customize visual themes and parameters reactively:", font_size=13, color=iOSTheme.secondary_label))
    
    # Reactive Light/Dark Mode Switch Row
    theme_row = FloatLayout(width=0.9, height=44)
    theme_row.add_child(Label(text="Tactile iOS Dark Mode Theme", font_size=14, bold=True, anchor="left", x=0, y=12))
    
    theme_switch = Switch(value=dark_mode_state, active_color=ColorPalette.GREEN, anchor="right", x=0, y=6)
    theme_row.add_child(theme_switch)
    card.add_child(theme_row)
    
    # Text Field Showcase
    card.add_child(Label(text="Developer Username Profile:", font_size=13, bold=True))
    user_state = State("Marius")
    text_input = TextField(text=user_state, width=0.9, height=40)
    card.add_child(text_input)
    
    # Profile Card
    profile_box = VStack(spacing=6, padding=12, width=0.9, height=64, border_radius=10, background_color=iOSTheme.fill_secondary)
    profile_box.add_child(Label(text="Active Session User:", font_size=11, color=iOSTheme.secondary_label))
    
    user_lbl = Label(text="Marius", font_size=14, bold=True)
    user_state.bind(lambda v: setattr(user_lbl, "text", str(v)))
    
    profile_box.add_child(user_lbl)
    card.add_child(profile_box)
    
    return view

# ----------------------------------------------------------------------
# Page Builder 3: Features Overview Tab
# ----------------------------------------------------------------------
def build_features_page() -> FloatLayout:
    view = FloatLayout(width=1.0, height=1.0)
    
    card = VStack(
        spacing=20, padding=24, anchor="center", width=0.82, height=0.85,
        border_radius=18, background_color=iOSTheme.secondary_background
    )
    view.add_child(card)
    
    card.add_child(Label(text="OpenGUI Architectural Architecture", font_size=22, bold=True))
    
    # Descriptive items
    desc_list = [
        "1. Dynamic responsive layout with top-down constraint solvers.",
        "2. Spring physics on transitions; kinetic scroll on overflow.",
        "3. Standalone: app.run() — or embed: App(managed_display=False), attach(screen), frame().",
        "4. process_event() / process_events() forward native pygame input unchanged.",
        "5. PygameCanvas hosts arbitrary draw(surface, rect) + handle_event(event, rect) code.",
    ]
    for d in desc_list:
        card.add_child(Label(text=d, font_size=13, color=iOSTheme.label))
        
    return view

# ----------------------------------------------------------------------
# Scene Composition
# ----------------------------------------------------------------------
# Create PageRouter Page layouts registry
router = PageRouter(
    initial_page="playground",
    pages_registry={
        "playground": build_playground_page,
        "features": build_features_page,
        "settings": build_settings_page
    },
    anchor="top", x=0, y=64,
    width=1.0, height=0.835
)
app.root.add_child(router)

# Reactive transition binding connecting active_tab with PageRouter
def on_tab_swapped(index: int):
    page_names = ["playground", "features", "settings"]
    target_page = page_names[max(0, min(2, int(index)))]
    router.navigate(target_page, "auto")
    
active_tab.bind(on_tab_swapped)

# App Bar Header Block
app_bar = FloatLayout(anchor="top", x=0, y=0, width=1.0, height=64)
app.root.add_child(app_bar)

# Header Title Label
app_bar.add_child(Label(text="OpenGUI Catalog", font_size=18, bold=True, anchor="left", x=64, y=20))

# Drawer Slide-out Sidebar Anchor Left
drawer = SidebarDrawer(
    active_tab_state=active_tab,
    tabs=["Widget Playground", "Framework Features", "System Settings"],
    open_state=sidebar_open,
    width=240
)
app.root.add_child(drawer)

# Hamburger morph button
hamburger = HamburgerButton(
    open_state=sidebar_open,
    active_color=ColorPalette.BLUE,
    anchor="left", x=16, y=14, width=36, height=36
)
app_bar.add_child(hamburger)

# iOS Bottom Tab Navigation Bar
bottom_bar = BottomNavigationBar(
    active_tab_state=active_tab,
    items=[
        {"title": "Playground"},
        {"title": "Features"},
        {"title": "Settings"}
    ],
    height=60
)
app.root.add_child(bottom_bar)

# Global theme sync: settings switch ↔ entire UI (cards, labels, chrome)
dark_mode_state.bind(lambda is_dark: app.apply_theme(bool(is_dark)))

# Run Showcase (managed window). For your own loop, use:
#   app = App(..., managed_display=False); app.attach(screen)
#   app.process_events(events); app.frame(dt); pygame.display.flip()
if __name__ == "__main__":
    app.run()
