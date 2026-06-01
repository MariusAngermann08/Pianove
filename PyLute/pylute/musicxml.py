"""
MusicXML importer for OpenScore.

Simplifications applied automatically:
  - Only the first <part> is imported (covers piano grand staff)
  - Chords: first note at each position kept, remaining chord members dropped
  - Multiple voices: voice 1 only
  - Grace notes: skipped
  - Tuplets (time-modification): skipped
  - Unsupported note types (32nd, 64th, 128th, ...): skipped
  - Ties, slurs, dynamics, articulations, lyrics: ignored
  - Time signature changes after the first measure: ignored
"""

import re
import xml.etree.ElementTree as ET

# MusicXML type name → OpenScore type name
_TYPE_MAP = {
    "whole":    "whole",
    "half":     "half",
    "quarter":  "quarter",
    "eighth":   "eighth",
    "16th":     "sixteenth",
}

_FIFTHS_TO_KEY = {
     0: "C",   1: "G",   2: "D",   3: "A",   4: "E",   5: "B",   6: "F#",  7: "C#",
    -1: "F",  -2: "Bb", -3: "Eb", -4: "Ab", -5: "Db", -6: "Gb", -7: "Cb",
}


# ----------------------------------------------------------------- xml helpers

def _tag(el):
    return re.sub(r'\{[^}]+\}', '', el.tag)


def _find(el, tag):
    if el is None:
        return None
    for child in el:
        if _tag(child) == tag:
            return child
    return None


def _findall(el, tag):
    if el is None:
        return []
    return [c for c in el if _tag(c) == tag]


def _text(el, tag, default=None):
    child = _find(el, tag)
    return child.text.strip() if (child is not None and child.text) else default


# ----------------------------------------------------------------- converters

def _note_type(note_el):
    """Return pylute duration string or None if unsupported."""
    from .durations import VALUES
    # Whole-measure rest: <rest measure="yes"/> typically has no <type> element
    rest_el = _find(note_el, "rest")
    if rest_el is not None and rest_el.get("measure") == "yes":
        return "whole"
    base = _TYPE_MAP.get(_text(note_el, "type", ""))
    if base is None:
        return None
    if _find(note_el, "dot") is not None:
        dotted = f"dotted_{base}"
        if dotted in VALUES:
            return dotted
    return base


def _pitch_str(note_el):
    """Return pitch string like 'F#4', or None on failure."""
    p = _find(note_el, "pitch")
    if p is None:
        return None
    step   = _text(p, "step",   "C")
    octave = _text(p, "octave", "4")
    try:
        alter = float(_text(p, "alter", "0"))
    except (ValueError, TypeError):
        alter = 0.0
    acc = "#" if alter >= 0.5 else ("b" if alter <= -0.5 else "")
    return f"{step}{acc}{octave}"


def _parse_attributes(attrs_el):
    """Extract (key, time, n_staves, clef_types) from an <attributes> element."""
    key        = "C"
    time       = (4, 4)
    n_staves   = 1
    clef_types = []

    if attrs_el is None:
        return key, time, n_staves, ["treble"]

    # Key
    key_el = _find(attrs_el, "key")
    if key_el is not None:
        try:
            fifths = int(_text(key_el, "fifths", "0"))
            key = _FIFTHS_TO_KEY.get(fifths, "C")
        except (ValueError, TypeError):
            pass

    # Time
    time_el = _find(attrs_el, "time")
    if time_el is not None:
        try:
            beats     = int(_text(time_el, "beats",     "4"))
            beat_type = int(_text(time_el, "beat-type", "4"))
            time = (beats, beat_type)
        except (ValueError, TypeError):
            pass

    # Staff count
    staves_el = _find(attrs_el, "staves")
    if staves_el is not None:
        try:
            n_staves = int(staves_el.text)
        except (ValueError, TypeError):
            pass

    # Clefs (sorted by staff number)
    clef_els = sorted(_findall(attrs_el, "clef"),
                      key=lambda c: int(c.get("number", "1")))
    for ce in clef_els:
        sign = _text(ce, "sign", "G")
        clef_types.append("bass" if sign == "F" else "treble")

    while len(clef_types) < n_staves:
        clef_types.append("bass" if len(clef_types) >= 1 else "treble")

    return key, time, n_staves, clef_types


# ----------------------------------------------------------------- public API

def load_musicxml(filepath, surface=None, length=1100, bars_per_system=None):
    """
    Load a MusicXML (.xml, .musicxml, .mxl) file and return a Score.

    Parameters
    ----------
    filepath : str
        Path to the MusicXML file.
    surface : pygame.Surface or None
        Passed to Score for rendering; can be set later via score.surface.
    length : int
        Staff length in pixels (default 1100).

    Returns
    -------
    Score
    """
    from .score import Score
    from .note  import Note
    from .rest  import Rest
    from .durations import get_value

    root = _parse_root(filepath)
    tag  = _tag(root)

    if tag == "score-timewise":
        raise ValueError("score-timewise MusicXML is not supported; "
                         "convert to score-partwise first.")
    if tag not in ("score-partwise", "score-partwise"):
        # some files wrap in a higher element — search for score-partwise
        sp = None
        for el in root.iter():
            if _tag(el) == "score-partwise":
                sp = el
                break
        if sp is None:
            raise ValueError("Could not locate <score-partwise> in the file.")
        root = sp

    # Metadata
    def _creator(id_el, role):
        for c in _findall(id_el, "creator") if id_el is not None else []:
            if c.get("type", "").lower() == role and c.text:
                return c.text.strip()
        return ""

    work_el    = _find(root, "work")
    id_el      = _find(root, "identification")
    title      = (_text(work_el, "work-title") or
                  _text(root,    "movement-title") or "")
    subtitle   = _text(work_el, "work-number") or ""
    composer   = _creator(id_el, "composer")
    lyricist   = _creator(id_el, "lyricist")
    rights     = _text(id_el,   "rights") or "" if id_el is not None else ""

    # Find first <part>
    parts = [el for el in root.iter() if _tag(el) == "part"]
    if not parts:
        raise ValueError("No <part> elements found.")
    part     = parts[0]
    measures = _findall(part, "measure")
    if not measures:
        raise ValueError("No <measure> elements found.")

    # Initial attributes from first measure
    first_attrs                      = _find(measures[0], "attributes")
    key, time, n_staves, clef_types  = _parse_attributes(first_attrs)

    # Scan all notes to catch staff numbers not declared in <staves>
    for m in measures:
        for n in _findall(m, "note"):
            try:
                s = int(_text(n, "staff", "1"))
                if s > n_staves:
                    n_staves = s
                    while len(clef_types) < n_staves:
                        clef_types.append("bass")
            except (ValueError, TypeError):
                pass

    score = Score(
        surface         = surface,
        staffs          = n_staves,
        length          = length,
        bars            = len(measures),
        clef_types      = clef_types,
        key             = key,
        time            = time,
        bars_per_system = bars_per_system,
    )
    score.title     = title
    score.subtitle  = subtitle
    score.composer  = composer
    score.lyricist  = lyricist
    score.copyright = rights

    bar_capacity = time[0] / time[1]
    stats = dict(chords=0, voices=0, grace=0, types=0, overflow=0)

    # First voice seen per staff — MusicXML voices are part-global so the bass
    # staff often uses voice "2", "3", or "5" rather than "1".
    primary_voice: dict[int, str] = {}

    for m_idx, measure in enumerate(measures):
        used = [0.0] * n_staves   # beats consumed per staff this measure

        for note_el in _findall(measure, "note"):

            # Grace notes
            if _find(note_el, "grace") is not None:
                stats["grace"] += 1
                continue

            # Chord member — keep only the first note at each beat position
            if _find(note_el, "chord") is not None:
                stats["chords"] += 1
                continue

            # Tuplet (time-modification present)
            if _find(note_el, "time-modification") is not None:
                stats["types"] += 1
                continue

            # Duration type
            ntype = _note_type(note_el)
            if ntype is None:
                stats["types"] += 1
                continue

            needed    = get_value(ntype)
            staff_idx = min(int(_text(note_el, "staff", "1")) - 1, n_staves - 1)

            # Voice filter: keep only the first voice encountered per staff.
            # This handles both part-global numbering (voices 1/2/3/4) and
            # per-staff numbering (both staves use voice "1").
            voice = _text(note_el, "voice", "1")
            if staff_idx not in primary_voice:
                primary_voice[staff_idx] = voice
            elif voice != primary_voice[staff_idx]:
                stats["voices"] += 1
                continue

            # Bar capacity guard (simplification may leave partial measures)
            if used[staff_idx] + needed > bar_capacity + 1e-6:
                stats["overflow"] += 1
                continue

            is_rest = _find(note_el, "rest") is not None
            bar     = score.staffs[staff_idx].bars[m_idx]
            staff   = score.staffs[staff_idx]

            if is_rest:
                bar.events.append(Rest(rtype=ntype, staff=staff))
            else:
                pitch = _pitch_str(note_el)
                if pitch is None:
                    continue
                bar.events.append(Note(ntype=ntype, pitch=pitch, staff=staff))

            used[staff_idx] += needed

    _report(stats)
    return score


def _parse_root(filepath):
    """Parse XML root, handling both plain .xml and compressed .mxl."""
    import os, zipfile
    ext = os.path.splitext(filepath)[1].lower()

    if ext == ".mxl":
        with zipfile.ZipFile(filepath) as zf:
            # Find the rootfile via META-INF/container.xml
            xml_path = None
            if "META-INF/container.xml" in zf.namelist():
                container = ET.parse(zf.open("META-INF/container.xml")).getroot()
                for el in container.iter():
                    if _tag(el) == "rootfile":
                        xml_path = el.get("full-path")
                        break
            if xml_path is None:
                # Fall back: first .xml that isn't in META-INF
                for name in sorted(zf.namelist()):
                    if name.endswith(".xml") and "META-INF" not in name:
                        xml_path = name
                        break
            if xml_path is None:
                raise ValueError("Could not locate XML content inside .mxl archive.")
            return ET.parse(zf.open(xml_path)).getroot()

    return ET.parse(filepath).getroot()


def _report(stats):
    total = sum(stats.values())
    if not total:
        return
    print("[OpenScore] MusicXML import — simplifications applied:")
    labels = [
        ("chords",   "chord notes removed (kept first note per chord)"),
        ("voices",   "notes from non-primary voices removed"),
        ("grace",    "grace notes skipped"),
        ("types",    "unsupported/tuplet notes skipped"),
        ("overflow", "notes skipped (bar over-capacity after simplification)"),
    ]
    for key, desc in labels:
        if stats[key]:
            print(f"  {stats[key]:4d}  {desc}")
