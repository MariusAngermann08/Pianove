# PyInstaller spec: builds Pianove as a stand-alone app (no Python needed to run it).
#
#     pip install pyinstaller
#     pyinstaller pianove.spec          → dist/Pianove/  (dist/Pianove.app on macOS)
#
# The FluidSynth library is taken from the build machine and shipped inside the app:
# on Windows from bin/, elsewhere from wherever the system has it (brew, apt, dnf).
# .github/workflows/build.yml runs this on Windows, macOS and Linux.
import ctypes.util
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(SPECPATH)


def tree(src: str, dest: str):
    """Every file under src that isn't Python source, kept at the same place under dest."""
    out = []
    for path in (ROOT / src).rglob("*"):
        if path.is_file() and path.suffix not in (".py", ".pyc") and "__pycache__" not in path.parts:
            out.append((str(path), str(Path(dest) / path.parent.relative_to(ROOT / src))))
    return out


def fluidsynth_libs():
    if sys.platform == "win32":
        return [(str(p), ".") for p in (ROOT / "bin").glob("*.dll")]
    names = ("fluidsynth", "fluidsynth-3", "libfluidsynth")
    found = next((ctypes.util.find_library(n) for n in names if ctypes.util.find_library(n)), None)
    if found and not os.path.isabs(found):            # Linux: only a soname; ask ldconfig
        out = subprocess.run(["ldconfig", "-p"], capture_output=True, text=True).stdout
        found = next((line.split("=>")[-1].strip() for line in out.splitlines()
                      if found in line and "=>" in line), None)
    if not found and sys.platform == "darwin":
        for prefix in (os.getenv("HOMEBREW_PREFIX", ""), "/opt/homebrew", "/usr/local"):
            cand = Path(prefix) / "lib" / "libfluidsynth.dylib"
            if prefix and cand.exists():
                found = str(cand)
                break
    if not found:
        print("WARNING: libfluidsynth not found; the app will run without piano sound")
        return []
    return [(os.path.realpath(found), ".")]


datas = (tree("pianove", "pianove")
         + tree("PyLay/pylay", "pylay")
         + tree("PyLute/pylute", "pylute"))

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT), str(ROOT / "PyLay"), str(ROOT / "PyLute")],
    binaries=fluidsynth_libs(),
    datas=datas,
    hiddenimports=["mido.backends.rtmidi", "rtmidi", "sounddevice", "fluidsynth"],
    excludes=["tkinter", "pytest", "matplotlib"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="Pianove",
    console=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="Pianove")

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="Pianove.app",
        bundle_identifier="org.pianove.app",
        info_plist={
            "NSMicrophoneUsageDescription": "Pianove listens to your piano to hear which keys you play.",
            "NSHighResolutionCapable": True,
        },
    )
