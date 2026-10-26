#!/usr/bin/env bash
# Ждёт, пока GitHub Action обработает запрос: bash khabar/wait.sh <id> [макс_секунд]
# Выходит 0, когда появился khabar/fetched/<id>/_done.json; 1 — по таймауту.
cd "$(dirname "$0")/.." || exit 1
id="$1"; max="${2:-420}"; t=0
until [ -f "khabar/fetched/$id/_done.json" ]; do
  [ "$t" -ge "$max" ] && { echo "timeout: $id"; exit 1; }
  sleep 10; t=$((t + 10)); git pull -q --rebase 2>/dev/null || true
done
echo "done: $id after ${t}s"
