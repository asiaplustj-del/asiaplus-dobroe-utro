"""Загрузка заявок youtube/requests/*.json на YouTube (запускается в GitHub Actions).

Заявка:
{
  "video": "videos/2026-11-07.mp4",
  "title": "...", "description": "...", "tags": ["..."],
  "privacy": "public" | "unlisted" | "private",
  "categoryId": "25"
}
Результат: youtube/published/<id>.json  {"ok": true, "id": "...", "url": "...", "privacy": "..."}
                                    или {"ok": false, "error": "..."}
Заявка, для которой уже есть результат, повторно не загружается.
"""
import json, os, pathlib, sys, datetime

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

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

failed = False
for p in pending:
    rid = p.stem
    try:
        r = json.loads(p.read_text(encoding="utf-8"))
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
        media = MediaFileUpload(str(video), mimetype="video/mp4", chunksize=8 * 1024 * 1024, resumable=True)
        req = yt.videos().insert(part="snippet,status", body=body, media_body=media, notifySubscribers=True)
        resp = None
        while resp is None:
            _, resp = req.next_chunk()
        vid = resp["id"]
        write(rid, {"ok": True, "id": vid, "url": f"https://youtube.com/shorts/{vid}",
                    "privacy": resp.get("status", {}).get("privacyStatus")})
    except Exception as e:
        failed = True
        write(rid, {"ok": False, "error": f"{type(e).__name__}: {e}"[:2000]})

sys.exit(1 if failed else 0)
