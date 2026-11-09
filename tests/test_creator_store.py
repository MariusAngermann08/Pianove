"""The lesson editor's storage: making, saving, duplicating and checking lessons, and
packages. Every test works in a temporary folder, never in ~/.pianove."""
import json
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "PyLay"))

from pianove import lesson_loader  # noqa: E402
from pianove import creator_store as cs  # noqa: E402
from pianove import creator_notes as cn  # noqa: E402


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setattr(lesson_loader, "_USER_LESSONS", tmp_path / "lessons")
    monkeypatch.setattr(lesson_loader, "_USER_COURSES", tmp_path / "courses")
    return tmp_path


# ── notes ──────────────────────────────────────────────────────────────────────────

def test_note_names_round_trip():
    assert cn.parse_note("C4") == 60
    assert cn.parse_note("F#4") == 66
    assert cn.parse_note("Bb3") == 58
    assert cn.parse_note("H4") is None
    assert cn.parse_chord("C4+E4+G4") == [60, 64, 67]
    assert cn.parse_chord("C4+") is None
    assert cn.note_name(61) == "C#4"
    assert cn.chord_name([67, 60, 64]) == "C4+E4+G4"


def test_keys_struck_together_become_one_chord():
    events = [(0.00, 60), (0.02, 64), (0.03, 67), (0.50, 62), (1.00, 64), (1.06, 67)]
    assert cn.group_chords(events) == [[60, 64, 67], [62], [64], [67]]


def test_split_bars_and_words():
    assert cn.split_bars(["C4", "D4", "E4", "F4", "G4"], 4) == [["C4", "D4", "E4", "F4"], ["G4"]]
    assert cn.split_words("C4, D4  E4") == ["C4", "D4", "E4"]


# ── lessons ────────────────────────────────────────────────────────────────────────

def test_new_lesson_is_found_by_the_loader(home):
    lid = cs.new_lesson("Waltz für Mia", author="Mia")
    assert lid == "waltz_fuer_mia"
    lesson = lesson_loader.load_lesson(lid)
    assert lesson is not None
    assert lesson["meta"]["author"] == "Mia"
    assert [s["type"] for s in lesson["steps"]] == ["scene", "exercise"]
    assert any(i["id"] == lid for i in lesson_loader.list_lessons())


def test_new_lesson_never_takes_a_used_id(home):
    assert cs.new_lesson("Welcome") == "welcome_2"          # "welcome" is built in
    assert cs.new_lesson("Welcome") == "welcome_3"


def test_save_keeps_fields_the_editor_does_not_know(home):
    lid = cs.new_lesson("Test")
    d = cs.load_draft(lid)
    d["steps"][0]["beats"][0]["velocities"] = [90, 60, 60]
    d["steps"][0]["beats"][0]["something_new"] = {"x": 1}
    d["strings"]["en"]["title"] = "Renamed"
    cs.save_draft(d)
    again = cs.load_draft(lid)
    assert again["steps"][0]["beats"][0]["velocities"] == [90, 60, 60]
    assert again["steps"][0]["beats"][0]["something_new"] == {"x": 1}
    assert again["strings"]["en"]["title"] == "Renamed"
    # nothing half-written is left behind
    assert not [p for p in (home / "lessons" / lid).iterdir() if p.name.endswith(".tmp")]


def test_saved_files_read_like_the_built_in_ones(home):
    lid = cs.new_lesson("Format")
    text = (home / "lessons" / lid / "steps.json").read_text(encoding="utf-8")
    assert '"bars": [["C4", "D4", "E4", "F4"]]' in text


def test_duplicate_a_built_in_lesson(home):
    new_id = cs.duplicate_lesson("welcome", author="Sam")
    assert new_id == "welcome_copy"
    assert cs.is_builtin_lesson("welcome")                 # the original stays
    d = cs.load_draft(new_id)
    assert d["meta"]["id"] == new_id
    assert d["meta"]["based_on"] == "welcome"
    assert d["meta"]["author"] == "Sam"
    assert d["strings"]["en"]["title"].endswith("(copy)")
    assert d["strings"]["de"]["title"].endswith("(Kopie)")
    assert cs.duplicate_lesson("welcome") == "welcome_copy_2"


def test_only_own_lessons_can_be_deleted(home):
    lid = cs.new_lesson("Gone soon")
    assert cs.delete_lesson(lid)
    assert lesson_loader.load_lesson(lid) is None
    assert not cs.delete_lesson("welcome")
    assert cs.is_builtin_lesson("welcome")
    assert not cs.delete_lesson("../etc")


def test_list_own_lessons(home):
    a = cs.new_lesson("First")
    b = cs.new_lesson("Second")
    ids = [i["id"] for i in cs.list_own_lessons()]
    assert set(ids) == {a, b}
    assert all(i["n_steps"] == 2 for i in cs.list_own_lessons())


# ── checking ───────────────────────────────────────────────────────────────────────

def _codes(draft):
    return {code for _, code, _ in cs.validate(draft)}


def test_built_in_lessons_pass_the_check():
    for d in sorted((ROOT / "pianove" / "lessons").iterdir()):
        if (d / "meta.json").exists():
            draft = {
                "id": d.name,
                "meta": json.loads((d / "meta.json").read_text(encoding="utf-8")),
                "strings": {lang: json.loads((d / f"{lang}.json").read_text(encoding="utf-8"))
                            for lang in ("en", "de")},
                "steps": json.loads((d / "steps.json").read_text(encoding="utf-8")),
            }
            assert cs.validate(draft) == [], d.name


def test_check_finds_mistakes(home):
    d = cs.load_draft(cs.new_lesson("Broken"))
    beat = d["steps"][0]["beats"][0]
    beat["play"] = ["C4", "H4", "C9"]
    beat["fingers"] = [1, 2]
    beat["say"] = {"en": "Hello", "de": ""}
    d["steps"][1]["bars"] = [["C4", "E4+G4"], []]
    d["strings"]["de"]["title"] = ""
    codes = _codes(d)
    assert {"bad_note", "out_of_range", "fingers_mismatch", "missing_say",
            "empty_bar", "missing_title"} <= codes
    assert "chord_in_exercise" not in codes                 # exercises can hold chords now


def test_check_reads_note_values(home):
    d = cs.load_draft(cs.new_lesson("Rhythm"))
    ex = d["steps"][1]
    ex["time"] = [3, 4]
    ex["bars"] = [["C4", "r", "E4+G4"], ["C4", "D4"]]
    ex["types"] = [["quarter", "quarter", "quarter"], ["half", "half"]]
    codes = {(w, c) for w, c, _ in cs.validate(d)}
    assert (("bar", 1, 1), "bar_too_full") in codes
    assert not any(w == ("bar", 1, 0) for w, _ in codes)
    ex["types"] = [["quarter"]]
    assert "bad_types" in _codes(d)


def test_a_lesson_should_end_with_an_exercise(home):
    d = cs.load_draft(cs.new_lesson("Order"))
    d["steps"].reverse()
    assert "last_not_exercise" in _codes(d)


# ── packages ───────────────────────────────────────────────────────────────────────

def test_package_round_trip(home, tmp_path):
    lid = cs.new_lesson("Shared")
    cid = cs.new_course("My course")
    course = cs.load_course(cid)
    course["meta"]["lessons"] = ["welcome", lid]
    cs.save_course(course)

    pkg = cs.export_package("course", cid, tmp_path / "out")
    with zipfile.ZipFile(pkg) as zf:
        names = zf.namelist()
    assert f"courses/{cid}/meta.json" in names
    assert f"lessons/{lid}/steps.json" in names
    assert not any(n.startswith("lessons/welcome/") for n in names)   # built in everywhere

    cs.delete_lesson(lid)
    cs.delete_course(cid)
    got = cs.import_package(pkg)
    assert got["lessons"] == [lid] and got["courses"] == [cid]
    assert lesson_loader.load_lesson(lid) is not None
    assert any(c["id"] == cid for c in lesson_loader.list_courses())


def test_package_of_a_plain_lesson_folder(home, tmp_path):
    pkg = tmp_path / "plain.pianove-pkg"
    src = ROOT / "pianove" / "lessons" / "c_major_scale"
    with zipfile.ZipFile(pkg, "w") as zf:
        for f in src.iterdir():
            zf.write(f, f"c_major_scale/{f.name}")
    got = cs.import_package(pkg)
    assert got == {"lessons": ["c_major_scale"], "courses": [], "replaced_builtin": ["c_major_scale"]}


def test_unsafe_packages_are_refused(home, tmp_path):
    bad = tmp_path / "bad.pianove-pkg"
    with zipfile.ZipFile(bad, "w") as zf:
        zf.writestr("lessons/x/meta.json", '{"id": "x"}')
        zf.writestr("lessons/x/../../evil.txt", "no")
    with pytest.raises(cs.PackageError) as e:
        cs.import_package(bad)
    assert e.value.code == "unsafe_path"

    junk = tmp_path / "junk.pianove-pkg"
    junk.write_bytes(b"not a zip")
    with pytest.raises(cs.PackageError) as e:
        cs.import_package(junk)
    assert e.value.code == "not_a_package"


# ── MusicXML ───────────────────────────────────────────────────────────────────────

def test_exercise_from_musicxml(tmp_path):
    xml = tmp_path / "tune.musicxml"
    notes = "".join(
        f"<note><pitch><step>{s}</step><octave>4</octave></pitch><duration>1</duration>"
        f"<type>quarter</type></note>" for s in "CDEFGAGF")
    chord = ("<note><pitch><step>C</step><octave>4</octave></pitch><duration>4</duration><type>whole</type></note>"
             "<note><chord/><pitch><step>E</step><octave>4</octave></pitch><duration>4</duration><type>whole</type></note>")
    xml.write_text(
        '<?xml version="1.0"?><score-partwise version="3.1"><part-list><score-part id="P1">'
        '<part-name>P</part-name></score-part></part-list><part id="P1">'
        '<measure number="1"><attributes><divisions>1</divisions><time><beats>4</beats>'
        '<beat-type>4</beat-type></time><clef><sign>G</sign><line>2</line></clef></attributes>'
        + notes[: len(notes) // 2] + '</measure><measure number="2">' + notes[len(notes) // 2:]
        + '</measure><measure number="3">' + chord + "</measure></part></score-partwise>",
        encoding="utf-8")
    ex = cs.exercise_from_musicxml(xml)
    assert ex["time"] == [4, 4]
    assert ex["bars"] == [["C4", "D4", "E4", "F4"], ["G4", "A4", "G4", "F4"], ["C4+E4"]]
    assert ex["types"][2] == ["whole"]
    assert ex["types"][0] == ["quarter"] * 4


def _note(step, octave, dur, ntype, staff=1, chord=False, tie=None):
    tie_el = f'<tie type="{tie}"/>' if tie else ""
    return (f"<note>{'<chord/>' if chord else ''}<pitch><step>{step}</step><octave>{octave}</octave></pitch>"
            f"<duration>{dur}</duration>{tie_el}<type>{ntype}</type><staff>{staff}</staff></note>")


def test_musicxml_ties_triplets_and_both_hands(tmp_path):
    # divisions 3: a quarter is 3, a triplet eighth 1
    m1 = (_note("C", 4, 1, "eighth") + _note("D", 4, 1, "eighth") + _note("E", 4, 1, "eighth")
          + _note("F", 4, 3, "quarter") + _note("G", 4, 6, "half", tie="start")
          + "<backup><duration>12</duration></backup>" + _note("C", 3, 12, "whole", staff=2))
    m2 = (_note("G", 4, 3, "quarter", tie="stop") + _note("A", 4, 9, "dotted_half")
          + "<backup><duration>12</duration></backup>" + _note("G", 2, 12, "whole", staff=2))
    xml = tmp_path / "both.musicxml"
    xml.write_text(
        '<?xml version="1.0"?><score-partwise version="3.1"><part-list><score-part id="P1">'
        '<part-name>P</part-name></score-part></part-list><part id="P1">'
        '<measure number="1"><attributes><divisions>3</divisions><time><beats>4</beats>'
        '<beat-type>4</beat-type></time><staves>2</staves><clef number="1"><sign>G</sign><line>2</line></clef>'
        '<clef number="2"><sign>F</sign><line>4</line></clef></attributes>'
        + m1 + '</measure><measure number="2">' + m2 + "</measure></part></score-partwise>",
        encoding="utf-8")
    ex = cs.exercise_from_musicxml(xml, "both")
    assert ex["bars"] == [["C4", "D4", "E4", "F4", "G4~"], ["G4", "A4"]]
    assert ex["types"][0] == ["triplet_eighth"] * 3 + ["quarter", "half"]
    assert ex["lh"]["bars"] == [["C3"], ["G2"]]
    d = {"id": "x", "meta": {"locales": ["en"]}, "strings": {"en": {"title": "x"}},
         "steps": [{"type": "exercise", **ex}]}
    assert cs.validate(d) == []
