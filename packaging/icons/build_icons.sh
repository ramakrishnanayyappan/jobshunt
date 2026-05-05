#!/usr/bin/env bash
# Regenerate JobsHunt.icns and JobsHunt.ico from jobs-hunt-app.png (macOS).
# Requires: sips, iconutil (macOS), ImageMagick (`brew install imagemagick`) for multi-res .ico.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
SRC="${ROOT}/jobs-hunt-app.png"
ICONSET="${ROOT}/JobsHunt.iconset"
if [[ ! -f "$SRC" ]]; then
  echo "missing $SRC" >&2
  exit 1
fi
rm -rf "$ICONSET"
mkdir -p "$ICONSET"
for s in 16 32 128 256 512; do
  sips -z "$s" "$s" "$SRC" --out "${ICONSET}/icon_${s}x${s}.png" >/dev/null
done
sips -z 32 32 "$SRC" --out "${ICONSET}/icon_16x16@2x.png" >/dev/null
sips -z 64 64 "$SRC" --out "${ICONSET}/icon_32x32@2x.png" >/dev/null
sips -z 256 256 "$SRC" --out "${ICONSET}/icon_128x128@2x.png" >/dev/null
sips -z 512 512 "$SRC" --out "${ICONSET}/icon_256x256@2x.png" >/dev/null
sips -z 1024 1024 "$SRC" --out "${ICONSET}/icon_512x512@2x.png" >/dev/null
iconutil -c icns "$ICONSET" -o "${ROOT}/JobsHunt.icns"
rm -rf "$ICONSET"
if command -v magick >/dev/null 2>&1; then
  magick "$SRC" -define icon:auto-resize=256,128,64,48,32,16 "${ROOT}/JobsHunt.ico"
else
  echo "Install ImageMagick for JobsHunt.ico (brew install imagemagick)" >&2
  exit 1
fi
echo "Wrote ${ROOT}/JobsHunt.icns and ${ROOT}/JobsHunt.ico"
