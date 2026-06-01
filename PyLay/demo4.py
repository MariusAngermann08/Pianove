"""
demo4.py — Reactive Declarative Component Showcase
Demonstrates:
- Fluid, object-free page definition DSL.
- Dynamic spring-physics PageRouter (lazy-loads and destroys page memories on-demand).
- Reactive 'State' variable bindings (updates labels, progress, checkboxes, text input instantly).
- High-fidelity TextField, ProgressBar, Checkbox, and RadioButton widgets.

Run with: python demo4.py
"""
import pygame
from pylay import (
    App, State, FloatLayout, VStack, Label, Button,
    TextField, ProgressBar, Checkbox, RadioButton, PageRouter,
    iOSTheme, ColorPalette
)

# 1. Initialize seamless Application manager
app = App(title="Reactive OpenUI Declarative Dashboard", width=1000, height=720, dark_mode=True)

# 2. Declare reactive global states (can be read/mutated from any page)
name_state = State("Marius")
terms_accepted = State(False)
progress_state = State(0.35)
active_accent = State(ColorPalette.BLUE)

# ---------------------------------------------------------------------------
# Page 1: Welcome & Text Input (Lazy Builder)
# ---------------------------------------------------------------------------
def build_home_page() -> FloatLayout:
    page_root = FloatLayout(width=1.0, height=1.0, background_color=pygame.Color(0,0,0,0))
    
    # Styled card container
    card = VStack(
        spacing=18, padding=24,
        anchor="center", x=0, y=0,
        width=0.76, height=0.9,
        border_radius=18, border_width=1,
        background_color=iOSTheme.secondary_background
    )
    page_root.add_child(card)
    
    card.add_child(Label(text="Reactive Onboarding", font_size=22, bold=True))
    card.add_child(Label(text="Frictionless reactive binding system — no object-oriented subclassing required.", 
                         font_size=12, color=iOSTheme.secondary_label))
    
    # Hello title: bound reactively to name_state changes!
    greeting = State(f"Hello, {name_state.value}!")
    name_state.bind(lambda v: setattr(greeting, "value", f"Hello, {v}!"))
    
    card.add_child(Label(text=greeting, font_size=20, bold=True, color=ColorPalette.BLUE))
    
    # Text entry field bound reactively
    card.add_child(Label(text="Edit Name below to see live synchronization:", font_size=13))
    card.add_child(TextField(text=name_state, placeholder="Enter your name...", width=0.88, height=44))
    
    # Checkbox Terms Agreement
    terms_row = FloatLayout(width=0.88, height=36)
    terms_row.add_child(Checkbox(value=terms_accepted, active_color=ColorPalette.GREEN, anchor="left", x=0, y=6))
    terms_row.add_child(Label(text="I accept the standard developer terms", font_size=13, anchor="left", x=36, y=10))
    card.add_child(terms_row)
    
    # Dynamic helper label that flips color and text based on agreement!
    status_text = State("Please accept the terms to unlock the control panel.")
    status_label = Label(text=status_text, font_size=12, color=ColorPalette.RED)
    
    def on_terms_change(accepted: bool):
        if accepted:
            status_text.value = "Terms Accepted! ✓ Proceed to Control Panel."
            status_label.color = ColorPalette.GREEN
        else:
            status_text.value = "Please accept the terms to unlock the control panel."
            status_label.color = ColorPalette.RED
            
    terms_accepted.bind(on_terms_change)
    card.add_child(status_label)
    
    # Transition navigation button (enables/disables reactively!)
    nav_btn = Button(
        text="Go to Controls Panel →",
        on_click=lambda: router.navigate("controls", "right"),
        width=0.88, height=46,
        background_color=ColorPalette.BLUE
    )
    
    # Bind button states dynamically
    def update_btn(accepted: bool):
        nav_btn.enabled = accepted
        nav_btn.background_color = ColorPalette.BLUE if accepted else ColorPalette.DARK_GRAY_3
        
    terms_accepted.bind(update_btn)
    card.add_child(nav_btn)
    
    return page_root

# ---------------------------------------------------------------------------
# Page 2: System Controls & Loading Progress (Lazy Builder)
# ---------------------------------------------------------------------------
def build_controls_page() -> FloatLayout:
    page_root = FloatLayout(width=1.0, height=1.0, background_color=pygame.Color(0,0,0,0))
    
    card = VStack(
        spacing=18, padding=24,
        anchor="center", x=0, y=0,
        width=0.76, height=0.9,
        border_radius=18, border_width=1,
        background_color=iOSTheme.secondary_background
    )
    page_root.add_child(card)
    
    card.add_child(Label(text="Reactive Control Center", font_size=22, bold=True))
    
    # Progress section
    card.add_child(Label(text="Simulated Task Progression:", font_size=14, bold=True))
    
    pct_text = State(f"Current completion level: {int(progress_state.value * 100)}%")
    progress_state.bind(lambda v: setattr(pct_text, "value", f"Current completion level: {int(v * 100)}%"))
    card.add_child(Label(text=pct_text, font_size=13, color=iOSTheme.secondary_label))
    
    # Progress bar filled reactively (with dynamic bar color!)
    progress_bar = ProgressBar(progress=progress_state, active_color=active_accent.value, width=0.88, height=10)
    active_accent.bind(lambda color: setattr(progress_bar, "active_color", color))
    card.add_child(progress_bar)
    
    # Button to step progression forward
    def increment_progress():
        next_val = progress_state.value + 0.15
        if next_val > 1.0:
            next_val = 0.0
        progress_state.value = next_val
        
    card.add_child(Button(
        text="Increment Progress Level (+15%)",
        on_click=increment_progress,
        width=0.88, height=40,
        background_color=ColorPalette.DARK_GRAY_3
    ))
    
    # Radio Choice Group (Theme Selector)
    card.add_child(Label(text="Select Interactive Theme Accent Color:", font_size=13, bold=True))
    
    color_choice = State("blue")
    
    def apply_color_choice(choice: str):
        if choice == "blue":
            active_accent.value = ColorPalette.BLUE
        elif choice == "purple":
            active_accent.value = ColorPalette.PURPLE
        elif choice == "green":
            active_accent.value = ColorPalette.GREEN
            
    color_choice.bind(apply_color_choice)
    
    radio_row = FloatLayout(width=0.88, height=40)
    
    # Blue Selector
    radio_row.add_child(RadioButton(group_state=color_choice, choice_value="blue", anchor="left", x=0, y=8))
    radio_row.add_child(Label(text="Blue", font_size=13, anchor="left", x=32, y=10))
    
    # Purple Selector
    radio_row.add_child(RadioButton(group_state=color_choice, choice_value="purple", anchor="left", x=120, y=8, active_color=ColorPalette.PURPLE))
    radio_row.add_child(Label(text="Purple", font_size=13, anchor="left", x=152, y=10))
    
    # Green Selector
    radio_row.add_child(RadioButton(group_state=color_choice, choice_value="green", anchor="left", x=240, y=8, active_color=ColorPalette.GREEN))
    radio_row.add_child(Label(text="Green", font_size=13, anchor="left", x=272, y=10))
    
    card.add_child(radio_row)
    
    # Back navigation button
    card.add_child(Button(
        text="← Back to Welcome Panel",
        on_click=lambda: router.navigate("home", "left"),
        width=0.88, height=46,
        background_color=ColorPalette.DARK_GRAY_2
    ))
    
    return page_root

# ---------------------------------------------------------------------------
# 3. Assemble root UI layout
# ---------------------------------------------------------------------------
root = FloatLayout(width=1.0, height=1.0)

# Modern iOS header title bar
header = FloatLayout(
    anchor="top", x=0, y=0, width=1.0, height=64,
    background_color=iOSTheme.secondary_background
)
root.add_child(header)

header.add_child(Label(text="OpenUI  ·  Declarative UI Platform", font_size=18, bold=True, anchor="top_left", x=24, y=20))

# Seamless light/dark toggle action
header.add_child(Button(
    text="Toggle Dark / Light",
    on_click=app.toggle_theme,
    anchor="top_right", x=-16, y=12,
    width=180, height=40,
    background_color=ColorPalette.DARK_GRAY_3,
    text_color=pygame.Color(255, 255, 255)
))

# 4. Instantiate animated lazy PageRouter
router = PageRouter(
    pages={
        "home": build_home_page,
        "controls": build_controls_page
    },
    initial_page="home",
    anchor="top", x=0, y=74,
    width=1.0, height=0.88
)
root.add_child(router)

if __name__ == "__main__":
    # Set main view and launch!
    app.set_root(root)
    app.run()

