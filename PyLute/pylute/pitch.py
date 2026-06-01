DIATONIC = {"C": 0, "D": 1, "E": 2, "F": 3, "G": 4, "A": 5, "B": 6}

# Absolute diatonic step of the bottom staff line per clef
CLEF_BOTTOM_LINE = {
    "treble": 4 * 7 + DIATONIC["E"],  # E4
    "bass":   2 * 7 + DIATONIC["G"],  # G2
}

def parse_pitch(pitch_str):
    """"G4" / "F#4" / "Bb3" -> (name, accidental, octave)"""
    name = pitch_str[0].upper()
    rest = pitch_str[1:]
    accidental = ""
    if rest and rest[0] in "#b":
        accidental = rest[0]
        rest = rest[1:]
    return name, accidental, int(rest)

def pitch_to_step(pitch_str, clef="treble"):
    """Step from the bottom staff line (0 = bottom line, 1 = first space, 2 = second line ...)."""
    name, _, octave = parse_pitch(pitch_str)
    return octave * 7 + DIATONIC[name] - CLEF_BOTTOM_LINE[clef]
