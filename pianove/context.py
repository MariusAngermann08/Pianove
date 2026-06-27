from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pylay import App, PageRouter

router: "PageRouter | None" = None
ui: "App | None" = None
current_lesson_id:    str       = "welcome"
current_course_id:    str | None = None
current_course_index: int        = 0
lesson_step_idx:      int        = 0   # which step in steps.json (text/demo/exercise)
lesson_current_idx:   int        = 0
lesson_section_idx:   int        = 0
lesson_keyboard_vis:  bool       = True
lesson_phase:         str        = "practice"   # "practice" | "performance"
lesson_completed:     bool       = False

# Song mode (set when user starts a custom imported song)
current_song_id:   str | None = None   # None → lesson mode
current_song_hand: str        = "right"  # "right" | "left" | "both"

# Score viewer (set when user taps "View Score" on the songs tab)
score_song_id: str | None = None

# Inner tab router (home shell) — set by home/container.py so tabs can self-refresh
inner_router: "PageRouter | None" = None

# Sight-reading practice mode (go mode — performance-only, no practice sections)
practice_mode:      bool        = False
practice_bars:      list | None = None   # pre-generated bars
practice_bpm:       int         = 80
practice_clef:      str         = "treble"
practice_last_hits:  int        = 0      # filled when session completes
practice_last_total: int        = 0
