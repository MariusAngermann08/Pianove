# Pianove Lesson & Course Format

Lessons and courses are plain folders of JSON files: readable, diff-friendly and easy to share. You can write them by hand, or make them in the app with **Creator Mode** (Settings → Content Creator → Creator Mode, then the **Create** tab).

---

## Where they live

```
pianove/lessons/<id>/                 built-in lessons (ship with the app, read-only)
pianove/courses/<id>/                 built-in courses
~/.pianove/packages/lessons/<id>/     your lessons: made in the editor or imported
~/.pianove/packages/courses/<id>/     your courses
```

Both places are scanned every time the Lessons tab is shown, so a lesson saved in your folder appears straight away. A lesson in your folder with the same id as a built-in one replaces it ("patch"). Progress is stored by lesson id, which is why the editor never renames a lesson and duplicates a built-in lesson under a new id (`welcome_copy`).

---

## Lesson folder

```
lessons/waltz_for_mia/
  meta.json     identity, author, difficulty, tags
  en.json       title and description in English
  de.json       … in German (one file per language)
  steps.json    what the lesson does, step by step
```

### meta.json

```json
{
  "id": "waltz_for_mia",
  "version": "1.0.0",
  "author": "Mia",
  "difficulty": "beginner",
  "tags": ["melody", "rhythm"],
  "locales": ["en", "de"],
  "estimated_minutes": 5,
  "based_on": "simple_waltz"
}
```

`id` must match the folder name (lowercase letters, digits and `_`). `difficulty` is `beginner`, `intermediate` or `advanced`. `based_on` is written by **Duplicate** and is optional.

### en.json / de.json

```json
{ "title": "Waltz for Mia", "description": "A gentle waltz in three-four time." }
```

### steps.json

A list of steps, played in order. Two types exist; a lesson should end with an exercise.

#### `scene`: explaining something

A scene is a series of **beats**: short screens with text, the keyboard, animated hands and a staff. Texts are written in every language right here.

```json
{
  "type": "scene",
  "title": {"en": "The waltz", "de": "Der Walzer"},
  "beats": [
    {
      "title": {"en": "ONE two three", "de": "EINS zwei drei"},
      "say": {"en": "A waltz counts three.", "de": "Ein Walzer zählt bis drei."},
      "play": ["E4", "G4", "G4", "C4+E4+G4"],
      "tempo": 100,
      "try": "play",
      "try_say": {"en": "Now you!", "de": "Jetzt du!"}
    }
  ]
}
```

| Field | Meaning |
|-------|---------|
| `title`, `say`, `try_say` | Texts: `{"en": …, "de": …}` |
| `play` | Notes Pianove plays, one after another. A chord is `"C4+E4+G4"` |
| `tempo` | Beats per minute for `play` (default 76) |
| `fingers` | A finger (1–5) for each note of `play`; `"1+3+5"` for a chord |
| `accent` | Stress every n-th note (`3` for a waltz) |
| `velocities` | Loudness (1–127) for each note of `play` |
| `try` | What the learner plays afterwards: `"play"` (the same notes) or a list of notes |
| `mark` | Keys to highlight |
| `labels` | Key names to show: a list of keys, or `"C"` (every C), `"white"`, `"hand"` (keys under the fingers) |
| `hand` | Where the hands rest: `{"right": {"C4": 1, "D4": 2}, "left": {…}}` |
| `numbers` | `true`: show finger numbers on the hands |
| `side` | `"right"` or `"left"`: the hand that plays (default: from `hand`) |
| `staff` | A staff: `{"clef": "treble"/"bass"/"grand", "key": 1, "time": [3, 4], "notes": […], "under": "names"/"count"}`. `key` counts sharps (positive) or flats (negative) |

**A screen's phrase.** The lesson editor writes a screen's music once, as `music` (the same form as an exercise below, with rhythm, both hands and fingers), and fills in what the player reads from it: `play`, plus

| Field | Meaning |
|-------|---------|
| `rhythm` | When each played event starts and how long it lasts, in beats: `[[0, 1], [1, 2]]`. Without it, one event per beat |
| `left` | The keys the left hand plays (a phrase for both hands) |
| `kind` | For the editor only: `explain`, `listen`, `find` or `hand` |

`music`, `kind`, `repeat` and `staff_own` are the editor's own; the player ignores them.

#### `exercise`: playing from sheet music

```json
{
  "type": "exercise",
  "time": [4, 4],
  "tempo": 96,
  "bars":  [["C4~", "C4", "E4", "D4", "C4", "G4"], ["C4+E4", "r"]],
  "types": [["quarter", "quarter", "triplet_eighth", "triplet_eighth", "triplet_eighth", "quarter"],
            ["half", "half"]],
  "lh": {"bars": [["C3"], ["G2"]], "types": [["whole"], ["whole"]]}
}
```

The learner plays the bars section by section, then all at once.

| Field | Meaning |
|-------|---------|
| `time` | Time signature, e.g. `[4, 4]`, `[3, 4]`, `[6, 8]` |
| `tempo` | Quarter notes per minute (default 80) |
| `clef` | `"treble"` (default) or `"bass"`, for an exercise with one staff |
| `bars` | Per bar: notes (`"C4"`), chords (`"C4+E4+G4"`) and rests (`"r"`). A note ending in `~` is tied to the same note in the next entry (`"C4~"`, or `"C4~+E4"` in a chord); `@` gives its finger (`"C4@1"`, `"C4@1+E4@3+G4@5"`, `"C4@1~"`) |
| `types` | Optional. The length of every entry: `whole`, `half`, `quarter`, `eighth`, `sixteenth`, `thirty_second`; `dotted_…` (1½ times as long) or `triplet_…` (two thirds: three triplet eighths take one quarter). Without it, a bar's entries share the bar evenly (how older lessons are written) |
| `lh` | Optional. The left hand, `{"bars", "types"}` like the right: the exercise is then shown on a grand staff (treble and bass) and played with both hands |

A bar whose entries don't fill it is silent for the rest. The lesson editor edits all of this as a score (click or tap a note, type A–G or play it, pick a value, drag a note to move it; see `pianove/score_editor.py`).

### Notes

A note is a letter, an optional `#` or `b`, and an octave: `C4` is middle C, `F#4`, `Bb3`. German *H* is written `B`.

---

## Course folder

```
courses/my_course/
  meta.json     {"id", "version", "author", "difficulty", "lessons": ["welcome", "waltz_for_mia"]}
  en.json       {"title", "description"}
  de.json
```

A course lists lessons by id, in order. They can be built-in or your own.

---

## Packages (`.pianove-pkg`)

A package is a zip file:

```
pianove-package.json        {"format": 1, "kind": "course", "id": "my_course"}
courses/my_course/…
lessons/waltz_for_mia/…     your own lessons the course uses (built-in ones are left out)
```

**Export** in the Create tab writes one to your Downloads folder; **Import package…** installs one into `~/.pianove/packages/`. Import also accepts a zip of a single lesson folder. Packages larger than 20 MB, or with files outside their folders, are refused.

---

## The editor's check

The editor lists problems as you work (they never stop you saving): unknown notes, a missing translation, a fingering that doesn't match the notes, a bar longer than its time signature allows, a lesson that doesn't end with an exercise. Every built-in lesson passes this check (`tests/test_creator_store.py`).
