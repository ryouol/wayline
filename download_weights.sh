#!/bin/bash
# Resumable download of LingBot-Map weights. Survives network drops:
# curl -C - resumes from the partial file, and the loop retries until complete.
set -u
cd "$(dirname "$0")"

fetch() {
  local name="$1" expected="$2"
  local url="https://huggingface.co/robbyant/lingbot-map/resolve/main/${name}"
  for attempt in $(seq 1 200); do
    if [ -f "$name" ]; then
      local have
      have=$(stat -f%z "$name" 2>/dev/null || echo 0)
      if [ "$have" -eq "$expected" ]; then
        echo "DONE $name ($have bytes)"
        return 0
      fi
    fi
    curl -sSL --retry 5 --retry-delay 5 --retry-all-errors \
         --connect-timeout 30 --speed-limit 1024 --speed-time 120 \
         -C - -o "$name" "$url" 2>/dev/null
    sleep 3
  done
  echo "FAILED $name after 200 attempts"
  return 1
}

fetch "lingbot-map.pt" 4632303465 || exit 1
fetch "skyseg_batch.onnx" 175997119 || exit 1
echo "ALL DOWNLOADS COMPLETE"
