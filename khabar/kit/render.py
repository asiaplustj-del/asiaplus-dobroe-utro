"""
Рендер «Хабарҳои шаб» (Азия-Плюс) в MP4 1080×1920, 30 к/с.

    python3 render.py data.json out.mp4

data.json:
  "date":  "2026-10-27"                       — дата выпуска (утро)
  "items": [{"cat","text","img"?}, ...]       — 1-й пункт = главная (5 с крупно), всего до 7;
           cat ∈ muhojirat|hodisa|siyosat|qonun|tandurusti|varzish|iqtisod|jahon|jomea|obuhavo;
           img — путь к картинке относительно data.json (необязательно)
Шрифты — fonts/fonts.css. Музыка — music.(mp3|m4a|wav) рядом, если есть.
Звук: на появление каждого заголовка — тихий «тик» (синтезируется здесь же).
"""
import json, pathlib, subprocess, sys, wave
import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
FPS, SR = 30, 48000
data_path = pathlib.Path(sys.argv[1]).resolve()
data = json.loads(data_path.read_text(encoding="utf-8"))
out = pathlib.Path(sys.argv[2]).resolve()
for it in data["items"]:
    if it.get("img"):
        p = (data_path.parent / it["img"]).resolve()
        it["img"] = p.as_uri() if p.exists() else ""
music = next((HERE / f"music.{e}" for e in ("mp3", "m4a", "wav") if (HERE / f"music.{e}").exists()), None)
video = out.with_name(out.stem + "_silent.mp4")

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1080, "height": 1920}, device_scale_factor=1)
    pg.goto((HERE / "index.html").as_uri() + "?render")
    pg.evaluate("Promise.all(['700 40px Brand','500 20px Text','600 20px Text','700 20px Text'].map(f=>document.fonts.load(f,'Аa1ҳҷқғӯӣ$'))).then(()=>document.fonts.ready)")
    info = pg.evaluate("d => window.renderSetup(d)", data)
    DUR = info["dur"]
    print("компоновка:", info, flush=True)
    ff = subprocess.Popen([
        "ffmpeg", "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(FPS), "-i", "-",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "17", "-pix_fmt", "yuv420p",
        "-movflags", "+faststart", str(video)], stdin=subprocess.PIPE)
    stage = pg.locator("#stage")
    for i in range(FPS * DUR):
        pg.evaluate(f"window.seek({i / FPS})")
        ff.stdin.write(stage.screenshot(type="png", animations="allow"))
        if i % 90 == 0:
            print(f"кадр {i}/{FPS * DUR}", flush=True)
    b.close()
    ff.stdin.close(); ff.wait()


# ---- звук: мягкий «стеклянный» тик (два обертона + еле слышный щелчок), без резкой атаки ----
def tick(freq):
    n = int(SR * 0.35); t = np.arange(n) / SR
    env = (1 - np.exp(-t / 0.002)) * np.exp(-t / 0.055)
    tone = np.sin(2 * np.pi * freq * t) + 0.35 * np.sin(2 * np.pi * freq * 1.5 * t) + 0.12 * np.sin(2 * np.pi * freq * 2.76 * t)
    click = np.random.default_rng(1).standard_normal(n) * np.exp(-t / 0.0015) * 0.15
    return (tone * env + click) * 0.22

track = np.zeros(int(SR * DUR))
for k, c in enumerate(info["cues"]):
    s = tick(1568 if k == 0 else 2093)        # главная — чуть ниже (G6), пункты — C7
    i = int(c * SR); track[i:i + len(s)] += s[:len(track) - i]
sfx = out.with_name(out.stem + "_sfx.wav")
with wave.open(str(sfx), "wb") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((np.clip(track, -1, 1) * 32767).astype(np.int16).tobytes())

if music:
    inputs = ["-i", str(video), "-stream_loop", "-1", "-i", str(music), "-i", str(sfx)]
    fc = (f"[1:a]atrim=0:{DUR},afade=t=in:d=0.6,afade=t=out:st={DUR - 1.5}:d=1.5,volume=0.85[m];"
          f"[2:a]aformat=channel_layouts=stereo[s];[m][s]amix=inputs=2:normalize=0[a]")
else:
    inputs = ["-i", str(video), "-i", str(sfx)]
    fc = "[1:a]aformat=channel_layouts=stereo[a]"
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex", fc, "-map", "0:v", "-map", "[a]",
                "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-t", str(DUR), "-movflags", "+faststart", str(out)], check=True)
video.unlink(); sfx.unlink()
print("Готово:", out, f"{DUR} с", "(музыка + тики)" if music else "(только тики)")
