import re
import xml.etree.ElementTree as ET

_TYPE_MAP = {
    "whole":   "whole",
    "half":    "half",
    "quarter": "quarter",
    "eighth":  "eighth",
    "16th":    "sixteenth",
    "32nd":    "thirty_second",
}

_FIFTHS_TO_KEY = {
     0: "C",   1: "G",   2: "D",   3: "A",   4: "E",   5: "B",   6: "F#",  7: "C#",
    -1: "F",  -2: "Bb", -3: "Eb", -4: "Ab", -5: "Db", -6: "Gb", -7: "Cb",
}


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


def _is_full_measure_rest(note_el):
    rest_el = _find(note_el, "rest")
    if rest_el is None:
        return False
    return rest_el.get("measure") == "yes" or _text(note_el, "type") is None


def _note_type(note_el):
    from .durations import VALUES
    if _is_full_measure_rest(note_el):
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
    key        = "C"
    time       = (4, 4)
    n_staves   = 1
    clef_types = []

    if attrs_el is None:
        return key, time, n_staves, ["treble"]

    key_el = _find(attrs_el, "key")
    if key_el is not None:
        try:
            fifths = int(_text(key_el, "fifths", "0"))
            key = _FIFTHS_TO_KEY.get(fifths, "C")
        except (ValueError, TypeError):
            pass

    time_el = _find(attrs_el, "time")
    if time_el is not None:
        try:
            beats     = int(_text(time_el, "beats",     "4"))
            beat_type = int(_text(time_el, "beat-type", "4"))
            time = (beats, beat_type)
        except (ValueError, TypeError):
            pass

    staves_el = _find(attrs_el, "staves")
    if staves_el is not None:
        try:
            n_staves = int(staves_el.text)
        except (ValueError, TypeError):
            pass

    clef_els = sorted(_findall(attrs_el, "clef"),
                      key=lambda c: int(c.get("number", "1")))
    for ce in clef_els:
        sign = _text(ce, "sign", "G")
        clef_types.append("bass" if sign == "F" else "treble")

    while len(clef_types) < n_staves:
        clef_types.append("bass" if len(clef_types) >= 1 else "treble")

    return key, time, n_staves, clef_types


def _choose_part(parts):
    # pick the part with the most actual pitched notes in the first 5 measures —
    # some exports put an empty ornament/cue part first (e.g. MuseScore arrangements)
    best, best_count = parts[0], -1
    for part in parts:
        measures = _findall(part, "measure")
        count = sum(
            1 for m in measures[:5]
            for n in _findall(m, "note")
            if _find(n, "rest") is None
        )
        if count > best_count:
            best_count = count
            best = part
    return best


def load_musicxml(filepath, surface=None, length=1100, bars_per_system=None):
    from .score import Score
    from .note  import Note
    from .rest  import Rest
    from .chord import Chord
    from .pitch import pitch_to_step
    from .durations import get_value

    root = _parse_root(filepath)
    tag  = _tag(root)

    if tag == "score-timewise":
        raise ValueError("score-timewise MusicXML is not supported; convert to score-partwise first.")
    if tag != "score-partwise":
        sp = None
        for el in root.iter():
            if _tag(el) == "score-partwise":
                sp = el
                break
        if sp is None:
            raise ValueError("Could not locate <score-partwise> in the file.")
        root = sp

    def _creator(id_el, role):
        for c in _findall(id_el, "creator") if id_el is not None else []:
            if c.get("type", "").lower() == role and c.text:
                return c.text.strip()
        return ""

    work_el  = _find(root, "work")
    id_el    = _find(root, "identification")
    title    = (_text(work_el, "work-title") or _text(root, "movement-title") or "")
    subtitle = _text(work_el, "work-number") or ""
    composer = _creator(id_el, "composer")
    lyricist = _creator(id_el, "lyricist")
    rights   = (_text(id_el, "rights") or "") if id_el is not None else ""

    parts = [el for el in root.iter() if _tag(el) == "part"]
    if not parts:
        raise ValueError("No <part> elements found.")
    part     = _choose_part(parts)
    measures = _findall(part, "measure")
    if not measures:
        raise ValueError("No <measure> elements found.")

    first_attrs                     = _find(measures[0], "attributes")
    key, time, n_staves, clef_types = _parse_attributes(first_attrs)

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
    stats        = dict(chords=0, grace=0, types=0, overflow=0)

    # keyed by (staff_idx, voice) so each voice has its own beat counter
    open_ties:    dict[tuple, Note] = {}
    tuplet_state: dict[tuple, dict] = {}

    for m_idx, measure in enumerate(measures):

        # flush any incomplete tuplets from the previous measure
        for vk, ts in list(tuplet_state.items()):
            if ts["notes"] and m_idx > 0:
                from .tuplet import Tuplet as _Tuplet
                si = vk[0]
                tp = _Tuplet(ts["notes"], ts["actual"], ts["normal"],
                             staff=score.staffs[si])
                score.staffs[si].bars[m_idx - 1].events.append(tp)
        tuplet_state.clear()

        # (staff_idx, voice) → beats consumed in this measure
        voice_used: dict[tuple, float] = {}
        # staff_idx → [(beat_pos, event)]  collected before sorting/merging
        collected:  dict[int, list]    = {}
        # (staff_idx, voice) → last Note/Chord (for within-voice <chord/> detection)
        last_voice_ev: dict[tuple, object] = {}

        for note_el in _findall(measure, "note"):

            if _find(note_el, "grace") is not None:
                stats["grace"] += 1
                continue

            time_mod  = _find(note_el, "time-modification")
            is_tuplet = time_mod is not None

            ntype = _note_type(note_el)
            if ntype is None:
                stats["types"] += 1
                continue

            staff_idx = min(int(_text(note_el, "staff", "1")) - 1, n_staves - 1)
            voice     = _text(note_el, "voice", "1")
            vk        = (staff_idx, voice)

            is_rest       = _find(note_el, "rest")  is not None
            is_chord_note = _find(note_el, "chord") is not None

            staff    = score.staffs[staff_idx]
            beat_pos = voice_used.get(vk, 0.0)

            is_full_measure = _is_full_measure_rest(note_el)

            if is_tuplet and time_mod is not None:
                try:
                    actual_n = int(_text(time_mod, "actual-notes", "3"))
                    normal_n = int(_text(time_mod, "normal-notes", "2"))
                except (ValueError, TypeError):
                    actual_n, normal_n = 3, 2
                note_beat = get_value(ntype) * (normal_n / actual_n)
            elif is_full_measure:
                note_beat = bar_capacity - beat_pos
            else:
                note_beat = get_value(ntype)

            # chord note within the same voice — merge into previous event
            if is_chord_note and not is_rest:
                prev = last_voice_ev.get(vk)
                if prev is not None:
                    pitch = _pitch_str(note_el)
                    if pitch:
                        new_note = Note(ntype=ntype, pitch=pitch, staff=staff)
                        if isinstance(prev, Chord):
                            prev.notes.append(new_note)
                            prev.notes.sort(
                                key=lambda n: pitch_to_step(n.pitch, staff.clef_type),
                                reverse=True,
                            )
                        elif isinstance(prev, Note):
                            chord = Chord([prev, new_note], staff=staff)
                            clist = collected.setdefault(staff_idx, [])
                            for i, (bp, ev) in enumerate(clist):
                                if ev is prev:
                                    clist[i] = (bp, chord)
                                    break
                            last_voice_ev[vk] = chord
                        stats["chords"] += 1
                continue

            if is_chord_note and is_rest:
                stats["chords"] += 1
                continue

            if not is_full_measure and beat_pos + note_beat > bar_capacity + 1e-6:
                stats["overflow"] += 1
                continue

            if is_rest:
                ev = Rest(rtype=ntype, staff=staff)
                if is_tuplet:
                    _add_to_tuplet(tuplet_state, vk, ev, actual_n, normal_n,
                                   beat_pos, collected, staff_idx, staff)
                else:
                    collected.setdefault(staff_idx, []).append((beat_pos, ev))
                voice_used[vk] = beat_pos + note_beat
            else:
                pitch = _pitch_str(note_el)
                if pitch is None:
                    continue
                ev = Note(ntype=ntype, pitch=pitch, staff=staff)

                tie_key = (staff_idx, voice, pitch)
                if tie_key in open_ties:
                    open_ties[tie_key].tied_to = ev
                    ev.tied_from = True
                    del open_ties[tie_key]
                for tie_el in _findall(note_el, "tie"):
                    if tie_el.get("type") == "start":
                        open_ties[tie_key] = ev
                        break

                _attach_expressions(note_el, ev, staff)

                if is_tuplet:
                    _add_to_tuplet(tuplet_state, vk, ev, actual_n, normal_n,
                                   beat_pos, collected, staff_idx, staff)
                else:
                    collected.setdefault(staff_idx, []).append((beat_pos, ev))
                    last_voice_ev[vk] = ev

                voice_used[vk] = beat_pos + note_beat

        # sort by beat position and merge cross-voice notes at the same beat into Chords
        for staff_idx, events_list in collected.items():
            events_list.sort(key=lambda x: x[0])
            bar    = score.staffs[staff_idx].bars[m_idx]
            merged = {}  # rounded_beat → event

            for beat_pos, ev in events_list:
                bp_key = round(beat_pos, 9)
                if bp_key in merged:
                    ex = merged[bp_key]
                    if isinstance(ex, Rest) and isinstance(ev, Note):
                        merged[bp_key] = ev  # note beats rest
                    elif isinstance(ex, Note) and isinstance(ev, Note):
                        merged[bp_key] = Chord([ex, ev], staff=score.staffs[staff_idx])
                    elif isinstance(ex, Chord) and isinstance(ev, Note):
                        ex.notes.append(ev)
                        ex.notes.sort(
                            key=lambda n: pitch_to_step(n.pitch, score.staffs[staff_idx].clef_type),
                            reverse=True,
                        )
                else:
                    merged[bp_key] = ev

            for bp_key in sorted(merged.keys()):
                bar.events.append(merged[bp_key])

    # flush remaining open tuplets after the last measure
    for vk, ts in tuplet_state.items():
        if ts["notes"] and measures:
            from .tuplet import Tuplet as _Tuplet
            si = vk[0]
            tp = _Tuplet(ts["notes"], ts["actual"], ts["normal"],
                         staff=score.staffs[si])
            score.staffs[si].bars[-1].events.append(tp)

    _report(stats)
    return score


def _attach_expressions(note_el, note, staff):
    from .expressions import Dynamic, Articulation, _XML_ARTICULATIONS, _XML_DYNAMICS
    notations = _find(note_el, "notations")
    if notations is None:
        return
    stem_dir  = getattr(note, "_stem_dir", lambda: "up")()
    above_art = (stem_dir == "down")

    for dyn_el in _findall(notations, "dynamics"):
        for child in dyn_el:
            name = _tag(child).lower()
            if name in _XML_DYNAMICS:
                note.expressions.append(Dynamic(name, staff=staff, above=False))

    for _ in _findall(notations, "fermata"):
        note.expressions.append(Articulation("fermata", staff=staff, above=True))

    art_el = _find(notations, "articulations")
    if art_el is not None:
        for child in art_el:
            name     = _tag(child).lower()
            internal = _XML_ARTICULATIONS.get(name)
            if internal:
                note.expressions.append(
                    Articulation(internal, staff=staff, above=above_art)
                )


def _add_to_tuplet(tuplet_state, voice_key, note, actual, normal,
                   beat_pos, collected, staff_idx, staff):
    from .tuplet import Tuplet as _Tuplet
    ts = tuplet_state.get(voice_key)
    if ts is None or ts["actual"] != actual or ts["normal"] != normal:
        if ts and ts["notes"]:
            tp = _Tuplet(ts["notes"], ts["actual"], ts["normal"], staff=staff)
            collected.setdefault(staff_idx, []).append((ts["start_beat"], tp))
        tuplet_state[voice_key] = {
            "actual": actual, "normal": normal,
            "notes": [], "start_beat": beat_pos,
        }
        ts = tuplet_state[voice_key]
    ts["notes"].append(note)
    if len(ts["notes"]) >= actual:
        tp = _Tuplet(ts["notes"], actual, normal, staff=staff)
        collected.setdefault(staff_idx, []).append((ts["start_beat"], tp))
        del tuplet_state[voice_key]


def _parse_root(filepath):
    import os, zipfile
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
            if xml_path is None:
                raise ValueError("Could not locate XML content inside .mxl archive.")
            return ET.parse(zf.open(xml_path)).getroot()

    return ET.parse(filepath).getroot()


def _report(stats):
    total = sum(stats.values())
    if not total:
        return
    print("[pylute] MusicXML import — simplifications applied:")
    labels = [
        ("chords",   "chord notes collected (kept as Chord objects)"),
        ("grace",    "grace notes skipped"),
        ("types",    "unsupported note types skipped (64th, 128th, etc.)"),
        ("overflow", "notes skipped (bar over-capacity)"),
    ]
    for key, desc in labels:
        if stats[key]:
            print(f"  {stats[key]:4d}  {desc}")
