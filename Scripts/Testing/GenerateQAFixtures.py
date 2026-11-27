"""Generate NEXTRON-QA-001 from self-authored patterns and FFmpeg sources."""
import hashlib
import json
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2] / "Tests" / "QA-Audit" / "NEXTRON-QA-001"
ROOT.mkdir(parents=True, exist_ok=True)

def ff(*args):
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *map(str, args)], check=True, timeout=180)

im = Image.new("RGB", (1280, 720))
d = ImageDraw.Draw(im)
for y in range(720):
    d.line((0, y, 1279, y), fill=(y % 256, (y * 2) % 256, 80))
d.rectangle((320, 210, 900, 510), outline="white", width=5)
d.text((350, 240), "NEXTRON QA 001 - ORIGINAL", fill="white")
im.save(ROOT / "IMG-01.jpg", quality=95, exif=Image.Exif())
edit = im.copy(); de = ImageDraw.Draw(edit)
de.rectangle((500, 300, 780, 470), fill=(255, 30, 30))
de.text((515, 320), "LOCAL EDIT", fill="white")
edit.save(ROOT / "IMG-02.jpg", quality=95)
im.resize((640, 360)).save(ROOT / "IMG-03.jpg", quality=45)
Image.new("RGB", (1280, 720), (17, 150, 70)).save(ROOT / "IMG-04.png")
ff("-f", "lavfi", "-i", "testsrc2=size=320x180:rate=24", "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000", "-t", "12", "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", ROOT / "VID-01.mp4")
ff("-i", ROOT / "VID-01.mp4", "-vf", "scale=240:136", "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", ROOT / "VID-02.mp4")
ff("-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000", "-t", "10", ROOT / "base.wav")
ff("-f", "lavfi", "-i", "sine=frequency=880:sample_rate=48000", "-t", "10", ROOT / "tone.wav")
ff("-f", "lavfi", "-i", "color=c=purple:size=320x180:rate=24", "-t", "12", "-c:v", "libx264", "-preset", "ultrafast", ROOT / "VID-04.mp4")
ff("-i", ROOT / "VID-01.mp4", "-an", "-c:v", "copy", ROOT / "VID-05.mp4")
ff("-i", ROOT / "VID-01.mp4", "-vn", "-c:a", "pcm_s16le", ROOT / "AUD-01.wav")
ff("-f", "lavfi", "-i", "sine=frequency=880:sample_rate=48000", "-t", "3", ROOT / "splice.wav")
ff("-i", ROOT / "AUD-01.wav", "-i", ROOT / "splice.wav", "-filter_complex", "[0:a]atrim=0:4,asetpts=PTS-STARTPTS[a];[1:a]asetpts=PTS-STARTPTS[b];[0:a]atrim=7:12,asetpts=PTS-STARTPTS[c];[a][b][c]concat=n=3:v=0:a=1[o]", "-map", "[o]", ROOT / "AUD-02.wav")
ff("-ss", "2", "-i", ROOT / "VID-01.mp4", "-i", ROOT / "AUD-02.wav", "-map", "0:v", "-map", "1:a", "-t", "10", "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", ROOT / "VID-03.mp4")
ff("-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono", "-t", "12", ROOT / "AUD-03.wav")
ff("-f", "lavfi", "-i", "sine=frequency=1300:sample_rate=48000", "-t", "12", ROOT / "AUD-04.wav")
(ROOT / "NEG-01.jpg").write_bytes(b"\xff\xd8\xff\xe0corrupt")
(ROOT / "NEG-02.jpg").write_text("plain text with a misleading extension", encoding="utf-8")
manifest = {"dataset": "NEXTRON-QA-001", "generation": "Self-generated patterns and FFmpeg lavfi; no external source calls", "fixtures": []}
for path in sorted(ROOT.glob("*")):
    if path.suffix not in {".jpg", ".png", ".mp4", ".wav"}: continue
    manifest["fixtures"].append({"id": path.stem, "filename": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "size_bytes": path.stat().st_size, "ground_truth": {"IMG-02": "local rectangle x500:780 y300:470", "IMG-03": "resized 640x360 JPEG quality45", "VID-02": "resized 240x136 and reencoded", "VID-03": "first two seconds trimmed; audio replacement intended at derived 4-7s", "AUD-02": "440Hz replaced by 880Hz at 4-7s"}.get(path.stem, "original, unrelated, silent, or negative as named"), "license": "self-generated"})
(ROOT / "Fixture-Manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
print(json.dumps({"count": len(manifest["fixtures"]), "root": str(ROOT)}))
