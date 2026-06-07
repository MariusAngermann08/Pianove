"""Programmatic note generation for sight-reading practice sessions."""
import random

_SCALES: dict[str, list[str]] = {
    "C":  ["C", "D", "E", "F", "G", "A", "B"],
    "G":  ["C", "D", "E", "F#", "G", "A", "B"],
    "D":  ["C#", "D", "E", "F#", "G", "A", "B"],
    "F":  ["C", "D", "E", "F", "G", "A", "Bb"],
}

# Octave ranges per clef × difficulty
_OCTAVES: dict[str, dict[str, list[int]]] = {
    "treble": {
        "beginner":     [4],
        "intermediate": [3, 4, 5],
        "advanced":     [3, 4, 5, 6],
    },
    "bass": {
        "beginner":     [3],
        "intermediate": [2, 3, 4],
        "advanced":     [2, 3, 4, 5],
    },
}

# For beginner we restrict to the first 5 scale degrees (C D E F G hand position)
_BEGINNER_DEGREES = 5


def build_pool(clef: str, difficulty: str, key: str) -> list[str]:
    """Return the list of pitch strings available for the given config."""
    scale = _SCALES.get(key, _SCALES["C"])
    degrees = scale[:_BEGINNER_DEGREES] if difficulty == "beginner" else scale
    octaves = _OCTAVES.get(clef, _OCTAVES["treble"]).get(difficulty, [4])
    return [f"{note}{oct}" for oct in octaves for note in degrees]


def generate_bars(clef: str, difficulty: str, key: str, n_notes: int) -> list[list[str]]:
    """
    Generate random bars of quarter notes for a sight-reading session.
    Returns a list of bars; each bar contains 4 pitch strings.
    """
    pool = build_pool(clef, difficulty, key)
    # Round up to a full bar
    n = ((n_notes + 3) // 4) * 4
    notes: list[str] = []
    prev: str | None = None
    for _ in range(n):
        # Avoid immediate repetition for harder difficulties
        if difficulty != "beginner" and len(pool) > 1 and prev is not None:
            choices = [p for p in pool if p != prev]
        else:
            choices = pool
        note = random.choice(choices)
        notes.append(note)
        prev = note
    return [notes[i:i + 4] for i in range(0, n, 4)]
