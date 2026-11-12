"""Build submission/demo.mp4 + demo.srt from the Playwright recording and Piper wavs.

Pipeline: tts.py -> record.mjs -> build.py
  - trims the head (blank page load) up to the intro scene mark
  - places each narration wav at its scene offset (adelay + amix), loudness-normalises
  - writes an SRT from the same offsets (cues <= 2 lines x ~45 chars)
  - scales 1600x900 -> 1920x1080 @30fps, burns subtitles, H.264 veryfast / yuv420p / AAC
"""
import json
import os
import pathlib
import re
import subprocess
import textwrap

ROOT = pathlib.Path(__file__).resolve().parents[2]
HERE = pathlib.Path(__file__).parent
WORK = pathlib.Path(os.environ.get("VIDEO_WORK", "/tmp/claude-0/video"))
OUT_MP4 = ROOT / "submission" / "demo.mp4"
OUT_SRT = ROOT / "submission" / "demo.srt"
FONTS = pathlib.Path.home() / ".fonts"
MAX_CHARS = 45
MAX_LEN_S = 180.0

tl = json.loads((WORK / "timeline.json").read_text())
durs = json.loads((WORK / "durations.json").read_text())
narr = {s["id"]: s["text"] for s in json.loads((HERE / "narration.json").read_text())}
scenes = tl["scenes"]
head_ms = scenes[0]["start"]
lead_ms = 250  # narration starts slightly after the cut into each scene
total_s = min((tl["total"] - head_ms) / 1000.0, MAX_LEN_S)


def ts(sec: float) -> str:
    ms = int(round(sec * 1000))
    h, ms = divmod(ms, 3600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


# Narration is spelled for the TTS voice; subtitles show the written form.
DISPLAY = [
    (r"\bR B I\b", "RBI"), (r"\bA I\b", "AI"), (r"\bI Ds\b", "IDs"), (r"\bI D\b", "ID"),
    (r"\bE M I\b", "EMI"), (r"Form sixteen", "Form 16"), (r"seventy-nine percent", "79%"),
    (r"sixty percent", "60%"), (r"thirty-seven lakh", "\u20b937 lakh"), (r"twenty twenty-five", "2025"),
    (r"paragraph fifty-eight", "para 58"), (r"\bsix months\b", "6 months"), (r"\beleven steps\b", "11 steps"),
    (r"\bTwelve synthetic\b", "12 synthetic"),
]


def display(text: str) -> str:
    for pat, rep in DISPLAY:
        text = re.sub(pat, rep, text)
    return text


def fits(t: str) -> bool:
    return len(textwrap.wrap(t, MAX_CHARS)) <= 2


def split_balanced(s: str) -> list[str]:
    """Split a sentence into the fewest 2-line cues, preferring breaks after commas/colons
    and avoiding very short cues (dynamic programming over word boundaries)."""
    words = s.split()
    n = len(words)
    best: list[tuple[float, int] | None] = [None] * (n + 1)
    best[0] = (0.0, -1)
    for j in range(1, n + 1):
        for i in range(j - 1, -1, -1):
            piece = " ".join(words[i:j])
            if not fits(piece):
                break
            if best[i] is None:
                continue
            cost = best[i][0] + 100
            if j < n:
                cost += 0 if words[j - 1].endswith((",", ":", ";")) else 35
            if len(piece) < 28:
                cost += 25
            if best[j] is None or cost < best[j][0]:
                best[j] = (cost, i)
    out, j = [], n
    while j > 0:
        i = best[j][1]
        out.append(" ".join(words[i:j]))
        j = i
    return out[::-1]


def cues_for(text: str) -> list[str]:
    """Split narration into subtitle cues of at most two ~45-char lines, breaking at sentences/clauses."""
    sentences = re.split(r"(?<=[.!?])\s+", display(text).strip())
    chunks: list[str] = []
    for s in sentences:
        if chunks and len(chunks[-1]) < 30 and fits(chunks[-1] + " " + s):
            chunks[-1] += " " + s
            continue
        chunks.extend(split_balanced(s))
    return ["\n".join(textwrap.wrap(c, MAX_CHARS)) for c in chunks]


# ---- SRT ----
srt, n, offsets = [], 1, {}
for sc in scenes:
    sid = sc["id"]
    start = (sc["start"] - head_ms + lead_ms) / 1000.0
    offsets[sid] = start
    dur = durs[sid]
    cues = cues_for(narr[sid])
    weights = [len(c) for c in cues]
    t = start
    for c, w in zip(cues, weights):
        d = dur * w / sum(weights)
        srt.append(f"{n}\n{ts(t)} --> {ts(min(t + d, total_s))}\n{c}\n")
        n += 1
        t += d
OUT_SRT.parent.mkdir(parents=True, exist_ok=True)
OUT_SRT.write_text("\n".join(srt), encoding="utf-8")
print("srt cues:", n - 1)

# ---- audio track ----
audio = WORK / "narration.m4a"
inputs, filt = [], []
for i, sc in enumerate(scenes):
    inputs += ["-i", str(WORK / "wav" / f"{sc['id']}.wav")]
    d = int(round(offsets[sc["id"]] * 1000))
    filt.append(f"[{i}:a]aresample=48000,adelay={d}|{d}[a{i}]")
mix = "".join(f"[a{i}]" for i in range(len(scenes)))
filt.append(
    f"{mix}amix=inputs={len(scenes)}:normalize=0:dropout_transition=0,"
    f"apad,atrim=0:{total_s:.3f},loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000[aout]"
)
subprocess.run(
    ["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex", ";".join(filt),
     "-map", "[aout]", "-ac", "2", "-c:a", "aac", "-b:a", "160k", str(audio)],
    check=True,
)

# ---- video ----
style = ("FontName=Plus Jakarta Sans,FontSize=12,PrimaryColour=&H00FFFFFF,OutlineColour=&H80000000,"
         "BackColour=&H80000000,BorderStyle=3,Outline=1,Shadow=0,MarginV=26,Bold=0")
srt_esc = str(OUT_SRT).replace(":", r"\:")
vf = (f"scale=1920:1080:flags=lanczos,fps=30,"
      f"subtitles='{srt_esc}':fontsdir='{FONTS}':force_style='{style}',format=yuv420p")
subprocess.run(
    ["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{head_ms / 1000:.3f}", "-i", tl["video"], "-i", str(audio),
     "-t", f"{total_s:.3f}", "-map", "0:v:0", "-map", "1:a:0", "-vf", vf,
     "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-r", "30",
     "-c:a", "copy", "-movflags", "+faststart", str(OUT_MP4)],
    check=True,
)
(WORK / "offsets.json").write_text(json.dumps(
    {k: {"start": v, "mid": v + durs[k] / 2} for k, v in offsets.items()}, indent=1))
print("wrote", OUT_MP4, f"{total_s:.1f}s")
