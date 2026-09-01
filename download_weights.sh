#!/usr/bin/env bash
# Pinned, resumable research-asset download with exact SHA-256 verification.
set -euo pipefail

cd "$(dirname "$0")"

readonly REQUIRED_ACK="I understand LingBot is research-only"
if [[ "${LINGBOT_RESEARCH_ACK:-}" != "$REQUIRED_ACK" ]]; then
  echo "LingBot checkpoint and training-data commercial rights are unresolved." >&2
  echo "This downloader is available only for research evaluation." >&2
  echo "Set LINGBOT_RESEARCH_ACK='$REQUIRED_ACK' to continue." >&2
  exit 2
fi

readonly MODEL_REPOSITORY="robbyant/lingbot-map"
readonly MODEL_REVISION="204754b72bb24f561f8d7e7e1e4e4cd9e809adf9"

sha256() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | awk '{print $1}'
  else
    shasum -a 256 "$1" | awk '{print $1}'
  fi
}

fetch() {
  local name="$1" expected_bytes="$2" expected_sha="$3"
  local url="https://huggingface.co/${MODEL_REPOSITORY}/resolve/${MODEL_REVISION}/${name}"
  local partial="${name}.part"

  if [[ -f "$name" ]] && [[ "$(sha256 "$name")" == "$expected_sha" ]]; then
    printf '%s  %s\n' "$expected_sha" "$name" >"${name}.sha256"
    echo "verified $name"
    return 0
  fi

  curl --fail --location --retry 10 --retry-delay 3 --retry-all-errors \
    --connect-timeout 30 --speed-limit 1024 --speed-time 120 \
    --continue-at - --output "$partial" "$url"

  local actual_bytes actual_sha
  actual_bytes=$(wc -c <"$partial" | tr -d ' ')
  actual_sha=$(sha256 "$partial")
  if [[ "$actual_bytes" != "$expected_bytes" ]] || [[ "$actual_sha" != "$expected_sha" ]]; then
    echo "integrity check failed for $name" >&2
    echo "expected $expected_bytes bytes / $expected_sha" >&2
    echo "received $actual_bytes bytes / $actual_sha" >&2
    exit 1
  fi
  chmod 600 "$partial"
  mv "$partial" "$name"
  printf '%s  %s\n' "$expected_sha" "$name" >"${name}.sha256"
  echo "downloaded and verified $name"
}

fetch "lingbot-map.pt" 4632303465 "ee665103348e07e6b826d529b8e61de8f413d5432a4f2e84970d6c8fd2e1cd72"
fetch "skyseg_batch.onnx" 175997119 "b09c0f6cf79e1caa2591b946b659487bd7c8208caddd3f80680cbb169617e378"

echo "Research assets verified at pinned model revision $MODEL_REVISION."
