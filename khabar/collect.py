"""Собирает «кандидатов» для «Хабарҳои шаб» из скачанных лент (khabar/fetched/<id>/).

    python3 khabar/collect.py khabar/fetched/<id> --since "2026-10-26 18:00" [--until "2026-10-27 06:30"]

Время — Душанбе (UTC+5). Понимает RSS/Atom (*.xml/*-rss/*-feed) и превью Telegram (tg-*.html).
Печатает список, отсортированный по времени, и пишет candidates.json рядом с лентами:
  [{"src","t","title","url","img","text"}]
"""
import argparse, datetime as dt, email.utils, html, json, pathlib, re

TZ = dt.timezone(dt.timedelta(hours=5))
ap = argparse.ArgumentParser()
ap.add_argument("dir"); ap.add_argument("--since", required=True); ap.add_argument("--until")
a = ap.parse_args()
D = pathlib.Path(a.dir)
since = dt.datetime.fromisoformat(a.since).replace(tzinfo=TZ)
until = dt.datetime.fromisoformat(a.until).replace(tzinfo=TZ) if a.until else dt.datetime.now(TZ)


def clean(s):
    s = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", s or "", flags=re.S)
    s = re.sub(r"<br\s*/?>", " ", s); s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def rss(name, x):
    out = []
    for it in re.findall(r"<item\b.*?</item>", x, flags=re.S):
        g = lambda tag: (re.search(rf"<{tag}\b[^>]*>(.*?)</{tag}>", it, flags=re.S) or [None, ""])[1]
        try:
            t = email.utils.parsedate_to_datetime(clean(g("pubDate"))).astimezone(TZ)
        except Exception:
            continue
        img = re.search(r'<(?:enclosure|media:content|media:thumbnail)[^>]+url="([^"]+)"', it)
        out.append({"src": name, "t": t, "title": clean(g("title")), "url": clean(g("link")),
                    "img": img.group(1) if img else "", "text": clean(g("description"))[:300]})
    return out


def telegram(name, x):
    out = []
    for blk in re.split(r'<div class="tgme_widget_message_wrap', x)[1:]:
        post = re.search(r'data-post="([^"]+)"', blk)
        tm = re.search(r'datetime="([^"]+)"', blk)
        if not (post and tm):
            continue
        txt = re.search(r'<div class="tgme_widget_message_text[^>]*>(.*?)</div>', blk, flags=re.S)
        img = re.search(r"tgme_widget_message_photo_wrap[^>]+background-image:url\('([^']+)'\)", blk)
        body = clean(txt.group(1)) if txt else ""
        out.append({"src": name, "t": dt.datetime.fromisoformat(tm.group(1)).astimezone(TZ),
                    "title": body[:160], "url": "https://t.me/" + post.group(1),
                    "img": img.group(1) if img else "", "text": body[:400]})
    return out


items = []
for f in sorted(D.iterdir()):
    if f.suffix not in (".html", ".xml") or f.name.startswith("_"):
        continue
    x = f.read_text(encoding="utf-8", errors="ignore")
    if f.stem.startswith("tg-"):
        items += telegram(f.stem, x)
    elif "<item" in x:
        items += rss(f.stem, x)

items = [i for i in items if since <= i["t"] <= until and i["title"]]
items.sort(key=lambda i: i["t"])
for i in items:
    print(f'{i["t"]:%d.%m %H:%M} [{i["src"]}] {i["title"][:140]}\n      {i["url"]}' + (f'\n      img: {i["img"]}' if i["img"] else ""))
print(f"\nВсего кандидатов: {len(items)} ({since:%d.%m %H:%M} – {until:%d.%m %H:%M})")
(D / "candidates.json").write_text(json.dumps([{**i, "t": i["t"].isoformat()} for i in items], ensure_ascii=False, indent=1), encoding="utf-8")
