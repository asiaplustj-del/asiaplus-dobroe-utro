#!/usr/bin/env bash
# «Доброе утро»: скачать курс НБТ и прогноз meteo.tj через GitHub Action khabar-fetch и собрать data.json.
#   bash dobroe/fetch.sh <D YYYY-MM-DD> <out/data.json>
# Среда Claude эти сайты сама не открывает (WebFetch ждёт разрешения) — их скачивает Action.
set -u
cd "$(dirname "$0")/.." || exit 1
D="$1"; OUT="$2"; P=$(date -d "$D -1 day" +%F); ID="du-$D"
if [ ! -f "khabar/fetched/$ID/_done.json" ]; then
  [ -f "khabar/fetched/$ID/_done.json" ] || rm -rf "khabar/fetched/$ID"
  cat > "khabar/requests/$ID.txt" <<R
# «Доброе утро» $D: курс НБТ (сегодня, вчера) и прогноз meteo.tj
page nbt_d https://nbt.tj/ru/kurs/export_xml.php?date=$D&export=xmlout
page nbt_p https://nbt.tj/ru/kurs/export_xml.php?date=$P&export=xmlout
page meteo https://www.meteo.tj/tj/weather-forecast
R
  git add "khabar/requests/$ID.txt"
  git commit -qm "dobroe-utro: данные $D" || true
  for i in 1 2 3; do git pull -q --rebase && git push -q && break; sleep 3; done
  bash khabar/wait.sh "$ID" 420 || exit 2
fi
cat "khabar/fetched/$ID/_done.json"
python3 -I dobroe/collect.py "khabar/fetched/$ID" "$D" "$OUT"
