#!/usr/bin/env bash
# Rebuild out/roadster_pov_x.mp4 (needs: node + playwright/chromium, python3 + numpy + scipy, ffmpeg)
set -euo pipefail
cd "$(dirname "$0")"
TMP="${TMPDIR:-/tmp}/roadster_build"
rm -rf "$TMP" && mkdir -p "$TMP" out
python3 audio.py "$TMP/audio.wav"
node render.js "$TMP/frames" 30
ffmpeg -hide_banner -loglevel error -y -framerate 30 -i "$TMP/frames/f_%05d.png" -i "$TMP/audio.wav" \
  -af "loudnorm=I=-14:TP=-1.5:LRA=11" -ar 48000 \
  -c:v libx264 -preset slow -crf 18 -pix_fmt yuv420p -profile:v high -level 4.1 \
  -c:a aac -b:a 192k -movflags +faststart -shortest out/roadster_pov_x.mp4
echo "done: out/roadster_pov_x.mp4"
