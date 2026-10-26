"""Обрабатывает khabar/requests/<id>.txt, у которых ещё нет khabar/fetched/<id>/_done.json.

Строка запроса: <вид> <имя> <url>
  page — сохранить HTML страницы как <имя>.html
  img  — скачать картинку как <имя>.<ext>
  og   — открыть страницу, взять og:image (или первую крупную картинку) и сохранить как <имя>.<ext>
Пустые строки и строки с # пропускаются.
"""
import json, pathlib, re, time, urllib.request, html

ROOT = pathlib.Path(__file__).resolve().parent
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/129.0 Safari/537.36")


def get(url, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "ru,tg;q=0.9,en;q=0.5"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(), r.headers.get("Content-Type", "")


def ext_for(ctype, url):
    for e in ("jpg", "jpeg", "png", "webp"):
        if e in ctype or url.lower().split("?")[0].endswith("." + e):
            return "jpg" if e == "jpeg" else e
    return "jpg"


def og_image(page_html, base):
    m = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)', page_html) or \
        re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image', page_html)
    if m:
        return urllib.parse.urljoin(base, html.unescape(m.group(1)))
    m = re.search(r'background-image:url\([\'"]?(https://[^\'")]+)', page_html)  # пост Telegram
    return m.group(1) if m else None


import urllib.parse
for req in sorted((ROOT / "requests").glob("*.txt")):
    out = ROOT / "fetched" / req.stem
    if (out / "_done.json").exists():
        continue
    out.mkdir(parents=True, exist_ok=True)
    log = []
    for line in req.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        kind, name, url = line.split(maxsplit=2)
        try:
            if kind == "page":
                body, _ = get(url)
                (out / f"{name}.html").write_bytes(body)
                log.append({"name": name, "ok": True, "file": f"{name}.html", "bytes": len(body)})
            else:
                src = url
                if kind == "og":
                    page, _ = get(url)
                    src = og_image(page.decode("utf-8", "ignore"), url)
                    if not src:
                        raise ValueError("og:image not found")
                body, ctype = get(src)
                f = f"{name}.{ext_for(ctype, src)}"
                (out / f).write_bytes(body)
                log.append({"name": name, "ok": True, "file": f, "src": src, "bytes": len(body)})
        except Exception as e:  # один сбой не должен ронять весь список
            log.append({"name": name, "ok": False, "url": url, "error": str(e)[:200]})
        time.sleep(0.3)
    (out / "_done.json").write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
    print(req.stem, sum(x["ok"] for x in log), "/", len(log))
