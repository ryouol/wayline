#!/usr/bin/env bash
set -euo pipefail

# Export delivery formats from the approved artwork and actual viewer captures.
# This is an offline ImageMagick 7 task; the application needs no image tool.
cd "$(dirname "$0")/../lingbot_map/workspace/static"
for size in 16 32 180 192 512; do
  case "$size" in
    16|32) output="favicon-${size}.png" ;;
    180) output="apple-touch-icon.png" ;;
    *) output="icon-${size}.png" ;;
  esac
  inset=$((size * 3 / 4))
  magick brand-mark.png -trim +repage -resize "${inset}x${inset}" \
    -gravity center -background '#fafbfc' -extent "${size}x${size}" \
    -alpha remove -strip "$output"
done
magick favicon-16.png favicon-32.png favicon.ico
magick brand-mark.png -resize 128x128 -define webp:lossless=true -strip brand-mark.webp

for name in landing-poster landing-poster-dark studio-preview studio-preview-dark; do
  for width in 640 960; do
    magick "${name}.jpg" -resize "${width}x>" -quality 90 -strip "${name}-${width}.webp"
  done
  magick "${name}.jpg" -quality 90 -strip "${name}.webp"
done
