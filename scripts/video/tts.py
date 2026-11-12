"""Generate one Piper wav per narration segment and write durations.json."""
import json, subprocess, sys, wave, pathlib, os
HERE = pathlib.Path(__file__).parent
OUT = pathlib.Path(os.environ.get("VIDEO_WORK", "/tmp/claude-0/video")) / "wav"
VOICE = os.environ.get("PIPER_VOICE", "/tmp/claude-0/voices/en_US-lessac-medium.onnx")
OUT.mkdir(parents=True, exist_ok=True)
segs = json.loads((HERE / "narration.json").read_text())
durs = {}
for s in segs:
    wav = OUT / f"{s['id']}.wav"
    subprocess.run([sys.executable, "-m", "piper", "-m", VOICE, "--length-scale", "0.95", "-f", str(wav)],
                   input=s["text"].encode(), check=True, capture_output=True)
    with wave.open(str(wav)) as w:
        durs[s["id"]] = round(w.getnframes() / w.getframerate(), 3)
    print(s["id"], durs[s["id"]])
(OUT.parent / "durations.json").write_text(json.dumps(durs, indent=1))
print("total", round(sum(durs.values()), 2))
