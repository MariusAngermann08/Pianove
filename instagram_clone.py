"""
Instagram UI clone built with PyLay.
Run:  python instagram_clone.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "PyLay"))

import pygame
from pylay import (
    App, State, FloatLayout, VStack, Label, Button,
    PageRouter, BottomNavigationBar, ScrollableCanvas,
    PygameCanvas, iOSTheme, ColorPalette, TextField
)

# ── Window ────────────────────────────────────────────────────────────
W, H       = 430, 900
BOTTOM_H   = 60
HEADER_H   = 56
FEED_H     = H - BOTTOM_H - HEADER_H  # pixels available to scroll area

# ── Instagram accent colours ──────────────────────────────────────────
IG_PINK   = (214,  41, 118)
IG_ORANGE = (250, 126,  30)
IG_PURPLE = (150,  47, 191)
IG_BLUE   = (  0, 149, 246)
SEP_COL   = ( 38,  38,  40)   # dark separator

# ── Data ──────────────────────────────────────────────────────────────
STORIES = [
    {"name": "Your Story", "color": (55, 55, 58),   "ring": False,  "seen": False},
    {"name": "alex_m",     "color": (255,  80,  40), "ring": True,   "seen": False},
    {"name": "maria.k",    "color": (200,  50, 200), "ring": True,   "seen": False},
    {"name": "travel.v",   "color": ( 50, 150, 255), "ring": True,   "seen": True},
    {"name": "food.lab",   "color": (255, 200,   0), "ring": True,   "seen": False},
    {"name": "photo_art",  "color": (  0, 200, 150), "ring": True,   "seen": True},
    {"name": "city_run",   "color": (255,  80, 120), "ring": True,   "seen": False},
]

POSTS = [
    {
        "user": "alex_m",    "avatar": (255,  80,  40),
        "loc":  "Milan, Italy",
        "bg":   ( 28,  55, 130),  "emoji": "🏛",
        "likes": 2_847, "liked": False, "comments": 47,
        "caption": "Discovering hidden gems in Milan — the architecture is breathtaking! ✨",
        "time": "2h",
    },
    {
        "user": "maria.k",   "avatar": (200,  50, 200),
        "loc":  "Tokyo, Japan",
        "bg":   (200,  50,  80),  "emoji": "🌸",
        "likes": 5_621, "liked": True,  "comments": 183,
        "caption": "Cherry blossom season is pure magic 🌸  #sakura #tokyo #spring",
        "time": "5h",
    },
    {
        "user": "food.lab",  "avatar": (255, 200,   0),
        "loc":  "New York, USA",
        "bg":   (180,  90,  20),  "emoji": "🍕",
        "likes": 1_203, "liked": False, "comments": 39,
        "caption": "Best pizza in NYC — fight me 🍕",
        "time": "8h",
    },
    {
        "user": "city_run",  "avatar": (255,  80, 120),
        "loc":  "Barcelona, Spain",
        "bg":   ( 20, 140,  80),  "emoji": "🌊",
        "likes":   891, "liked": False, "comments": 21,
        "caption": "Morning run along the waterfront. Worth every early alarm 🏃‍♂️",
        "time": "1d",
    },
]

EXPLORE_TILES = [
    ("🏛", ( 28,  55, 130)), ("🌸", (200,  50,  80)), ("🍕", (180,  90,  20)),
    ("🌊", ( 20, 140,  80)), ("🌅", (255, 130,  30)), ("🦋", (130,  50, 200)),
    ("🎸", ( 80,  80, 200)), ("🏔", ( 50, 100, 160)), ("🍜", (180,  60,  40)),
    ("🌿", ( 30, 160,  80)), ("🎭", (160,  40, 120)), ("🌙", ( 40,  40,  90)),
]

NOTIFS = [
    {"user": "alex_m",   "color": (255, 80, 40),  "action": "liked your photo.",        "time": "2m",  "type": "like"},
    {"user": "maria.k",  "color": (200, 50, 200), "action": "commented: 'So beautiful 😍'", "time": "15m", "type": "comment"},
    {"user": "food.lab", "color": (255,200,  0),  "action": "started following you.",    "time": "1h",  "type": "follow"},
    {"user": "city_run", "color": (255, 80,120),  "action": "liked your photo.",         "time": "2h",  "type": "like"},
    {"user": "photo_art","color": (  0,200,150),  "action": "mentioned you in a comment.","time": "3h",  "type": "mention"},
    {"user": "travel.v", "color": ( 50,150,255),  "action": "started following you.",    "time": "1d",  "type": "follow"},
    {"user": "alex_m",   "color": (255, 80, 40),  "action": "saved your post.",          "time": "1d",  "type": "save"},
    {"user": "maria.k",  "color": (200, 50,200),  "action": "liked your photo.",         "time": "2d",  "type": "like"},
]

PROFILE = {
    "username": "your_name",
    "name":     "Your Name",
    "bio":      "Living my best life 📸\nPhotography | Travel | Food",
    "posts":    42,
    "followers": "1.2K",
    "following": 318,
    "avatar":   (100, 100, 220),
    "highlights": [
        ("Travel",   ( 50, 150, 255)),
        ("Food",     (255, 200,   0)),
        ("Friends",  (255,  80, 120)),
        ("Nature",   ( 20, 140,  80)),
        ("Art",      (150,  47, 191)),
    ],
    "grid": [
        (( 28,  55, 130), "🏛"), ((200,  50,  80), "🌸"), ((180,  90,  20), "🍕"),
        (( 20, 140,  80), "🌊"), ((255, 130,  30), "🌅"), ((130,  50, 200), "🦋"),
        (( 80,  80, 200), "🎸"), (( 50, 100, 160), "🏔"), ((180,  60,  40), "🍜"),
    ],
}

# ── Font cache ────────────────────────────────────────────────────────
_FC: dict = {}
def _f(size: int, bold: bool = False) -> pygame.font.Font:
    k = (size, bold)
    if k not in _FC:
        _FC[k] = pygame.font.SysFont("Arial", size, bold=bold)
    return _FC[k]

# ── Drawing primitives ────────────────────────────────────────────────
def _circle(surf, cx, cy, r, color):
    pygame.draw.circle(surf, color, (cx, cy), r)

def _ring(surf, cx, cy, r, color):
    pygame.draw.circle(surf, color, (cx, cy), r + 3, width=3)

def _text(surf, txt, font, color, x, y, align="left", max_w=0):
    ts = font.render(txt, True, color)
    if max_w and ts.get_width() > max_w:
        while ts.get_width() > max_w - 10 and len(txt) > 4:
            txt = txt[:-4] + "…"
            ts = font.render(txt, True, color)
    if align == "center":
        surf.blit(ts, (x - ts.get_width() // 2, y))
    elif align == "right":
        surf.blit(ts, (x - ts.get_width(), y))
    else:
        surf.blit(ts, (x, y))

def _avatar(surf, cx, cy, r, color, initial="?"):
    _circle(surf, cx, cy, r, color)
    _text(surf, initial.upper(), _f(r, bold=True), (255, 255, 255),
          cx, cy - r // 2, align="center")

def _gradient_rect(surf, rect, top_col, bot_col=None):
    if bot_col is None:
        bot_col = tuple(max(0, c - 50) for c in top_col)
    x, y, w, h = rect
    for i in range(h):
        t   = i / max(h - 1, 1)
        col = tuple(int(top_col[j] * (1 - t) + bot_col[j] * t) for j in range(3))
        pygame.draw.line(surf, col, (x, y + i), (x + w - 1, y + i))

def _truncate(txt, font, max_w):
    if font.size(txt)[0] <= max_w:
        return txt
    while len(txt) > 4 and font.size(txt + "…")[0] > max_w:
        txt = txt[:-1]
    return txt + "…"

# ── Stories bar ───────────────────────────────────────────────────────
STORY_BAR_H = 106
STORY_R     = 32

def _draw_stories(surf, x, y, w):
    surf.fill(iOSTheme.background, (x, y, w, STORY_BAR_H))
    slot_w = min(80, w // len(STORIES))
    for i, s in enumerate(STORIES):
        cx = x + i * slot_w + slot_w // 2
        cy = y + 36
        if s["ring"]:
            ring_col = SEP_COL if s["seen"] else IG_PINK
            pygame.draw.circle(surf, ring_col, (cx, cy), STORY_R + 3)
        _avatar(surf, cx, cy, STORY_R, s["color"], s["name"][0])
        if s["name"] == "Your Story":
            pygame.draw.circle(surf, IG_BLUE, (cx + STORY_R - 8, cy + STORY_R - 8), 10)
            _text(surf, "+", _f(14, bold=True), (255, 255, 255),
                  cx + STORY_R - 8, cy + STORY_R - 8 - 7, align="center")
        name = _truncate(s["name"], _f(10), slot_w - 4)
        _text(surf, name, _f(10), iOSTheme.label,
              cx, cy + STORY_R + 8, align="center")

# ── Single post ───────────────────────────────────────────────────────
POST_HEADER_H  = 56
POST_IMG_RATIO = 1.0       # square posts
POST_ACTION_H  = 52
POST_CAPTION_H = 50

def _post_height(w):
    return POST_HEADER_H + int(w * POST_IMG_RATIO) + POST_ACTION_H + POST_CAPTION_H

def _draw_post(surf, post, x, y, w):
    img_h = int(w * POST_IMG_RATIO)
    bg    = tuple(iOSTheme.background)[:3]

    # ── header ──────────────────────────────────────────────────────
    surf.fill(bg, (x, y, w, POST_HEADER_H))
    _avatar(surf, x + 28, y + 28, 20, post["avatar"], post["user"][0])
    _text(surf, post["user"], _f(14, bold=True), iOSTheme.label, x + 56, y + 13)
    _text(surf, post["loc"], _f(11), iOSTheme.secondary_label, x + 56, y + 31)
    _text(surf, "•••", _f(16, bold=True), iOSTheme.label, x + w - 30, y + 20, align="right")

    # ── image ────────────────────────────────────────────────────────
    iy = y + POST_HEADER_H
    _gradient_rect(surf, (x, iy, w, img_h), post["bg"])
    ef   = _f(min(img_h // 2, 96))
    etxt = ef.render(post["emoji"], True, (255, 255, 255))
    surf.blit(etxt, etxt.get_rect(center=(x + w // 2, iy + img_h // 2)))

    # ── action row ───────────────────────────────────────────────────
    ay = iy + img_h
    surf.fill(bg, (x, ay, w, POST_ACTION_H))
    heart_col = (237, 73, 86) if post["liked"] else tuple(iOSTheme.label)[:3]
    heart_sym = "♥" if post["liked"] else "♡"
    _text(surf, heart_sym, _f(26), heart_col, x + 14, ay + 12)
    _text(surf, "💬", _f(20), iOSTheme.label, x + 52, ay + 14)
    _text(surf, "✈", _f(22), iOSTheme.label, x + 88, ay + 13)
    _text(surf, "🔖", _f(20), iOSTheme.label, x + w - 16, ay + 14, align="right")

    # ── likes & caption ──────────────────────────────────────────────
    cy_ = ay + POST_ACTION_H
    surf.fill(bg, (x, cy_, w, POST_CAPTION_H))
    likes_str = f"{post['likes']:,} likes"
    _text(surf, likes_str, _f(13, bold=True), iOSTheme.label, x + 14, cy_)
    cap = _truncate(post["caption"], _f(12), w - 28)
    _text(surf, cap, _f(12), iOSTheme.label, x + 14, cy_ + 18)
    _text(surf, f"View all {post['comments']} comments", _f(11),
          iOSTheme.secondary_label, x + 14, cy_ + 34)

    # ── separator ────────────────────────────────────────────────────
    pygame.draw.line(surf, SEP_COL, (x, cy_ + POST_CAPTION_H - 1),
                     (x + w, cy_ + POST_CAPTION_H - 1))

# ── Feed content ──────────────────────────────────────────────────────
class FeedContent:
    dirty = False

    def content_height(self, canvas_w):
        ph = sum(_post_height(canvas_w) for _ in POSTS)
        return STORY_BAR_H + 1 + ph + 24

    def draw(self, surf, rect):
        w = rect.width
        surf.fill(iOSTheme.background)
        y = 0
        _draw_stories(surf, 0, y, w)
        y += STORY_BAR_H
        pygame.draw.line(surf, SEP_COL, (0, y), (w, y))
        y += 1
        for post in POSTS:
            _draw_post(surf, post, 0, y, w)
            y += _post_height(w)

# ── Explore content ───────────────────────────────────────────────────
EXPLORE_COLS = 3

class ExploreContent:
    dirty = False

    def content_height(self, canvas_w):
        tile_w = canvas_w // EXPLORE_COLS
        rows   = (len(EXPLORE_TILES) + EXPLORE_COLS - 1) // EXPLORE_COLS
        return rows * tile_w + 4

    def draw(self, surf, rect):
        w      = rect.width
        tile_w = w // EXPLORE_COLS
        surf.fill(iOSTheme.background)
        for i, (emoji, bg) in enumerate(EXPLORE_TILES):
            col = i % EXPLORE_COLS
            row = i // EXPLORE_COLS
            tx  = col * tile_w + 1
            ty  = row * tile_w + 1
            tw  = tile_w - 2
            _gradient_rect(surf, (tx, ty, tw, tw), bg)
            ef   = _f(min(tw // 2, 48))
            etxt = ef.render(emoji, True, (255, 255, 255))
            surf.blit(etxt, etxt.get_rect(center=(tx + tw // 2, ty + tw // 2)))

# ── Notifications content ─────────────────────────────────────────────
NOTIF_ROW_H = 68

class NotifContent:
    dirty = False

    def content_height(self, canvas_w):
        return len(NOTIFS) * NOTIF_ROW_H + 16

    def draw(self, surf, rect):
        w = rect.width
        surf.fill(iOSTheme.background)
        type_icon = {"like": "♥", "comment": "💬", "follow": "👤",
                     "mention": "@", "save": "🔖"}
        type_col  = {"like": (237, 73, 86), "comment": IG_BLUE,
                     "follow": (52, 199, 89), "mention": IG_PURPLE, "save": (255, 204, 0)}
        for i, n in enumerate(NOTIFS):
            y   = i * NOTIF_ROW_H + 8
            col = n["color"]
            _avatar(surf, 30, y + 30, 22, col, n["user"][0])
            # type indicator badge
            ic     = type_icon.get(n["type"], "•")
            ic_col = type_col.get(n["type"], (200, 200, 200))
            _circle(surf, 46, y + 46, 11, ic_col)
            _text(surf, ic, _f(11, bold=True), (255, 255, 255), 46, y + 39, align="center")
            _text(surf, n["user"], _f(13, bold=True), iOSTheme.label, 62, y + 14)
            action = _truncate(n["action"], _f(12), w - 120)
            _text(surf, action, _f(12), iOSTheme.secondary_label, 62, y + 31)
            _text(surf, n["time"], _f(11), iOSTheme.secondary_label, w - 14, y + 22, align="right")
            pygame.draw.line(surf, SEP_COL, (62, y + NOTIF_ROW_H - 1), (w, y + NOTIF_ROW_H - 1))

# ── Profile content ───────────────────────────────────────────────────
PROFILE_HEADER_H = 260
HIGHLIGHT_H      = 100

class ProfileContent:
    dirty = False

    def content_height(self, canvas_w):
        tile_w = canvas_w // 3
        rows   = (len(PROFILE["grid"]) + 2) // 3
        return PROFILE_HEADER_H + HIGHLIGHT_H + 1 + rows * tile_w + 4

    def draw(self, surf, rect):
        w  = rect.width
        P  = PROFILE
        surf.fill(iOSTheme.background)

        # Avatar
        _avatar(surf, w // 2, 56, 46, P["avatar"], P["username"][0])
        pygame.draw.circle(surf, IG_PINK, (w // 2, 56), 50, width=3)

        # Name & bio
        _text(surf, P["name"],     _f(16, bold=True), iOSTheme.label, w // 2, 110, align="center")
        for li, line in enumerate(P["bio"].split("\n")):
            _text(surf, line, _f(12), iOSTheme.secondary_label, w // 2, 130 + li * 16, align="center")

        # Stats row
        stat_y = 175
        for idx, (label, val) in enumerate(
                [("Posts", str(P["posts"])), ("Followers", P["followers"]),
                 ("Following", str(P["following"]))]):
            sx = (idx + 1) * w // 4
            _text(surf, str(val), _f(17, bold=True), iOSTheme.label, sx, stat_y, align="center")
            _text(surf, label,    _f(11), iOSTheme.secondary_label, sx, stat_y + 20, align="center")

        # Edit profile button
        bx, bw, bh = 16, w - 32, 32
        pygame.draw.rect(surf, SEP_COL, (bx, 215, bw, bh), border_radius=8)
        _text(surf, "Edit Profile", _f(13, bold=True), iOSTheme.label, w // 2, 224, align="center")

        # Highlights
        hy = PROFILE_HEADER_H + 8
        hs = 56
        slot = w // max(len(P["highlights"]), 1)
        for i, (hlabel, hcol) in enumerate(P["highlights"]):
            hx = i * slot + slot // 2
            pygame.draw.circle(surf, IG_PINK, (hx, hy + hs // 2), hs // 2 + 2, width=2)
            _avatar(surf, hx, hy + hs // 2, hs // 2 - 2, hcol, hlabel[0])
            _text(surf, hlabel[:6], _f(10), iOSTheme.label, hx, hy + hs + 4, align="center")

        # Grid separator
        gy = PROFILE_HEADER_H + HIGHLIGHT_H
        pygame.draw.line(surf, SEP_COL, (0, gy), (w, gy))
        gy += 1

        # Post grid
        tile_w = w // 3
        for i, (gbg, gemoji) in enumerate(P["grid"]):
            col = i % 3
            row = i // 3
            tx  = col * tile_w + 1
            ty  = gy + row * tile_w + 1
            tw  = tile_w - 2
            _gradient_rect(surf, (tx, ty, tw, tw), gbg)
            ef   = _f(min(tw // 3, 28))
            etxt = ef.render(gemoji, True, (255, 255, 255))
            surf.blit(etxt, etxt.get_rect(center=(tx + tw // 2, ty + tw // 2)))

# ── Header bar builders ───────────────────────────────────────────────
def _ig_logo_canvas(width):
    """Draws the 'Instagram' wordmark in a PygameCanvas."""
    class LogoDrawer:
        def draw(self, surf, rect):
            surf.fill(iOSTheme.background, rect)
            _text(surf, "Instagram", _f(26, bold=True), iOSTheme.label,
                  rect.centerx, rect.centery - 13, align="center")
        def handle_event(self, *_): return False

    return PygameCanvas(target=LogoDrawer(), anchor="top", x=0, y=0,
                        width=width, height=HEADER_H)

# ── Page builders ─────────────────────────────────────────────────────
def build_home() -> FloatLayout:
    page = FloatLayout(width=1.0, height=1.0)

    # Header
    hdr = FloatLayout(anchor="top", x=0, y=0, width=1.0, height=HEADER_H,
                      background_color=iOSTheme.secondary_background, border_radius=0)
    hdr.add_child(Label("Instagram", font_size=22, bold=True,
                        anchor="center", x=0, y=-8))
    hdr.add_child(Label("📷  ✈", font_size=18,
                        anchor="right", x=-16, y=-8))
    page.add_child(hdr)

    # Scrollable feed
    feed = ScrollableCanvas(
        target=FeedContent(),
        anchor="top", x=0, y=HEADER_H,
        width=1.0, height=1.0 - HEADER_H / H
    )
    page.add_child(feed)
    return page


def build_explore() -> FloatLayout:
    page = FloatLayout(width=1.0, height=1.0)

    hdr = FloatLayout(anchor="top", x=0, y=0, width=1.0, height=HEADER_H,
                      background_color=iOSTheme.secondary_background, border_radius=0)
    hdr.add_child(Label("🔍  Search", font_size=15,
                        color=iOSTheme.secondary_label,
                        anchor="center", x=0, y=-8))
    page.add_child(hdr)

    grid = ScrollableCanvas(
        target=ExploreContent(),
        anchor="top", x=0, y=HEADER_H,
        width=1.0, height=1.0 - HEADER_H / H
    )
    page.add_child(grid)
    return page


def build_new_post() -> FloatLayout:
    page = FloatLayout(width=1.0, height=1.0)
    card = VStack(spacing=20, padding=32, anchor="center", width=0.88, height=320,
                  border_radius=20, background_color=iOSTheme.secondary_background)
    card.add_child(Label("📸", font_size=48))
    card.add_child(Label("Create New Post", font_size=20, bold=True))
    card.add_child(Label("Choose a photo from your library\nor take a new one.",
                         font_size=13, color=iOSTheme.secondary_label))
    card.add_child(Button("Open Camera Roll", width=0.85, height=44,
                          background_color=ColorPalette.PINK))
    page.add_child(card)
    return page


def build_notifs() -> FloatLayout:
    page = FloatLayout(width=1.0, height=1.0)

    hdr = FloatLayout(anchor="top", x=0, y=0, width=1.0, height=HEADER_H,
                      background_color=iOSTheme.secondary_background, border_radius=0)
    hdr.add_child(Label("Activity", font_size=20, bold=True,
                        anchor="center", x=0, y=-8))
    page.add_child(hdr)

    notif_list = ScrollableCanvas(
        target=NotifContent(),
        anchor="top", x=0, y=HEADER_H,
        width=1.0, height=1.0 - HEADER_H / H
    )
    page.add_child(notif_list)
    return page


def build_profile() -> FloatLayout:
    page = FloatLayout(width=1.0, height=1.0)

    hdr = FloatLayout(anchor="top", x=0, y=0, width=1.0, height=HEADER_H,
                      background_color=iOSTheme.secondary_background, border_radius=0)
    hdr.add_child(Label(PROFILE["username"], font_size=16, bold=True,
                        anchor="center", x=0, y=-8))
    hdr.add_child(Label("☰", font_size=22, anchor="right", x=-16, y=-8))
    page.add_child(hdr)

    prof = ScrollableCanvas(
        target=ProfileContent(),
        anchor="top", x=0, y=HEADER_H,
        width=1.0, height=1.0 - HEADER_H / H
    )
    page.add_child(prof)
    return page

# ── App assembly ──────────────────────────────────────────────────────
app       = App("Instagram", width=W, height=H, dark_mode=True)
active_tab = State(0)

router = PageRouter(
    initial_page="home",
    pages_registry={
        "home":    build_home,
        "explore": build_explore,
        "new":     build_new_post,
        "notifs":  build_notifs,
        "profile": build_profile,
    },
    anchor="top", x=0, y=0,
    width=1.0, height=(H - BOTTOM_H) / H
)
app.root.add_child(router)

PAGES = ["home", "explore", "new", "notifs", "profile"]

def _on_tab(idx: int):
    router.navigate(PAGES[idx], "auto")

active_tab.bind(_on_tab)

nav = BottomNavigationBar(
    active_tab_state=active_tab,
    items=[
        {"title": "Home"},
        {"title": "Search"},
        {"title": "＋ Post"},
        {"title": "Activity"},
        {"title": "Profile"},
    ],
    height=BOTTOM_H,
)
app.root.add_child(nav)

if __name__ == "__main__":
    app.run()
