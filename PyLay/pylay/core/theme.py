import pygame

class ColorPalette:
    # Standard iOS Colors
    BLUE = pygame.Color(0, 122, 255)       # System Blue
    GREEN = pygame.Color(52, 199, 89)      # System Green
    RED = pygame.Color(255, 59, 48)        # System Red
    ORANGE = pygame.Color(255, 149, 0)     # System Orange
    YELLOW = pygame.Color(255, 204, 0)     # System Yellow
    TEAL = pygame.Color(48, 176, 199)      # System Teal
    PURPLE = pygame.Color(175, 82, 222)    # System Purple
    PINK = pygame.Color(255, 45, 85)       # System Pink
    
    # Grays (Dark Mode)
    DARK_GRAY_1 = pygame.Color(142, 142, 147)
    DARK_GRAY_2 = pygame.Color(99, 99, 102)
    DARK_GRAY_3 = pygame.Color(72, 72, 74)
    DARK_GRAY_4 = pygame.Color(48, 48, 50)
    DARK_GRAY_5 = pygame.Color(28, 28, 30)
    DARK_GRAY_6 = pygame.Color(18, 18, 20)

    # Grays (Light Mode)
    LIGHT_GRAY_1 = pygame.Color(142, 142, 147)
    LIGHT_GRAY_2 = pygame.Color(174, 174, 178)
    LIGHT_GRAY_3 = pygame.Color(199, 199, 204)
    LIGHT_GRAY_4 = pygame.Color(209, 209, 214)
    LIGHT_GRAY_5 = pygame.Color(229, 229, 234)
    LIGHT_GRAY_6 = pygame.Color(242, 242, 247)


class Theme:
    def __init__(self, dark: bool = True):
        self.dark = dark
        
        # Initialize persistent color objects once (allows global in-place update propagation)
        self.background = pygame.Color(0, 0, 0)
        self.secondary_background = pygame.Color(0, 0, 0)
        self.tertiary_background = pygame.Color(0, 0, 0)
        
        self.label = pygame.Color(0, 0, 0)
        self.secondary_label = pygame.Color(0, 0, 0, 0)
        self.tertiary_label = pygame.Color(0, 0, 0, 0)
        
        self.fill = pygame.Color(0, 0, 0, 0)
        self.fill_secondary = pygame.Color(0, 0, 0, 0)
        self.fill_tertiary = pygame.Color(0, 0, 0, 0)
        
        self.accent = pygame.Color(0, 0, 0)
        self.success = pygame.Color(0, 0, 0)
        self.warning = pygame.Color(0, 0, 0)
        self.danger = pygame.Color(0, 0, 0)
        
        self.update_theme()
        
    def update_theme(self):
        if self.dark:
            # Backgrounds
            self.background.update(18, 18, 20)           # ColorPalette.DARK_GRAY_6
            self.secondary_background.update(28, 28, 30) # ColorPalette.DARK_GRAY_5
            self.tertiary_background.update(48, 48, 50)  # ColorPalette.DARK_GRAY_4
            
            # Label/Text Colors
            self.label.update(255, 255, 255)
            self.secondary_label.update(235, 235, 245, 153) # 60% white
            self.tertiary_label.update(235, 235, 245, 76)    # 30% white
            
            # Active element backgrounds (Translucent gray)
            self.fill.update(120, 120, 128, 90)              # 36% opacity
            self.fill_secondary.update(120, 120, 128, 60)    # 24% opacity
            self.fill_tertiary.update(120, 120, 128, 40)     # 16% opacity
            
        else:
            # Backgrounds
            self.background.update(255, 255, 255)
            self.secondary_background.update(242, 242, 247) # ColorPalette.LIGHT_GRAY_6
            self.tertiary_background.update(229, 229, 234)  # ColorPalette.LIGHT_GRAY_5
            
            # Label/Text Colors
            self.label.update(0, 0, 0)
            self.secondary_label.update(60, 60, 67, 153)     # 60% black
            self.tertiary_label.update(60, 60, 67, 76)        # 30% black
            
            # Active element backgrounds
            self.fill.update(120, 120, 128, 50)              # 20% opacity
            self.fill_secondary.update(120, 120, 128, 30)    # 12% opacity
            self.fill_tertiary.update(120, 120, 128, 15)     # 6% opacity

        self.accent.update(0, 122, 255)                      # System Blue
        self.success.update(52, 199, 89)                     # System Green
        self.warning.update(255, 149, 0)                     # System Orange
        self.danger.update(255, 59, 48)                      # System Red


class PianoveTheme(Theme):
    """
    Branded theme for the Pianove application.

    Matches the docs site palette — gold/amber accent, pure near-black
    backgrounds in dark mode, warm off-white surfaces in light mode.

    Dark                          Light
    ──────────────────────────    ──────────────────────────
    bg           #0f0f0f          #ffffff
    bg-alt       #181818          #f4f4f4
    surface      #222222          #ebebeb
    border       #2e2e2e          #d0d0d0
    text         #efefef          #111111
    text-sec     #c0c0c0          #3d3d3d
    muted        #6e6e6e          #777777
    accent       #d4a017          #b07d0a
    """

    def update_theme(self):
        if self.dark:
            self.background.update(15, 15, 15)             # #0f0f0f
            self.secondary_background.update(24, 24, 24)   # #181818
            self.tertiary_background.update(34, 34, 34)    # #222222

            self.label.update(239, 239, 239)                # #efefef
            self.secondary_label.update(192, 192, 192, 160) # #c0c0c0 ~63%
            self.tertiary_label.update(110, 110, 110, 200)  # #6e6e6e muted

            self.fill.update(46, 46, 46, 220)               # #2e2e2e border tone
            self.fill_secondary.update(46, 46, 46, 140)
            self.fill_tertiary.update(46, 46, 46, 70)

            self.accent.update(212, 160, 23)                # #d4a017 gold
        else:
            self.background.update(255, 255, 255)           # #ffffff
            self.secondary_background.update(244, 244, 244) # #f4f4f4
            self.tertiary_background.update(235, 235, 235)  # #ebebeb

            self.label.update(17, 17, 17)                   # #111111
            self.secondary_label.update(61, 61, 61, 210)    # #3d3d3d
            self.tertiary_label.update(119, 119, 119, 180)  # #777777 muted

            self.fill.update(208, 208, 208, 220)            # #d0d0d0 border tone
            self.fill_secondary.update(208, 208, 208, 140)
            self.fill_tertiary.update(208, 208, 208, 70)

            self.accent.update(176, 125, 10)                # #b07d0a gold

        self.success.update(52, 199, 89)
        self.warning.update(255, 149, 0)
        self.danger.update(255, 59, 48)


# Global theme instance — used by all PyLay widgets
iOSTheme = PianoveTheme(dark=True)
