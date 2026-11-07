"""«Доброе утро»: собрать data.json из страниц, скачанных Action-ом khabar-fetch.

    python3 dobroe/collect.py khabar/fetched/du-<D> <D> out/data.json

Ожидает в папке: nbt_d.html (НБТ на D), nbt_p.html (НБТ на вчера), meteo.html (meteo.tj/tj/weather-forecast).
Погода берётся из блока, датированного D (не просто первого: на сайте может висеть вчерашний).
Печатает JSON с данными и списком ошибок; код выхода 1, если какая-то проверка не прошла.
"""
import html, json, re, sys, pathlib

src, D, out = pathlib.Path(sys.argv[1]), sys.argv[2], pathlib.Path(sys.argv[3])
errors = []


def nbt(name):
    p = src / f"{name}.html"
    if not p.exists():
        errors.append(f"нет {name}"); return None, {}
    s = p.read_bytes().decode("cp1251", "ignore")
    date = (re.search(r'ValCurs Date="([\d-]+)"', s) or [None, None])[1]
    r = {}
    for code in ("RUB", "USD", "EUR"):
        m = re.search(rf"<CharCode>{code}</CharCode>\s*<Nominal>(\d+)</Nominal>.*?<Value>([\d.,]+)</Value>", s, re.S)
        if m:
            r[code] = round(float(m[2].replace(",", ".")) / int(m[1]), 4)
        else:
            errors.append(f"{name}: нет {code}")
    return date, r


dd, rd = nbt("nbt_d")
dp, rp = nbt("nbt_p")
if dd != D:
    errors.append(f"НБТ: курс на {D} не найден (в файле {dd})")
cur = {}
for code in ("RUB", "USD", "EUR"):
    if code in rd and code in rp:
        if abs(rd[code] - rp[code]) / rp[code] > 0.05:
            errors.append(f"{code}: изменение больше 5% ({rp[code]} → {rd[code]})")
        cur[code.lower()] = {"v": rd[code], "prev": rp[code]}

CITIES = ["Душанбе", "Хуҷанд", "Бохтар", "Хоруғ"]
cities = []
mp = src / "meteo.html"
s = mp.read_text(encoding="utf-8", errors="ignore") if mp.exists() else ""
if not s:
    errors.append("нет meteo.html")
marks = list(re.finditer(r"JSON\.parse\('\\u0022(\d{4}-\d{2}-\d{2})T", s))
blocks = {}
for k, m in enumerate(marks):
    end = marks[k + 1].start() if k + 1 < len(marks) else len(s)
    t = html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s[m.start():end])))
    for c in CITIES:
        if c in t and (m[1], c) not in blocks:
            blocks[(m[1], c)] = t


def icon(txt):
    l = txt.lower()
    if "барф" in l: return "snow"
    if re.search(r"(?<!бе)борон|(?<!бе)борид", l): return "rain"
    if "соф" in l: return "sun"
    if "камабр" in l: return "few"
    if "тағйирёбанда" in l: return "partly"
    if "абрнок" in l or "серабр" in l: return "cloud"
    if "чангу ғубор" in l: return "haze"
    return "partly"


for c in CITIES:
    t = blocks.get((D, c))
    if not t:
        errors.append(f"погода: нет блока на {D} для {c}"); continue
    i = t.find(c)
    # карточка перед названием города: «Шабона + 12... + 14° C <текст> Шамол ... Рӯзона + 23... + 25° C <текст> Шамол»
    head = t[max(0, i - 600):i]
    m = re.search(r"Шабона\s*([+-]?)\s*(\d+)\.\.\.\s*([+-]?)\s*(\d+)°\s*C\s*(.*?)Шамол.*?Рӯзона\s*([+-]?)\s*(\d+)\.\.\.\s*([+-]?)\s*(\d+)°\s*C\s*(.*?)Шамол", head)
    if not m:
        errors.append(f"погода: не разобрал карточку {c}"); continue
    mn = int(m[2]) * (-1 if m[1] == "-" else 1)
    mx = int(m[9]) * (-1 if m[8] == "-" else 1)
    day_txt = m[10].strip().rstrip(",")
    w = [x.strip().rstrip(",") for x in day_txt.split(",") if x.strip()]
    tt = ", ".join([w[0].replace("Ҳавои ", "").capitalize()] + [x.lower() for x in w[1:]]) if w else ""
    if len(tt) > 28: tt = tt[:28].rsplit(" ", 1)[0].rstrip(",")
    if not (-40 <= mn <= 50 and -40 <= mx <= 50 and mn <= mx):
        errors.append(f"погода: странные числа {c} {mn}/{mx}")
    cities.append({"n": c, "mx": mx, "mn": mn, "c": icon(day_txt + " " + m[5]), "t": tt,
                   "raw": t[i:i + 260].strip()})

data = {"date": D, "src": "meteo.tj", "cities": [{k: v for k, v in x.items() if k != "raw"} for x in cities], **cur}
if len(cities) == 4 and len(cur) == 3:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps({"ok": not errors, "errors": errors, "nbt_dates": [dd, dp], "data": data,
                  "raw": {x["n"]: x["raw"] for x in cities}}, ensure_ascii=False, indent=1))
sys.exit(1 if errors else 0)
