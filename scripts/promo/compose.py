"""
Cut the Pianove promo video from the clips record.py made.

    python scripts/promo/compose.py CLIPS_DIR OUT.mp4

1920×1080, 30 fps. A text column on the left, the app on the right; the soundtrack is
the notes the app itself played in each clip (rendered offline with FluidSynth and the
Salamander grand Pianove ships), so what you hear is what you see.
"""
from __future__ import annotations

import json
import math
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
CLIPS = Path(sys.argv[1] if len(sys.argv) > 1 else "promo_clips")
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else "pianove-promo.mp4")

W, H, FPS = 1920, 1080, 30
VIEW_W, VIEW_H = 1350, 844
WIN_X, WIN_Y = W - 80 - VIEW_W, (H - VIEW_H) // 2
COL_X, COL_W = 96, WIN_X - 96 - 48
RATE = 48000

BG = (14, 14, 16)
TEXT = (242, 242, 245)
MUTED = (150, 150, 158)
GOLD = (212, 160, 23)
BORDER = (44, 44, 48)

FONTS = ROOT / "PyLay" / "pylay" / "assets"


def font(size, bold=False):
    return ImageFont.truetype(str(FONTS / ("Inter-Bold.ttf" if bold else "Inter-Regular.ttf")), size)


# ── the cut ──────────────────────────────────────────────────────────────────────
# kind: "title" | "clip" (footage) | "still" | "end"; for clips: src, clip time at the cut
# (in), and whether its notes go on the soundtrack
SHOTS = [
    dict(kind="title", dur=3.6),
    dict(kind="clip", src="theory", t_in=0.6, dur=8.4, notes=True,
         eyebrow="LESSONS", head="See it, then\nplay it.",
         body="Each lesson opens with a short scene: the idea on the keys, and a hand that plays it."),
    dict(kind="clip", src="exercise", t_in=0.4, dur=5.6, notes=True,
         eyebrow="LESSONS", head="The music\nwaits for you.",
         body="Play note by note, at your own pace. Every right note turns green."),
    dict(kind="clip", src="computer_keys", t_in=0.3, dur=4.7, notes=True,
         eyebrow="NO PIANO YET?", head="Start on\nyour laptop.",
         body="Your computer keys play the notes. Add a MIDI keyboard, or let the microphone hear a real piano, when you're ready.",
         keycaps=True),
    dict(kind="still", src="song_path", dur=4.0, zoom=(1.0, 1.035), focus=(0.5, 0.35),
         eyebrow="SONGS", head="Any piece.\nIn steps.",
         body="Import a MusicXML file. Pianove builds the path: right hand, left hand, both, then the whole piece."),
    dict(kind="clip", src="chopin", t_in=4.1, dur=7.8, notes=False,
         eyebrow="SONGS", head="All the way\nto Chopin.",
         body="Slow it down, loop the hard bars, and follow the fingering on screen."),
    dict(kind="clip", src="home", t_in=0.0, dur=4.2, notes=False, hold_zoom=1.03,
         eyebrow="PROGRESS", head="Practice\nthat counts.",
         body="Minutes measured from what you actually play, against a goal you set."),
    dict(kind="still", src="editor", dur=4.0, zoom=(1.0, 1.04), focus=(0.62, 0.3),
         eyebrow="CREATOR MODE", head="Write your\nown lessons.",
         body="Scenes, pieces and translations, shared as a single file."),
    dict(kind="end", dur=6.2),
]
# Chopin starts under the song-path still: its first note lands just after that cut, and
# the footage that follows is the same performance, so picture and sound stay together
MUSIC = dict(src="chopin", start_shot=4, lead=0.1)
XFADE = 0.0          # hard cuts: dissolving one UI into another only looks muddy

t = 0.0
for s in SHOTS:
    s["t0"] = t
    t += s["dur"]
TOTAL = t
music_t0 = SHOTS[MUSIC["start_shot"]]["t0"] + MUSIC["lead"] - 0.4   # clip note 1 is at 0.4 s
SHOTS[5]["t_in"] = SHOTS[5]["t0"] - music_t0                          # the footage in sync


def ease_out(x):
    x = max(0.0, min(1.0, x))
    return 1 - (1 - x) ** 3


def ease_in_out(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


# ── footage ─────────────────────────────────────────────────────────────────────
class Clip:
    """Frames of a recorded clip. The clip is unpacked once into JPEG frames on disk
    (ffmpeg reading into a pipe buffers decoded frames ahead and runs out of memory),
    then each frame is loaded when it's needed; past the end the last one is held."""

    def __init__(self, name):
        self.dir = CLIPS / f"{name}_frames"
        if not (self.dir / "done").exists():
            self.dir.mkdir(exist_ok=True)
            subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-threads", "1",
                            "-i", str(CLIPS / f"{name}.mkv"), "-q:v", "1", "-qmin", "1",
                            str(self.dir / "%05d.jpg")], check=True)
            (self.dir / "done").write_text("")
        self.n = len(list(self.dir.glob("*.jpg")))
        self.idx, self.frame = None, None

    def at(self, clip_t):
        want = min(self.n - 1, max(0, int(round(clip_t * FPS))))
        if want != self.idx:
            with Image.open(self.dir / f"{want + 1:05d}.jpg") as im:
                self.frame = im.convert("RGB")
            self.idx = want
        return self.frame

    def close(self):
        pass


def release_clips_before(i):
    needed = {s.get("src") for s in SHOTS[max(0, i - 1):]}
    for name in [n for n in _clips if n not in needed]:
        _clips.pop(name).close()


_clips: dict[str, Clip] = {}
_stills: dict[str, Image.Image] = {}


def footage(shot, t):
    """The app picture of a shot at video time t."""
    local = t - shot["t0"]
    if shot["kind"] == "still":
        img = _stills.setdefault(shot["src"], Image.open(CLIPS / f"{shot['src']}.png").convert("RGB"))
        z0, z1 = shot["zoom"]
        return zoom(img, z0 + (z1 - z0) * ease_in_out(local / shot["dur"]), shot["focus"])
    clip = _clips.setdefault(shot["src"], Clip(shot["src"]))
    img = clip.at(shot["t_in"] + local)
    if shot.get("hold_zoom"):
        img = zoom(img, 1.0 + (shot["hold_zoom"] - 1.0) * ease_in_out(local / shot["dur"]), (0.5, 0.4))
    return img


def zoom(img, z, focus):
    if z <= 1.0001:
        return img
    w, h = img.size
    cw, ch = w / z, h / z
    fx, fy = focus
    x0 = min(max(0.0, fx * w - cw / 2), w - cw)
    y0 = min(max(0.0, fy * h - ch / 2), h - ch)
    return img.resize((w, h), Image.LANCZOS, box=(x0, y0, x0 + cw, y0 + ch))


_mask = Image.new("L", (VIEW_W, VIEW_H), 0)
ImageDraw.Draw(_mask).rounded_rectangle((0, 0, VIEW_W - 1, VIEW_H - 1), radius=14, fill=255)


def put_window(canvas, img, alpha=1.0):
    m = _mask if alpha >= 0.999 else _mask.point(lambda v: int(v * alpha))
    canvas.paste(img, (WIN_X, WIN_Y), m)


def window_border(draw):
    draw.rounded_rectangle((WIN_X - 1, WIN_Y - 1, WIN_X + VIEW_W, WIN_Y + VIEW_H), radius=15,
                           outline=BORDER, width=1)


# ── type ────────────────────────────────────────────────────────────────────────
F_EYEBROW, F_HEAD, F_BODY = font(17, True), font(56, True), font(24)
F_WORD_S = font(26, True)


def tracked(draw, xy, text, fnt, fill, tracking):
    x, y = xy
    for ch in text:
        draw.text((x, y), ch, font=fnt, fill=fill)
        x += draw.textlength(ch, font=fnt) + tracking


def wrap(text, fnt, width):
    words, lines, cur = text.split(), [], ""
    for w in words:
        test = f"{cur} {w}".strip()
        if fnt.getlength(test) <= width:
            cur = test
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def text_layer(shot):
    """The text column of a shot as three transparent layers (eyebrow, headline, body),
    each with its y position, so they can come in one after the other."""
    layers = []
    head_lines = shot["head"].split("\n")
    body_lines = wrap(shot["body"], F_BODY, COL_W)
    head_h = len(head_lines) * 64
    body_h = len(body_lines) * 36
    total = 22 + 26 + head_h + 26 + body_h
    y = (H - total) // 2 - 10

    def layer(h, paint):
        img = Image.new("RGBA", (COL_W + 40, h), (0, 0, 0, 0))
        paint(ImageDraw.Draw(img))
        return img

    layers.append((layer(26, lambda d: tracked(d, (0, 0), shot["eyebrow"], F_EYEBROW, GOLD, 2.2)), y))
    y += 22 + 26
    layers.append((layer(head_h + 12, lambda d: [d.text((0, i * 64), ln, font=F_HEAD, fill=TEXT)
                                                 for i, ln in enumerate(head_lines)]), y))
    y += head_h + 26
    layers.append((layer(body_h + 10, lambda d: [d.text((0, i * 36), ln, font=F_BODY, fill=MUTED)
                                                 for i, ln in enumerate(body_lines)]), y))
    return layers


def faded(img, a):
    if a >= 0.999:
        return img
    r, g, b, al = img.split()
    return Image.merge("RGBA", (r, g, b, al.point(lambda v: int(v * a))))


KEY_ROW = "ASDFGHJKL"
KEY_NOTE = {60: "A", 62: "S", 64: "D", 65: "F", 67: "G", 69: "H", 71: "J", 72: "K", 74: "L"}
F_KEY = font(20, True)


def draw_keycaps(canvas, shot, t):
    """The computer keys under the text; the one playing lights up, from the clip's notes."""
    local = t - shot["t0"]
    a = min(ease_out((local - 0.5) / 0.5), 1.0 - ease_in_out((local - (shot["dur"] - 0.35)) / 0.3))
    if a <= 0.003:
        return
    if "_presses" not in shot:
        ev = json.loads((CLIPS / f"{shot['src']}.json").read_text())["events"]
        downs = {}
        shot["_presses"] = []
        for ct, kind, m, _ in ev:
            if kind:
                downs[m] = ct
            elif m in downs:
                shot["_presses"].append((downs.pop(m), ct, m))
    ct = shot["t_in"] + local
    lit = {KEY_NOTE.get(m) for t0, t1, m in shot["_presses"] if t0 <= ct < t1}
    layer = Image.new("RGBA", (COL_W + 40, 60), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    size, gap = 34, 5
    for i, ch in enumerate(KEY_ROW):
        x = i * (size + gap)
        on = ch in lit
        d.rounded_rectangle((x, 4 if on else 0, x + size, size + (4 if on else 0)), radius=6,
                            fill=GOLD if on else (30, 30, 34), outline=None if on else (58, 58, 64))
        if not on:
            d.line((x + 4, size + 2, x + size - 4, size + 2), fill=(58, 58, 64), width=3)
        tw = d.textlength(ch, font=F_KEY)
        d.text((x + (size - tw) / 2, (4 if on else 0) + 6), ch, font=F_KEY,
               fill=(20, 16, 4) if on else TEXT)
    y = shot["_layers"][-1][1] + shot["_layers"][-1][0].height + 26
    canvas.alpha_composite(faded(layer, a), (COL_X, y))


def draw_text(canvas, shot, t, prev_shot, next_shot):
    local, dur = t - shot["t0"], shot["dur"]
    if "_layers" not in shot:
        shot["_layers"] = text_layer(shot)
    layers = shot["_layers"]
    same_eyebrow_in = prev_shot is not None and prev_shot.get("eyebrow") == shot["eyebrow"]
    same_eyebrow_out = next_shot is not None and next_shot.get("eyebrow") == shot["eyebrow"]
    for k, (img, y) in enumerate(layers):
        keep_in = k == 0 and same_eyebrow_in
        keep_out = k == 0 and same_eyebrow_out
        a_in = 1.0 if keep_in else ease_out((local - 0.12 - 0.09 * k) / 0.55)
        a_out = 1.0 if keep_out else 1.0 - ease_in_out((local - (dur - 0.35)) / 0.3)
        a = max(0.0, min(a_in, a_out))
        if a <= 0.003:
            continue
        rise = 0 if keep_in else int(round(14 * (1 - a_in)))
        canvas.alpha_composite(faded(img, a), (COL_X, y + rise))


# ── the logo, drawn like the app draws it: four keys, two black, one in gold ────
def draw_logo(canvas, cx, cy, scale, lit, word_alpha=1.0, word=True):
    d = ImageDraw.Draw(canvas)
    ww, wh, bw, bh, rad = 10 * scale, 36 * scale, 7 * scale, 22 * scale, 3 * scale
    f = font(int(round(30 * scale)), True)
    word_w = f.getlength("Pianove") if word else 0
    gap = 10 * scale
    total = 4 * ww + (gap + word_w if word else 0)
    ox, oy = cx - total / 2, cy - wh / 2
    for i in range(4):
        x0 = ox + i * ww
        a = lit[i]
        col = tuple(int(238 + a * (g - 238)) for g in GOLD) if a > 0 else (238, 238, 244)
        d.rounded_rectangle((x0, oy, x0 + ww - max(1, scale * 0.6), oy + wh), radius=rad, fill=col,
                            corners=(False, False, True, True))
    for slot in (0, 1):
        bx = ox + (slot + 1) * ww - bw / 2
        d.rounded_rectangle((bx, oy, bx + bw, oy + bh), radius=rad, fill=(22, 22, 24),
                            corners=(False, False, True, True))
    if word and word_alpha > 0.003:
        layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)
        tx = ox + 4 * ww + gap
        ty = cy - f.getbbox("Pianove")[3] / 2 - f.getbbox("P")[1] / 2
        ld.text((tx, ty), "P", font=f, fill=GOLD)
        ld.text((tx + f.getlength("P"), ty), "ianove", font=f, fill=TEXT)
        canvas.alpha_composite(faded(layer, word_alpha))


TITLE_NOTES = [(0.45, 60), (0.70, 62), (0.95, 64), (1.20, 65)]    # the logo's keys, C D E F


def logo_lit(t):
    lit = [0.0] * 4
    for i, (tn, _) in enumerate(TITLE_NOTES):
        if t >= tn:
            lit[i] = max(0.0, 1.0 - (t - tn) / 0.45)
    if t >= 1.5:                                          # settles on E, as in the app
        lit[2] = max(lit[2], ease_out((t - 1.5) / 0.4))
    return lit


def centered(canvas, y, text, fnt, fill, a):
    if a <= 0.003:
        return
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.text(((W - d.textlength(text, font=fnt)) / 2, y), text, font=fnt, fill=fill)
    canvas.alpha_composite(faded(layer, a))


F_TAG, F_SMALL = font(30), font(21)


def title_card(canvas, local):
    a_out = 1.0 - ease_in_out((local - 3.2) / 0.4)
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw_logo(layer, W / 2, H / 2 - 40, 4.2, logo_lit(local), word_alpha=ease_out((local - 0.25) / 0.7))
    centered(layer, H / 2 + 80, "Piano lessons that are free, open and yours.", F_TAG, MUTED,
             ease_out((local - 1.5) / 0.7))
    canvas.alpha_composite(faded(layer, a_out))


def end_card(canvas, local):
    a_in = ease_out(local / 0.8)
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw_logo(layer, W / 2, H / 2 - 90, 4.2, [0, 0, 1, 0], word_alpha=1.0)
    centered(layer, H / 2 + 30, "Free and open source.", F_TAG, TEXT, ease_out((local - 0.4) / 0.6))
    centered(layer, H / 2 + 76, "No account. No subscription. Works offline.", F_TAG, MUTED,
             ease_out((local - 0.6) / 0.6))
    centered(layer, H / 2 + 170, "Windows  ·  macOS  ·  Linux", F_SMALL, MUTED, ease_out((local - 1.0) / 0.6))
    centered(layer, H / 2 + 204, "github.com/MariusAngermann08/Pianove", F_SMALL, GOLD,
             ease_out((local - 1.1) / 0.6))
    canvas.alpha_composite(faded(layer, a_in))


def wordmark(canvas, a):
    """Small logo bottom left while the app is on screen."""
    if a <= 0.003:
        return
    layer = Image.new("RGBA", (360, 70), (0, 0, 0, 0))
    draw_logo(layer, 110, 35, 1.0, [0, 0, 1, 0])
    canvas.alpha_composite(faded(layer, a * 0.7), (COL_X - 34, H - 104))


# ── frames ──────────────────────────────────────────────────────────────────────
def frame(t):
    canvas = Image.new("RGBA", (W, H), BG + (255,))
    i = next(k for k, s in enumerate(SHOTS) if s["t0"] <= t < s["t0"] + s["dur"] or k == len(SHOTS) - 1)
    shot = SHOTS[i]
    prev_shot = SHOTS[i - 1] if i > 0 and "eyebrow" in SHOTS[i - 1] else None
    next_shot = SHOTS[i + 1] if i + 1 < len(SHOTS) and "eyebrow" in SHOTS[i + 1] else None
    local = t - shot["t0"]

    if shot["kind"] == "title":
        title_card(canvas, local)
    elif shot["kind"] == "end":
        end_card(canvas, local)
    else:
        rgb = canvas.convert("RGB")
        first = SHOTS[i - 1]["kind"] == "title"
        last = SHOTS[i + 1]["kind"] == "end"
        a = ease_out(local / 0.6) if first else 1.0
        if last:
            a = min(a, 1.0 - ease_in_out((local - (shot["dur"] - 0.5)) / 0.5))
        img = footage(shot, t)
        if not first and local < XFADE and SHOTS[i - 1]["kind"] in ("clip", "still"):
            before = footage(SHOTS[i - 1], t)          # the previous shot, run on under the dissolve
            put_window(rgb, before)
            put_window(rgb, img, ease_in_out(local / XFADE))
        else:
            put_window(rgb, img, a)
        if a > 0.5:
            window_border(ImageDraw.Draw(rgb))
        canvas = rgb.convert("RGBA")
        draw_text(canvas, shot, t, prev_shot, next_shot)
        if shot.get("keycaps"):
            draw_keycaps(canvas, shot, t)
        wa = ease_out(local / 0.6) if first else 1.0
        if last:
            wa = min(wa, 1.0 - ease_in_out((local - (shot["dur"] - 0.5)) / 0.5))
        wordmark(canvas, wa)
    return canvas.convert("RGB")


# ── sound ───────────────────────────────────────────────────────────────────────
def note_events():
    """(time, on, key, velocity) for the whole video."""
    out = [(tn, 1, m, 52) for tn, m in TITLE_NOTES] + [(2.6, 0, m, 0) for _, m in TITLE_NOTES]
    for s in SHOTS:
        if s["kind"] != "clip" or not s.get("notes"):
            continue
        ev = json.loads((CLIPS / f"{s['src']}.json").read_text())["events"]
        t_in, t_out = s["t_in"], s["t_in"] + s["dur"]
        on = set()
        for ct, kind, m, v in ev:
            if t_in <= ct < t_out:
                out.append((s["t0"] + ct - t_in, kind, m, v))
                (on.add if kind else on.discard)(m)
        out += [(s["t0"] + s["dur"], 0, m, 0) for m in on]
    ev = json.loads((CLIPS / f"{MUSIC['src']}.json").read_text())["events"]
    end = TOTAL - 0.6
    on = set()
    for ct, kind, m, v in ev:
        gt = music_t0 + ct
        if gt < end:
            out.append((gt, kind, m, int(v * 0.95)))
            (on.add if kind else on.discard)(m)
    out += [(end, 0, m, 0) for m in on]
    return sorted(out, key=lambda e: (e[0], e[1]))


def render_audio(path):
    sys.path.insert(0, str(ROOT))
    import fluidsynth
    fs = fluidsynth.Synth(samplerate=float(RATE), gain=0.5)
    sf = fs.sfload(str(ROOT / "pianove" / "assets" / "soundfonts" / "SalamanderC5-Light.sf2"))
    fs.program_select(0, sf, 0, 0)
    try:
        fs.set_reverb(roomsize=0.62, damping=0.4, width=0.9, level=0.32)
    except Exception:
        pass
    chunks, pos = [], 0
    for et, kind, m, v in note_events():
        target = int(round(et * RATE))
        if target > pos:
            chunks.append(np.asarray(fs.get_samples(target - pos), dtype=np.int16))
            pos = target
        if kind:
            fs.noteon(0, m, max(1, min(127, v)))
        else:
            fs.noteoff(0, m)
    total = int(round((TOTAL + 0.2) * RATE))
    if total > pos:
        chunks.append(np.asarray(fs.get_samples(total - pos), dtype=np.int16))
    fs.delete()
    audio = np.concatenate(chunks).astype(np.float32).reshape(-1, 2)
    fade = int(3.0 * RATE)                                   # the music fades out over the end card
    audio[-fade:] *= np.linspace(1.0, 0.0, fade)[:, None] ** 1.5
    peak = np.abs(audio).max() or 1.0
    audio *= (10 ** (-1.5 / 20) * 32767) / peak              # to -1.5 dBFS
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(audio.astype(np.int16).tobytes())


def main():
    wav = OUT.with_suffix(".wav")
    render_audio(wav)
    print(f"soundtrack: {wav} ({TOTAL:.1f}s)")
    enc = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error",
         "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
         "-i", str(wav),
         "-c:v", "libx264", "-preset", "slow", "-crf", "16", "-pix_fmt", "yuv420p",
         "-threads", "2", "-x264-params", "rc-lookahead=20",
         "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(OUT)],
        stdin=subprocess.PIPE)
    n = int(round(TOTAL * FPS))
    shot_i = 0
    for k in range(n):
        t = k / FPS
        while shot_i + 1 < len(SHOTS) and t >= SHOTS[shot_i + 1]["t0"]:
            shot_i += 1
            release_clips_before(shot_i)
        enc.stdin.write(frame(t).tobytes())
        if k % 150 == 0:
            print(f"  {k / FPS:5.1f}s / {TOTAL:.1f}s")
    enc.stdin.close()
    enc.wait()
    print(f"wrote {OUT}")


if __name__ == "__main__":
    if len(sys.argv) > 3 and sys.argv[3] == "--frames":     # a few stills to check the look
        for ts in sys.argv[4:]:
            frame(float(ts)).save(OUT.parent / f"frame_{ts}.png")
    else:
        main()
