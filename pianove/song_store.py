import os
import json
import shutil
import uuid
import xml.etree.ElementTree as ET

_STORE_DIR  = os.path.expanduser("~/.pianove/songs")
_FILES_DIR  = os.path.join(_STORE_DIR, "files")
_INDEX_FILE = os.path.join(_STORE_DIR, "index.json")

# Difficulty heuristic thresholds (avg notes/bar after range weighting)
_DIFF_EASY   = 3.5
_DIFF_MEDIUM = 6.0

# MusicXML type name → beat duration (in quarter-note units)
_TYPE_BEATS = {
    "whole": 4.0, "half": 2.0, "quarter": 1.0,
    "eighth": 0.5, "16th": 0.25,
    "dotted-whole": 6.0, "dotted-half": 3.0, "dotted-quarter": 1.5,
    "dotted-eighth": 0.75,
}

# MusicXML <type> text → pylute note-type vocabulary (see PyLute's durations.py).
_MXL_TYPE_TO_PYLUTE = {
    "breve": "whole", "whole": "whole", "half": "half", "quarter": "quarter",
    "eighth": "eighth", "16th": "sixteenth", "32nd": "thirty_second",
    "64th": "thirty_second", "128th": "thirty_second",    # drawn as 32nds; they sound as written
}
_QUARTERS_OF = {"whole": 4.0, "half": 2.0, "quarter": 1.0, "eighth": 0.5, "sixteenth": 0.25,
                "thirty_second": 0.125}

# Bumped whenever the importer reads more of a file: songs imported by an older version
# are read again from their file the next time they are opened
PARSER_VERSION = 2



def _ensure_dirs():
    os.makedirs(_FILES_DIR, exist_ok=True)


def _load_index() -> list[dict]:
    if not os.path.exists(_INDEX_FILE):
        return []
    try:
        with open(_INDEX_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _save_index(index: list[dict]):
    _ensure_dirs()
    with open(_INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2, ensure_ascii=False)



def _tag(el):
    import re
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


def _credit_meta(root):
    """Title and composer from <credit> blocks (MuseScore exports often store them only there)."""
    words = []
    for cr in root.iter():
        if _tag(cr) != "credit":
            continue
        ctype = next((c.text.strip().lower() for c in cr if _tag(c) == "credit-type" and c.text), "")
        for w in cr:
            if _tag(w) == "credit-words" and w.text and w.text.strip():
                try:
                    size = float(w.get("font-size", "0"))
                except ValueError:
                    size = 0.0
                words.append((ctype, size, w.get("justify", ""), w.text.strip()))
    title = next((txt for c, _, _, txt in words if c == "title"), "")
    composer = next((txt for c, _, _, txt in words if c == "composer"), "")
    if not title and words:
        title = max(words, key=lambda w: w[1])[3]
    if not composer:
        composer = next((txt for c, _, j, txt in words if j == "right" and txt != title), "")
    return title, composer


_FIFTHS_TO_KEY = {
    0: "C", 1: "G", 2: "D", 3: "A", 4: "E", 5: "B", 6: "F#", 7: "C#",
    -1: "F", -2: "Bb", -3: "Eb", -4: "Ab", -5: "Db", -6: "Gb", -7: "Cb",
}

_SEMITONES = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def _pitch_to_midi(pitch: str) -> int:
    name = pitch[0].upper()
    rest = pitch[1:]
    acc = 0
    if rest and rest[0] == "#":
        acc, rest = 1, rest[1:]
    elif rest and rest[0] == "b":
        acc, rest = -1, rest[1:]
    return (int(rest) + 1) * 12 + _SEMITONES[name] + acc


def _parse_musicxml(filepath: str) -> dict:
    import zipfile, re

    ext = os.path.splitext(filepath)[1].lower()
    if ext == ".mxl":
        with zipfile.ZipFile(filepath) as zf:
            xml_path = None
            if "META-INF/container.xml" in zf.namelist():
                container = ET.parse(zf.open("META-INF/container.xml")).getroot()
                for el in container.iter():
                    if _tag(el) == "rootfile":
                        xml_path = el.get("full-path")
                        break
            if xml_path is None:
                for name in sorted(zf.namelist()):
                    if name.endswith(".xml") and "META-INF" not in name:
                        xml_path = name
                        break
            root = ET.parse(zf.open(xml_path)).getroot()
    else:
        root = ET.parse(filepath).getroot()

    # Navigate to score-partwise
    if _tag(root) != "score-partwise":
        for el in root.iter():
            if _tag(el) == "score-partwise":
                root = el
                break

    # Metadata
    work_el  = _find(root, "work")
    id_el    = _find(root, "identification")
    _fallback_title = os.path.splitext(os.path.basename(filepath))[0]
    title    = (_text(work_el, "work-title") or _text(root, "movement-title") or _fallback_title)
    composer = ""
    if id_el is not None:
        for c in _findall(id_el, "creator"):
            if c.get("type", "").lower() == "composer" and c.text:
                composer = c.text.strip()
                break
    credit_title, credit_composer = _credit_meta(root)
    if title == "Untitled" and credit_title:
        title = credit_title
    composer = composer or credit_composer

    # First part only
    parts    = [el for el in root.iter() if _tag(el) == "part"]
    part     = parts[0]
    measures = _findall(part, "measure")

    # Attributes from first measure
    first_attrs = _find(measures[0], "attributes")
    key  = "C"
    time = (4, 4)
    n_staves = 1
    if first_attrs is not None:
        key_el = _find(first_attrs, "key")
        if key_el is not None:
            try:
                fifths = int(_text(key_el, "fifths", "0"))
                key = _FIFTHS_TO_KEY.get(fifths, "C")
            except (ValueError, TypeError):
                pass
        time_el = _find(first_attrs, "time")
        if time_el is not None:
            try:
                time = (int(_text(time_el, "beats", "4")),
                        int(_text(time_el, "beat-type", "4")))
            except (ValueError, TypeError):
                pass
        staves_el = _find(first_attrs, "staves")
        if staves_el is not None:
            try:
                n_staves = int(staves_el.text)
            except (ValueError, TypeError):
                pass

    # Every note of every voice on both staves, as it sounds: where it starts in its bar,
    # how long it really lasts (tuplets included), whether it only continues a tie, and
    # how loud it is. Tempo changes become a tempo map. Two-note and single-note
    # tremolos are written out as the notes they sound as.
    S = {0: "rh", 1: "lh"}
    data = {k: [] for k in ("bars", "types", "onsets", "durs", "ties", "vels")}
    out = {f"{k}_{h}": [] for k in data for h in S.values()}
    bar_lens: list[float] = []             # real length of each bar in quarters (pickups are short)
    tempos: list[list[float]] = []         # [position in quarters from the start, quarter bpm]
    divisions = 1
    bpm = None
    full_bar = time[0] * 4 / time[1]
    bar_start_q = 0.0
    velocity = 80                          # MusicXML's default forte is 90; mf ≈ 80
    open_ties: dict = {}                   # (staff, voice, pitch) → (bar list, index) of the first note
    trem_start = None                      # the first note of a two-note tremolo

    def _tempo_of(el):
        """A tempo from a <direction>/<sound>, in quarter notes per minute."""
        for sub in el.iter():
            if _tag(sub) == "sound" and sub.get("tempo"):
                try:
                    return float(sub.get("tempo"))
                except ValueError:
                    pass
        for sub in el.iter():
            if _tag(sub) == "metronome":
                unit = _text(sub, "beat-unit", "quarter")
                try:
                    per = float(_text(sub, "per-minute", "") or 0)
                except ValueError:
                    per = 0
                if per:
                    q = {"whole": 4, "half": 2, "quarter": 1, "eighth": 0.5, "16th": 0.25}.get(unit, 1)
                    if _find(sub, "beat-unit-dot") is not None:
                        q *= 1.5
                    return per * q
        return None

    def _dynamics_of(el):
        for sub in el.iter():
            if _tag(sub) == "sound" and sub.get("dynamics"):
                try:
                    return max(20, min(127, round(90 * float(sub.get("dynamics")) / 100)))
                except ValueError:
                    pass
        return None

    for measure in measures:
        bar = {h: {k: [] for k in data} for h in S.values()}
        cursor = longest = last_onset = 0

        def add(staff_idx, pitch, ntype, on_div, dur_div, tied=False, vel=None):
            b = bar[S.get(staff_idx, "lh")]
            b["bars"].append(pitch)
            b["types"].append(ntype)
            b["onsets"].append(round(on_div / divisions, 6))
            b["durs"].append(round(dur_div / divisions, 6))
            b["ties"].append(bool(tied))
            b["vels"].append(vel or velocity)
            return b, len(b["bars"]) - 1

        # Walk the measure in document order with a time cursor, as MusicXML defines it
        for el in measure:
            tag = _tag(el)
            if tag == "attributes":
                try:
                    divisions = int(_text(el, "divisions", str(divisions)))
                except (ValueError, TypeError):
                    pass
                continue
            if tag in ("backup", "forward"):
                try:
                    d = int(_text(el, "duration", "0") or 0)
                except (ValueError, TypeError):
                    d = 0
                cursor += d if tag == "forward" else -d
                longest = max(longest, cursor)
                continue
            if tag in ("direction", "sound"):
                tempo = _tempo_of(el)
                if tempo:
                    if bpm is None:
                        bpm = tempo
                    tempos.append([round(bar_start_q + cursor / divisions, 6), tempo])
                dyn = _dynamics_of(el)
                if dyn:
                    velocity = dyn
                continue
            if tag != "note":
                continue

            note_el = el
            is_grace = _find(note_el, "grace") is not None
            is_chord = _find(note_el, "chord") is not None
            try:
                dur = int(_text(note_el, "duration", "0") or 0)
            except (ValueError, TypeError):
                dur = 0
            onset = last_onset if is_chord else cursor
            if not is_grace and not is_chord:
                last_onset = cursor
                cursor += dur
                longest = max(longest, cursor)

            if is_grace or _find(note_el, "cue") is not None:
                continue                   # ornaments without time of their own
            if _find(note_el, "rest") is not None:
                continue
            pitch_el = _find(note_el, "pitch")
            if pitch_el is None:
                continue

            ntype_el = _find(note_el, "type")
            ntype = _MXL_TYPE_TO_PYLUTE.get(ntype_el.text if ntype_el is not None else "", "")
            if not ntype:                  # no written value: the closest one to its length
                q = dur / max(1, divisions)
                ntype = min(_QUARTERS_OF, key=lambda k: abs(_QUARTERS_OF[k] - q))
            if _findall(note_el, "dot") and ntype != "whole":
                ntype = f"dotted_{ntype}"

            staff_idx = 0
            try:
                staff_idx = int(_text(note_el, "staff", "1")) - 1
            except (ValueError, TypeError):
                pass
            voice = _text(note_el, "voice", "1")

            step   = _text(pitch_el, "step", "C")
            octave = _text(pitch_el, "octave", "4")
            try:
                alter = float(_text(pitch_el, "alter", "0"))
            except (ValueError, TypeError):
                alter = 0.0
            pitch = _spell(step, round(alter), octave)
            vel = None
            if note_el.get("dynamics"):
                try:
                    vel = max(20, min(127, round(90 * float(note_el.get("dynamics")) / 100)))
                except ValueError:
                    pass

            # tremolos: written as what they sound as
            trem = next((n for n in note_el.iter() if _tag(n) == "tremolo"), None)
            if trem is not None:
                try:
                    beams = int((trem.text or "3").strip())
                except ValueError:
                    beams = 3
                step_div = max(1, divisions // (2 ** max(1, beams)))
                kind = trem.get("type", "single")
                if kind == "start":
                    trem_start = (staff_idx, pitch, onset, dur, vel)
                    continue
                if kind == "stop" and trem_start is not None:
                    s_idx, p0, on0, d0, v0 = trem_start
                    trem_start = None
                    small = "thirty_second" if beams >= 3 else "sixteenth" if beams == 2 else "eighth"
                    for k in range(max(2, (d0 + dur) // step_div)):
                        add(s_idx, p0 if k % 2 == 0 else pitch, small, on0 + k * step_div, step_div, vel=v0)
                    continue
                if kind == "single":
                    small = "thirty_second" if beams >= 3 else "sixteenth" if beams == 2 else "eighth"
                    for k in range(max(1, dur // step_div)):
                        add(staff_idx, pitch, small, onset + k * step_div, step_div, vel=vel)
                    continue

            # ties: a note that only continues a tied one is drawn, but not struck again;
            # its length is added to the note it continues
            tie_types = {t.get("type") for t in note_el if _tag(t) == "tie"}
            key_ = (staff_idx, voice, pitch)
            if "stop" in tie_types and key_ in open_ties:
                b0, i0 = open_ties[key_]
                b0["durs"][i0] = round(b0["durs"][i0] + dur / divisions, 6)
                add(staff_idx, pitch, ntype, onset, dur, tied=True, vel=vel)
                if "start" not in tie_types:
                    del open_ties[key_]
                continue
            b, i = add(staff_idx, pitch, ntype, onset, dur, vel=vel)
            if "start" in tie_types:
                open_ties[key_] = (b, i)

        for h in S.values():
            for k in data:
                out[f"{k}_{h}"].append(bar[h][k])
        blen = round(longest / divisions, 6) if longest else full_bar
        bar_lens.append(blen)
        bar_start_q += blen

    return {
        "title":     title,
        "composer":  composer,
        "key":       key,
        "time":      list(time),
        **out,
        "bar_lens":  bar_lens,
        "bpm":       bpm,
        "tempos":    tempos,
        "parser":    PARSER_VERSION,
    }


_STEP_SEMI = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
_SHARP_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def _spell(step: str, alter: int, octave) -> str:
    """A pitch name the rest of Pianove reads. A single sharp or flat is kept as written;
    a double sharp or flat (F## is G) is spelled as the key it sounds as."""
    if alter in (-1, 0, 1):
        return f"{step}{'#' if alter == 1 else 'b' if alter == -1 else ''}{octave}"
    midi = 12 * (int(octave) + 1) + _STEP_SEMI.get(step, 0) + alter
    return f"{_SHARP_NAMES[midi % 12]}{midi // 12 - 1}"


def _bar_pitches(bar) -> list[str]:
    """The pitches of a bar, whichever way it was saved: plain pitch strings (with the
    rhythm kept alongside), [pitch, type] pairs, or groups of such pairs (a chord)."""
    out = []
    for item in bar:
        if isinstance(item, str):
            out.append(item)
        elif item and isinstance(item[0], str):
            out.append(item[0])
        else:
            out.extend(pair[0] for pair in item)
    return out


def _compute_difficulty(bars_rh: list[list[str]], bars_lh: list[list[str]]) -> str:
    all_notes = [p for bar in bars_rh + bars_lh for p in _bar_pitches(bar)]
    if not all_notes:
        return "beginner"
    avg_per_bar = len(all_notes) / max(1, len(bars_rh))
    midis = [_pitch_to_midi(p) for p in all_notes]
    pitch_range = (max(midis) - min(midis)) / 12.0
    score = avg_per_bar * (1 + pitch_range * 0.15)
    if score < _DIFF_EASY:
        return "beginner"
    elif score < _DIFF_MEDIUM:
        return "intermediate"
    return "advanced"



def list_songs() -> list[dict]:
    return _load_index()


_MUSIC_KEYS = tuple(f"{k}_{h}" for k in ("bars", "types", "onsets", "durs", "ties", "vels")
                    for h in ("rh", "lh")) + ("bar_lens", "bpm", "tempos", "parser")


def _music_of(parsed: dict) -> dict:
    return {k: parsed.get(k) for k in _MUSIC_KEYS}


def import_song(filepath: str) -> dict:
    _ensure_dirs()
    parsed = _parse_musicxml(filepath)

    song_id  = str(uuid.uuid4())[:8]
    dest_ext = os.path.splitext(filepath)[1].lower() or ".xml"
    dest     = os.path.join(_FILES_DIR, f"{song_id}{dest_ext}")
    shutil.copy2(filepath, dest)

    difficulty = _compute_difficulty(parsed["bars_rh"], parsed["bars_lh"])
    n_bars     = len(parsed["bars_rh"])

    entry = {
        "id":         song_id,
        "title":      parsed["title"],
        "composer":   parsed["composer"],
        "key":        parsed["key"],
        "time":       parsed["time"],
        "difficulty": difficulty,
        "n_bars":     n_bars,
        "filepath":   dest,
        **_music_of(parsed),
    }

    index = _load_index()
    index.append(entry)
    _save_index(index)
    return entry


def delete_song(song_id: str):
    index = _load_index()
    entry = next((s for s in index if s["id"] == song_id), None)
    if entry and os.path.exists(entry.get("filepath", "")):
        try:
            os.remove(entry["filepath"])
        except OSError:
            pass
    _save_index([s for s in index if s["id"] != song_id])


_QUARTERS = {"whole": 4.0, "half": 2.0, "quarter": 1.0, "eighth": 0.5, "sixteenth": 0.25}


def _flatten_bars(bars):
    """Bars saved as [pitch, type] pairs or as groups of them (a chord) → plain pitches,
    their note types, and where each starts in its bar (quarter notes): the form the
    lesson page reads. Plain pitch bars come back as they are, without rhythm."""
    if all(isinstance(item, str) for bar in bars for item in bar):
        return bars, None, None
    pitches, types, onsets = [], [], []
    for bar in bars:
        bp, bt, bo, pos = [], [], [], 0.0
        for item in bar:
            group = ([(item, "quarter")] if isinstance(item, str)
                     else [tuple(item)] if item and isinstance(item[0], str)
                     else [tuple(pair) for pair in item])
            for p, t in group:
                bp.append(p)
                bt.append(t)
                bo.append(round(pos, 4))
            t0 = group[0][1]
            base = t0.replace("dotted_", "")
            pos += _QUARTERS.get(base, 1.0) * (1.5 if t0.startswith("dotted_") else 1.0)
        pitches.append(bp)
        types.append(bt)
        onsets.append(bo)
    return pitches, types, onsets


def _get_song_raw(song_id: str) -> dict | None:
    return next((s for s in _load_index() if s["id"] == song_id), None)


def _reimport(song: dict) -> dict:
    """Read an older import again from its file, so it gains everything the importer now
    understands (all voices, tuplets, short notes, ties, tempo changes, dynamics)."""
    try:
        parsed = _parse_musicxml(song["filepath"])
    except Exception as e:                      # keep the old import rather than nothing
        print(f"Re-import of {song.get('title')} failed: {e}")
        return song
    new = {**song, **_music_of(parsed),
           "n_bars": len(parsed["bars_rh"]),
           "difficulty": _compute_difficulty(parsed["bars_rh"], parsed["bars_lh"])}
    index = _load_index()
    for i, s in enumerate(index):
        if s["id"] == song["id"]:
            index[i] = new
    _save_index(index)
    return new


def get_song(song_id: str) -> dict | None:
    """A song from the library. Songs saved with chords as groups of [pitch, type]
    pairs read the same as the rest: plain pitches, with their types and positions."""
    song = _get_song_raw(song_id)
    if song is None:
        return None
    if song.get("parser", 1) < PARSER_VERSION and os.path.exists(song.get("filepath", "")):
        song = _reimport(song)
    out = dict(song)
    for hand in ("rh", "lh"):
        bars, types, onsets = _flatten_bars(song.get(f"bars_{hand}", []))
        out[f"bars_{hand}"] = bars
        if types is not None and not song.get(f"types_{hand}"):
            out[f"types_{hand}"], out[f"onsets_{hand}"] = types, onsets
    return out


def get_song_bars_split(song_id: str) -> tuple[list[list[str]], list[list[str]]]:
    song = get_song(song_id)
    if song is None:
        return [], []
    return song.get("bars_rh", []), song.get("bars_lh", [])


def get_song_types_split(song_id: str) -> tuple[list[list[str]] | None, list[list[str]] | None]:
    """Per-bar note types for each hand, or (None, None) for songs imported before
    rhythms were stored."""
    song = get_song(song_id)
    if song is None:
        return None, None
    return song.get("types_rh"), song.get("types_lh")


def get_song_rhythm(song_id: str) -> dict:
    """Note values, positions, bar lengths and tempo of an imported song. Keys are
    missing (None) for songs imported before rhythms were stored."""
    song = get_song(song_id) or {}
    return {k: song.get(k) for k in ("types_rh", "types_lh", "onsets_rh", "onsets_lh", "durs_rh", "durs_lh",
                                     "ties_rh", "ties_lh", "vels_rh", "vels_lh", "bar_lens", "bpm", "tempos")}


def get_song_bars(song_id: str, hand: str = "right") -> list[list[str]]:
    song = get_song(song_id)
    if song is None:
        return [["C4", "D4", "E4", "F4"]]

    bars_rh = song.get("bars_rh", [])
    bars_lh = song.get("bars_lh", [])

    if hand == "left":
        return bars_lh  # preserve bar alignment; empty bars = whole rests

    if hand == "both":
        combined = []
        for i in range(len(bars_rh)):
            rh = bars_rh[i] if i < len(bars_rh) else []
            lh = bars_lh[i] if i < len(bars_lh) else []
            merged = rh + lh
            combined.append(merged)
        return combined if combined else bars_rh

    # default: right hand — preserve bar alignment
    return bars_rh
