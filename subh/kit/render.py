"""
Рендер объединённой утренней рубрики (Азия-Плюс, Shorts 1080×1920, ~38 с):
«Хабарҳои шаби гузашта» (0–22 с) → рассвет (22–23,5 с) → «Обу ҳаво / қурби асъор» (до конца).
    python3 render.py news.json weather.json out.mp4
news.json   — {"date","items":[{"cat","text","img"}],"sources"} (как у «Хабарҳои шаб»; img относительно news.json)
weather.json — data.json от dobroe/collect.py ({"date","src","cities","rub","usd","eur"} с v/prev)
Рядом: fonts/ (fonts.css + Nunito из khabar/kit/fonts + SF Pro из закрытого артефакта), music.mp3 (трек «Хабарҳои шаб»).
Звук: музыка новостей на весь ролик, тики на заголовках; на экране погоды — те же два тика под блоками погоды и курса.
"""
import json, pathlib, subprocess, sys, wave, datetime
import numpy as np
from playwright.sync_api import sync_playwright

HERE = pathlib.Path(__file__).resolve().parent
FPS, SR = 30, 48000
news_p, wx_p, out = (pathlib.Path(a).resolve() for a in sys.argv[1:4])
news = json.loads(news_p.read_text(encoding="utf-8"))
for it in news["items"]:
    if it.get("img"):
        p = (news_p.parent / it["img"]).resolve()
        it["img"] = p.as_uri() if p.exists() else ""
wx = json.loads(wx_p.read_text(encoding="utf-8"))
for k in ("rub", "usd", "eur"):
    wx[k]["c"] = round(wx[k]["v"] - wx[k]["prev"], 4)
tmp = out.parent / "_parts"; tmp.mkdir(exist_ok=True)
FONTS = "Promise.all(['700 40px Brand','500 20px Text','600 20px Text','700 20px Text'].map(f=>document.fonts.load(f,'Аa1ҳҷқғӯӣ$₽€'))).then(()=>document.fonts.ready)"


def part(pg, page, data, name):
    pg.goto((HERE / page).as_uri() + "?render")
    pg.evaluate(FONTS)
    info = pg.evaluate("d => window.renderSetup(d)", data)
    dur = info["dur"]; mp4 = tmp / f"{name}.mp4"
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(FPS), "-i", "-",
                           "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-pix_fmt", "yuv420p", str(mp4)],
                          stdin=subprocess.PIPE)
    st = pg.locator("#stage")
    for i in range(round(FPS * dur)):
        pg.evaluate(f"window.seek({i / FPS})")
        ff.stdin.write(st.screenshot(type="png", animations="allow"))
    ff.stdin.close(); ff.wait()
    print(name, info, flush=True)
    return info


with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1080, "height": 1920}, device_scale_factor=1)
    ni = part(pg, "khabar.html", news, "news")
    di = part(pg, "dawn.html", {}, "dawn")
    wx["ts"] = ni["ts"]
    wi = part(pg, "weather.html", wx, "weather")
    b.close()

X1, X2 = 0.5, 0.35   # новости длятся 22.5 с → переход начинается ровно на 22-й секунде                       # склейки: новости→рассвет, рассвет→погода
o1 = ni["dur"] - X1
o2 = o1 + di["dur"] - X2
TOTAL = o2 + wi["dur"]
silent = tmp / "silent.mp4"
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(tmp / "news.mp4"), "-i", str(tmp / "dawn.mp4"), "-i", str(tmp / "weather.mp4"),
                "-filter_complex", f"[0:v][1:v]xfade=transition=fade:duration={X1}:offset={o1:.3f}[a];[a][2:v]xfade=transition=fade:duration={X2}:offset={o2:.3f}[v]",
                "-map", "[v]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-pix_fmt", "yuv420p", str(silent)], check=True)


# ---------- звук ----------
from scipy.signal import fftconvolve, butter, sosfilt
rng = np.random.default_rng(7)
def hz(n): return 440 * 2 ** ((n - 69) / 12)
def env(t, a, d): return (1 - np.exp(-t / a)) * np.exp(-t / d)
def lp(x, f): return sosfilt(butter(2, f, "low", fs=SR, output="sos"), x)
def bp(x, lo, hi): return sosfilt(butter(2, [lo, hi], "band", fs=SR, output="sos"), x)

# тики новостей — как были
def tick(freq):
    n = int(SR * 0.35); t = np.arange(n) / SR
    e = (1 - np.exp(-t / 0.002)) * np.exp(-t / 0.055)
    tone = np.sin(2 * np.pi * freq * t) + 0.35 * np.sin(2 * np.pi * freq * 1.5 * t) + 0.12 * np.sin(2 * np.pi * freq * 2.76 * t)
    click = np.random.default_rng(1).standard_normal(n) * np.exp(-t / 0.0015) * 0.15
    return (tone * e + click) * 0.22

# «стекло»: FM-колокольчик + мягкое тело октавой ниже (тональность трека — ре)
def glass(note, dur=1.6, amp=0.16):
    t = np.arange(int(SR * dur)) / SR; f = hz(note)
    idx = 2.2 * np.exp(-t / 0.18)
    bell = np.sin(2 * np.pi * f * t + idx * np.sin(2 * np.pi * f * 3.5 * t)) * env(t, .003, .55)
    body = np.sin(2 * np.pi * f / 2 * t) * env(t, .004, .22) * .7
    air = lp(rng.standard_normal(len(t)), 6000) * env(t, .001, .012) * .08
    return lp(bell + body + air, 7000) * amp

# «раскрытие» заголовка: низкий мягкий аккорд D-A-D с медленной атакой
def bloom(dur=2.6, amp=0.11):
    t = np.arange(int(SR * dur)) / SR; s = np.zeros_like(t)
    for n, g in ((38, 1.0), (45, .6), (50, .45), (57, .25)):
        for det in (-.12, .12):
            s += g * np.sin(2 * np.pi * hz(n + det) * t)
    return lp(s * env(t, .09, .9), 1800) * amp

# «воздух» рассвета: шум, раскрывающийся фильтром, + суббас
def swell(dur=1.9, amp=0.07):
    t = np.arange(int(SR * dur)) / SR; k = t / dur
    nz = rng.standard_normal(len(t)); out = np.zeros_like(t); seg = SR // 20
    for i in range(0, len(t), seg):
        lo = 200 + 2600 * k[i] ** 1.5; out[i:i + seg] = bp(nz[i:i + seg + 2000], lo, lo * 2.2)[:len(out[i:i + seg])]
    e = np.sin(np.pi * np.clip(k, 0, 1)) ** 1.6
    sub = np.sin(2 * np.pi * hz(26) * t) * np.clip((k - .35) / .4, 0, 1) * np.exp(-np.clip(k - .75, 0, 1) * 6)
    return (out * e * .6 + sub * .5) * amp

L = int(SR * TOTAL); dry = np.zeros((L, 2)); wetsend = np.zeros((L, 2))
def put(sig, at, pan=0.0, wet=0.35):
    i = int(at * SR); j = min(L, i + len(sig)); s = sig[:j - i]
    gl, gr = np.cos((pan + 1) * np.pi / 4), np.sin((pan + 1) * np.pi / 4)
    dry[i:j, 0] += s * gl; dry[i:j, 1] += s * gr
    wetsend[i:j, 0] += s * gl * wet; wetsend[i:j, 1] += s * gr * wet

for k, c in enumerate(ni["cues"]):
    put(tick(1568 if k == 0 else 2093), c, 0, 0)
W0 = o2                                   # начало экрана погоды
put(tick(1568), W0 + 0.97, 0, 0)          # появление блока погоды — тот же звук, что у главной новости
put(tick(2093), W0 + 1.90, 0, 0)          # появление блока курса — тот же звук, что у пунктов списка

# реверберация: стерео-импульс 2,4 с
n = int(SR * 2.4); t = np.arange(n) / SR
ir = np.stack([lp(rng.standard_normal(n), 5000) * np.exp(-t / .55) for _ in range(2)], 1); ir /= np.abs(ir).sum(0) ** .5 * 6
wet = np.stack([fftconvolve(wetsend[:, c], ir[:, c])[:L] for c in range(2)], 1)
mix = np.clip(dry + wet, -1, 1)
sfx = tmp / "sfx.wav"
with wave.open(str(sfx), "wb") as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((mix * 32767).astype(np.int16).tobytes())

# музыка: трек короче ролика — склеиваем сам с собой через кроссфейд 2 с
mus = HERE / "music.mp3"
fc = (f"[1:a]silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.02[m1];"
      f"[2:a]silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.02[m2];"
      f"[m1][m2]acrossfade=d=2[mm];[mm]atrim=0:{TOTAL:.3f},afade=t=in:d=0.15,afade=t=out:st={TOTAL - 1.8:.3f}:d=1.8,volume=0.85[m];"
      f"[3:a]anull[s];[m][s]amix=inputs=2:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=11[a]")
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(silent), "-i", str(mus), "-i", str(mus), "-i", str(sfx),
                "-filter_complex", fc, "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                "-t", f"{TOTAL:.3f}", "-movflags", "+faststart", str(out)], check=True)
print(json.dumps({"total": round(TOTAL, 2), "news_end": round(o1, 2), "weather_start": round(o2, 2)}))
