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
lesson_hands_vis:     bool | None = None   # None → the saved preference
lesson_phase:         str        = "practice"   # "practice" | "performance"
lesson_completed:     bool       = False

# Song mode (set when user starts a custom imported song)
current_song_id:   str | None = None   # None → lesson mode
current_song_hand: str        = "right"  # "right" | "left" | "both"
# A step of the song's learning path (pianove/song_path.py): only these bars, and the
# stars it earns are kept. None → the whole song, practised freely
song_range:      tuple[int, int] | None = None
path_step:       str | None = None
path_last_stars: int        = 0

# Score viewer (set when user taps "View Score" on the songs tab)
score_song_id: str | None = None
score_return:  str | None = None     # the page "Back" in the score viewer goes to

# Inner tab router (home shell) — set by home/container.py so tabs can self-refresh
inner_router: "PageRouter | None" = None
# Page last opened from the sidebar, so a home-shell rebuild (theme change) stays there
home_page: str | None = None

# Sight-reading practice mode (go mode — performance-only, no practice sections)
practice_mode:      bool        = False
practice_bars:      list | None = None   # pre-generated bars
practice_bpm:       int         = 80
practice_clef:      str         = "treble"
practice_last_hits:  int        = 0      # filled when session completes
practice_last_total: int        = 0

# Creator Mode: the lesson and course being edited, and where "Back" in the lesson player
# goes while a lesson is being tested from the editor (None: not a test run)
editor_lesson_id:   str | None = None
editor_course_id:   str | None = None
lesson_test_return: str | None = None
lesson_beat_idx:    int        = 0      # a test run starts on this screen of the scene

# Today's session (pianove/session.py): set by a finish screen that moved the session on,
# so building that screen again doesn't move it twice
session_done_marker: tuple | None = None

# a short screen before the run in tempo ("tempo") or None
lesson_intro: str | None = None

# how the last run in tempo went (pages/lesson.store_result), for its finish screen
last_result: dict | None = None
