"""Разовая авторизация канала для автозагрузки (запускать на своём компьютере).

    python3 auth.py ~/Downloads/client_secret_XXXX.json

Откроется браузер: войдите в Google-аккаунт, который управляет каналом, и разрешите
загрузку видео. Скрипт выведет ключ и (на Mac) скопирует его в буфер обмена —
вставьте его в GitHub: Settings → Secrets and variables → Actions → New repository secret,
имя YOUTUBE_TOKEN.
"""
import sys, subprocess
from google_auth_oauthlib.flow import InstalledAppFlow

if len(sys.argv) < 2:
    sys.exit("Укажите путь к client_secret_....json")
flow = InstalledAppFlow.from_client_secrets_file(sys.argv[1], ["https://www.googleapis.com/auth/youtube.upload"])
creds = flow.run_local_server(port=0, prompt="consent", access_type="offline")
if not creds.refresh_token:
    sys.exit("Google не выдал refresh_token. Удалите доступ на myaccount.google.com/permissions и запустите снова.")
token = creds.to_json()
try:
    subprocess.run(["pbcopy"], input=token.encode(), check=True)
    print("\n✅ Готово. Ключ скопирован в буфер обмена — вставьте его в секрет YOUTUBE_TOKEN на GitHub.\n")
except Exception:
    print("\n✅ Готово. Скопируйте строку ниже целиком в секрет YOUTUBE_TOKEN на GitHub:\n")
    print(token)
