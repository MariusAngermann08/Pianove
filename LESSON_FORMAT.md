# Pianove Lesson & Course Format

Pianove uses a folder-based bundle format for lessons and courses. The format is designed to be human-readable, diff-friendly, and Git-friendly so that the community can study, share, and improve content freely.

---

## Directory Layout

```
pianove/lessons/          ← built-in lessons, read-only, versioned with the app
~/.pianove/packages/      ← user-installed packages (lessons & courses)
```

A `.pianove-pkg` file is a renamed `.zip` of a lesson or course folder. It can be imported via the in-app package manager or the file picker.

---

## Lesson Bundle

Each lesson lives in its own folder:

```
lessons/welcome/
  meta.json          ← identity, authorship, difficulty, tags
  en.json            ← localized strings (title, descriptions, hints)
  de.json            ← additional locale files follow the same pattern
  steps.json         ← ordered list of step blocks
  assets/
    notation_1.xml   ← MusicXML snippets rendered by PyLute
    audio_1.ogg      ← optional backing audio
```

### meta.json

```json
{
  "id": "welcome",
  "version": "1.0.0",
  "author": "Pianove",
  "difficulty": "beginner",
  "tags": ["intro", "basics"],
  "locales": ["en", "de"],
  "estimated_minutes": 5
}
```

### steps.json

A step is a typed block. The renderer dispatches on `type`:

```json
[
  {
    "type": "text",
    "content_key": "step1_text"
  },
  {
    "type": "notation",
    "file": "assets/notation_1.xml",
    "caption_key": "step1_caption"
  },
  {
    "type": "exercise",
    "notes": ["C4", "E4", "G4"],
    "caption_key": "step1_exercise"
  },
  {
    "type": "quiz",
    "question_key": "step1_question",
    "options_keys": ["opt_a", "opt_b", "opt_c"],
    "correct": 0
  }
]
```

`content_key`, `caption_key`, etc. are looked up in the locale file for the active language, falling back to `en.json`.

### Step types

| Type | Description |
|------|-------------|
| `text` | Explanatory prose, supports inline bold/italic via simple markup |
| `notation` | Sheet music rendered by PyLute from a MusicXML asset file |
| `exercise` | Interactive play-along — user must play specified notes on MIDI keyboard |
| `quiz` | Multiple-choice question with immediate feedback |

---

## Course Bundle

A course is an ordered collection of lessons:

```
courses/beginner_path/
  meta.json          ← course identity and lesson order
  en.json
  de.json
```

### meta.json

```json
{
  "id": "beginner_path",
  "version": "1.0.0",
  "author": "Pianove",
  "difficulty": "beginner",
  "lessons": [
    "welcome",
    "c_major_scale",
    "reading_notes",
    "first_melody"
  ]
}
```

Lessons referenced here can be bundled inside the course zip or declared as dependencies resolved from already-installed packages.

---

## Package Manager

- Import source: local file picker (`.pianove-pkg` zip) — v1
- Future: registry index at a hosted `index.json` (GitHub releases or static hosting)
- No server required for the registry — a community-maintained `index.json` in a public repo is sufficient

### Package resolution order

1. Built-in (`pianove/lessons/`, `pianove/courses/`)
2. User-installed (`~/.pianove/packages/`)
3. User-installed packages shadow built-ins of the same `id` — allows community patches

---

## Design Principles

- **Human-readable**: JSON + MusicXML are plain text — readable, diffable, Git-friendly
- **Localizable**: Every user-facing string lives in locale files, following the same pattern as the rest of the app
- **Forkable**: Anyone can copy a lesson folder, edit it, and share the zip or submit a PR
- **Extensible**: New step types can be added without breaking existing lessons — unknown types are skipped with a fallback UI
