#!/usr/bin/env bash
# 08_fetch_vendor.sh - Tai san ECharts va font Be Vietnam Pro vao web/vendor, web/fonts (D15).
# Chi chay 1 lan (can mang); file tai ve duoc commit vao git de demo khong can mang.
# Dau ra: web/vendor/echarts.min.js + LICENSE, web/fonts/*.woff2 (12 file) + OFL.txt,
#         web/vendor/manifest.txt (kich thuoc + sha256 cua tung file)
# Cach chay (Git Bash, tu thu muc du an):  bash scripts/08_fetch_vendor.sh
set -euo pipefail
cd "$(dirname "$0")/.."

ECHARTS=5.5.1
FONT=5.2.8
CDN=https://cdn.jsdelivr.net/npm
mkdir -p web/vendor web/fonts

curl -fsSL -o web/vendor/echarts.min.js     "$CDN/echarts@$ECHARTS/dist/echarts.min.js"
curl -fsSL -o web/vendor/LICENSE-echarts.txt "$CDN/echarts@$ECHARTS/LICENSE"

# Can du 3 subset: vietnamese chi co chu co dau, chu a-z va so nam trong latin
for w in 400 500 600 700; do
  for s in latin latin-ext vietnamese; do
    f="be-vietnam-pro-$s-$w-normal.woff2"
    curl -fsSL -o "web/fonts/$f" "$CDN/@fontsource/be-vietnam-pro@$FONT/files/$f"
  done
done
curl -fsSL -o web/fonts/OFL.txt "$CDN/@fontsource/be-vietnam-pro@$FONT/LICENSE"

{
  echo "# echarts@$ECHARTS, @fontsource/be-vietnam-pro@$FONT (tai tu $CDN)"
  for f in web/vendor/echarts.min.js web/vendor/LICENSE-echarts.txt web/fonts/*; do
    printf '%s  %s bytes  %s\n' "$(sha256sum "$f" | cut -c1-64)" "$(wc -c < "$f" | tr -d ' ')" "$f"
  done
} > web/vendor/manifest.txt
cat web/vendor/manifest.txt
