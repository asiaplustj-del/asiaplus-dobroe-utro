"""Загрузка заявок youtube/requests/*.json на YouTube (запускается в GitHub Actions).

Заявка:
{
  "video": "videos/2026-11-07.mp4",
  "title": "...", "description": "...", "tags": ["..."],
  "privacy": "public" | "unlisted" | "private",
  "categoryId": "25",
  "publishAt": "2026-11-07T07:00:00+05:00",  (необязательно: отложенная публикация)
  "thumbnail": "subh/videos/2026-11-21.jpg"   (необязательно: своя обложка, JPEG/PNG до 2 МБ)
}
Обложку ставим после обработки ролика и дважды (иначе YouTube перебивает её автокадром).
Только обложка для уже загруженного ролика: {"videoId": "...", "thumbnail": "путь"}.
Ошибка обложки ролик не отменяет: в результате поле "thumbnail": "ok" или текст ошибки.
Результат: youtube/published/<id>.json  {"ok": true, "id": "...", "url": "...", "privacy": "..."}
                                    или {"ok": false, "error": "..."}
Заявка, для которой уже есть результат, повторно не загружается.
"""
import json, os, pathlib, sys, datetime, time

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError

ROOT = pathlib.Path(__file__).resolve().parent.parent
REQ = ROOT / "youtube" / "requests"
OUT = ROOT / "youtube" / "published"
OUT.mkdir(parents=True, exist_ok=True)
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def write(rid, data):
    data["at"] = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    (OUT / f"{rid}.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(rid, data)


pending = [p for p in sorted(REQ.glob("*.json")) if not (OUT / p.name).exists()]
if not pending:
    print("Нет новых заявок.")
    sys.exit(0)

token = os.environ.get("YOUTUBE_TOKEN", "").strip()
if not token:
    for p in pending:
        write(p.stem, {"ok": False, "error": "Секрет YOUTUBE_TOKEN не задан в репозитории"})
    sys.exit(1)

creds = Credentials.from_authorized_user_info(json.loads(token), SCOPES)
if not creds.valid:
    creds.refresh(Request())
yt = build("youtube", "v3", credentials=creds, cache_discovery=False)

def processed(vid):
    """True/False — статус обработки; None — узнать нельзя (не хватает прав ключа)."""
    try:
        it = yt.videos().list(part="processingDetails", id=vid).execute().get("items", [])
        if not it:
            return None
        return it[0].get("processingDetails", {}).get("processingStatus") == "succeeded"
    except Exception:
        return None


def set_once(vid, img):
    mime = "image/png" if img.suffix.lower() == ".png" else "image/jpeg"
    yt.thumbnails().set(videoId=vid, media_body=MediaFileUpload(str(img), mimetype=mime)).execute()


def set_thumb(vid, img, fresh=True):
    """Обложку, поставленную до окончания обработки, YouTube перебивает автокадром (21.11.2026).
    Поэтому: ждём статус succeeded (если ключ позволяет) или 4 мин, ставим, и через 4 мин ставим ещё раз."""
    if not img.exists():
        return f"нет файла {img.name}"
    if fresh:
        t0 = time.time()
        while time.time() - t0 < 420:
            st = processed(vid)
            if st is True:
                break
            if st is None and time.time() - t0 >= 240:
                break
            time.sleep(20)
    errs, ok = [], 0
    for attempt in range(2 if fresh else 1):
        for _ in range(6):
            try:
                set_once(vid, img); ok += 1; break
            except Exception as e:
                errs.append(f"{type(e).__name__}: {e}"[:300]); time.sleep(20)
        if fresh and attempt == 0:
            time.sleep(240)
    return "ok" if ok else "; ".join(errs[-2:])


failed = False
for p in pending:
    rid = p.stem
    try:
        r = json.loads(p.read_text(encoding="utf-8"))
        if r.get("videoId"):            # только обложка для уже загруженного ролика
            res = set_thumb(r["videoId"], ROOT / r["thumbnail"], fresh=False)
            write(rid, {"ok": res == "ok", "id": r["videoId"], "thumbnail": res})
            failed = failed or res != "ok"
            continue
        video = ROOT / r["video"]
        if not video.exists():
            raise FileNotFoundError(f"нет файла {r['video']}")
        body = {
            "snippet": {
                "title": r["title"][:100],
                "description": r.get("description", ""),
                "tags": r.get("tags", []),
                "categoryId": str(r.get("categoryId", "25")),
                "defaultLanguage": r.get("language", "tg"),
            },
            "status": {"privacyStatus": r.get("privacy", "public"), "selfDeclaredMadeForKids": False},
        }
        # Отложенная публикация: "publishAt": "2026-11-07T07:00:00+05:00".
        # YouTube требует privacy=private; в указанное время ролик сам станет публичным.
        # Если время уже прошло (или до него < 2 мин) — публикуем сразу.
        pa = r.get("publishAt")
        if pa:
            t = datetime.datetime.fromisoformat(pa)
            now = datetime.datetime.now(datetime.timezone.utc)
            if t - now > datetime.timedelta(minutes=2):
                body["status"]["privacyStatus"] = "private"
                body["status"]["publishAt"] = t.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        media = MediaFileUpload(str(video), mimetype="video/mp4", chunksize=8 * 1024 * 1024, resumable=True)
        req = yt.videos().insert(part="snippet,status", body=body, media_body=media, notifySubscribers=True)
        resp = None
        while resp is None:
            _, resp = req.next_chunk()
        vid = resp["id"]
        st = resp.get("status", {})
        res = {"ok": True, "id": vid, "url": f"https://youtube.com/shorts/{vid}",
               "privacy": st.get("privacyStatus"), "publishAt": st.get("publishAt")}
        if r.get("thumbnail"):
            res["thumbnail"] = set_thumb(vid, ROOT / r["thumbnail"])
        write(rid, res)
    except Exception as e:
        failed = True
        write(rid, {"ok": False, "error": f"{type(e).__name__}: {e}"[:2000]})

sys.exit(1 if failed else 0)
