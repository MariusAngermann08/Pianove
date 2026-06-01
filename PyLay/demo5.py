"""
demo5.py — Interactive Morphing & Drawer Dashboard
Demonstrates:
- Vector-morphed HamburgerButton (morphs to 'X' via spring animation).
- Slide-out SidebarDrawer anchored left with click-to-close dimming backdrop.
- Spring-shifting BottomNavigationBar with active icon scale-bounces.
- Reactive Synchronization: Sidebar, Bottom Tabs, and PageRouter all bind
  to a single shared active_tab State variable!

Run with: python demo5.py
"""
import pygame
from pylay import (
    App, State, FloatLayout, VStack, Label, Button,
    TextField, ProgressBar, Checkbox, RadioButton, PageRouter,
    HamburgerButton, SidebarDrawer, BottomNavigationBar, Switch, Slider,
    LineChart, iOSTheme, ColorPalette
)

# 1. Initialize Application
app = App(title="OpenUI Morphing & Drawer Dashboard", width=1024, height=768, dark_mode=True)

# 2. Shared Reactive States
sidebar_open = State(False)
active_tab = State(0)
name_state = State("Marius")
volume_state = State(0.75)
system_loading = State(0.4)

# ---------------------------------------------------------------------------
# Tab Page Builders (Lazily loaded & garbage collected!)
# ---------------------------------------------------------------------------
def build_home_tab() -> FloatLayout:
    view = FloatLayout(width=1.0, height=1.0)
    card = VStack(
        spacing=18, padding=24, anchor="center", width=0.8, height=0.88,
        border_radius=18, background_color=iOSTheme.secondary_background
    )
    view.add_child(card)
    
    card.add_child(Label(text="Dashboard Welcome", font_size=24, bold=True))
    card.add_child(Label(text="Open the hamburger menu at the top-left to slide out the side navigation drawer.",
                         font_size=12, color=iOSTheme.secondary_label))
    
    # Reactive name greeting
    greeting = State(f"Welcome back, {name_state.value}!")
    name_state.bind(lambda v: setattr(greeting, "value", f"Welcome back, {v}!"))
    card.add_child(Label(text=greeting, font_size=18, color=ColorPalette.BLUE, bold=True))
    
    card.add_child(TextField(text=name_state, placeholder="Change greeting name...", width=0.8, height=44))
    
    # Simple direct button to trigger drawer slide-in manually
    card.add_child(Button(
        text="Open Slide Menu Drawer",
        on_click=lambda: sidebar_open.value.update(True) if hasattr(sidebar_open.value, "update") else setattr(sidebar_open, "value", True),
        width=0.8, height=44,
        background_color=ColorPalette.DARK_GRAY_3
    ))
    return view

def build_analytics_tab() -> FloatLayout:
    view = FloatLayout(width=1.0, height=1.0)
    card = VStack(
        spacing=18, padding=24, anchor="center", width=0.8, height=0.88,
        border_radius=18, background_color=iOSTheme.secondary_background
    )
    view.add_child(card)
    
    card.add_child(Label(text="System Analytics", font_size=24, bold=True))
    
    # Interactive checklist
    card.add_child(Label(text="Task Checklist (Circular iOS Reminders style):", font_size=13, bold=True))
    
    check_state = State(False)
    check_row = FloatLayout(width=0.8, height=36)
    check_row.add_child(Checkbox(value=check_state, active_color=ColorPalette.GREEN, anchor="left", x=0, y=6))
    
    check_label = State("Task: Pending approval")
    check_state.bind(lambda v: setattr(check_label, "value", "Task: Approved & Completed! ✓" if v else "Task: Pending approval"))
    check_lbl_widget = Label(text=check_label, font_size=13, anchor="left", x=36, y=10)
    check_state.bind(lambda v: setattr(check_lbl_widget, "color", ColorPalette.GREEN if v else iOSTheme.label))
    check_row.add_child(check_lbl_widget)
    card.add_child(check_row)
    
    # Premium Line Chart showing CPU Load trends
    card.add_child(Label(text="CPU Load Trend (Past Week):", font_size=13, bold=True))
    chart = LineChart(
        data=[12.0, 19.5, 8.4, 27.0, 15.2, 33.1, 45.0],
        labels=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        active_color=ColorPalette.BLUE,
        title="Server CPU Metrics (%)",
        width=0.8,
        height=180
    )
    card.add_child(chart)
    
    # Progress bar section
    card.add_child(Label(text="Processing Queue:", font_size=13, bold=True))
    prog_bar = ProgressBar(progress=system_loading, active_color=ColorPalette.PURPLE, width=0.8, height=10)
    card.add_child(prog_bar)
    
    def step_progress():
        next_val = system_loading.value + 0.2
        if next_val > 1.01:
            next_val = 0.0
        system_loading.value = next_val
        
    card.add_child(Button(
        text="Advance Queue (+20%)",
        on_click=step_progress,
        width=0.8, height=40,
        background_color=ColorPalette.DARK_GRAY_3
    ))
    return view

def build_settings_tab() -> FloatLayout:
    view = FloatLayout(width=1.0, height=1.0)
    card = VStack(
        spacing=18, padding=24, anchor="center", width=0.8, height=0.88,
        border_radius=18, background_color=iOSTheme.secondary_background
    )
    view.add_child(card)
    
    card.add_child(Label(text="System Preferences", font_size=24, bold=True))
    
    # Switch toggle row
    toggle_row = FloatLayout(width=0.8, height=44)
    toggle_row.add_child(Label(text="Enable Notification Pushes:", font_size=13, anchor="left", x=0, y=12))
    toggle_row.add_child(Switch(value=True, anchor="right", x=0, y=6))
    card.add_child(toggle_row)
    
    # Volume Slider row
    card.add_child(Label(text="Master Output Volume:", font_size=13, bold=True))
    vol_label = State(f"Level: {int(volume_state.value * 100)}%")
    volume_state.bind(lambda v: setattr(vol_label, "value", f"Level: {int(v * 100)}%"))
    card.add_child(Label(text=vol_label, font_size=12, color=iOSTheme.secondary_label))
    
    slider = Slider(value=volume_state.value, on_change=lambda v: setattr(volume_state, "value", v), width=0.8, height=32)
    card.add_child(slider)
    
    return view

# ---------------------------------------------------------------------------
# 3. Assemble Root Layout
# ---------------------------------------------------------------------------
root = FloatLayout(width=1.0, height=1.0)

# A. Header Bar
header = FloatLayout(anchor="top", x=0, y=0, width=1.0, height=64, background_color=iOSTheme.secondary_background)
root.add_child(header)

# Hamburger Morph Menu Button (Bound reactively to sidebar_open state!)
hamburger = HamburgerButton(open_state=sidebar_open, anchor="top_left", x=12, y=12)
header.add_child(hamburger)

header.add_child(Label(text="OpenUI Custom Showcase", font_size=18, bold=True, anchor="top_left", x=64, y=20))

# Standard Dark/Light theme toggle
header.add_child(Button(
    text="Toggle Dark/Light",
    on_click=app.toggle_theme,
    anchor="top_right", x=-16, y=12,
    width=160, height=40,
    background_color=ColorPalette.DARK_GRAY_3
))

# B. Center Dynamic Page Router (Lazy loaded, synced to active_tab!)
router = PageRouter(
    pages={
        "home": build_home_tab,
        "analytics": build_analytics_tab,
        "settings": build_settings_tab
    },
    initial_page="home",
    anchor="top", x=0, y=64,
    width=1.0, height=0.835
)
root.add_child(router)

# Reactive transition sync when active_tab state shifts
def on_tab_changed(index: int):
    page_names = ["home", "analytics", "settings"]
    target_page = page_names[max(0, min(2, int(index)))]
    # Animate page slides right/left based on index movement
    router.navigate(target_page, "auto")
    
active_tab.bind(on_tab_changed)

# C. Spring-Shifting Bottom Navigation Bar
bottom_bar = BottomNavigationBar(
    active_tab_state=active_tab,
    items=[
        {"title": "Welcome"},
        {"title": "Analytics"},
        {"title": "Preferences"}
    ]
)
root.add_child(bottom_bar)

# D. Slide-Out Sidebar Drawer (Bound reactively to sidebar_open state!)
sidebar = SidebarDrawer(open_state=sidebar_open, width=280)
root.add_child(sidebar)

# Add navigation options inside the sidebar VStack panel
sidebar_list = VStack(spacing=14, padding=20, anchor="top_left", x=0, y=64, width=1.0, height=0.8)
sidebar.add_child(sidebar_list)

sidebar_list.add_child(Label(text="NAVIGATION MENU", font_size=12, bold=True, color=iOSTheme.secondary_label))

# Helper: clicking options updates tab index and closes sidebar drawer
def select_menu_option(tab_index: int):
    # Close instantly to prevent visual drawer overlaps during page slide-and-fades
    sidebar.slide_progress = 0.0
    sidebar.visible = False
    sidebar_open.value = False
    active_tab.value = tab_index

sidebar_list.add_child(Button(text="Welcome Dashboard", on_click=lambda: select_menu_option(0), width=0.9, height=42))
sidebar_list.add_child(Button(text="System Analytics", on_click=lambda: select_menu_option(1), width=0.9, height=42))
sidebar_list.add_child(Button(text="System Preferences", on_click=lambda: select_menu_option(2), width=0.9, height=42))

if __name__ == "__main__":
    app.set_root(root)
    app.run()
