#!/usr/bin/env bash
# Ждёт результат загрузки: bash youtube/wait.sh <id> [макс_секунд]
# Выходит 0 и печатает результат, когда появился youtube/published/<id>.json; 1 — по таймауту.
cd "$(dirname "$0")/.." || exit 1
id="$1"; max="${2:-600}"; t=0
until [ -f "youtube/published/$id.json" ]; do
  [ "$t" -ge "$max" ] && { echo "timeout: $id"; exit 1; }
  sleep 10; t=$((t + 10)); git pull -q --rebase 2>/dev/null || true
done
cat "youtube/published/$id.json"
