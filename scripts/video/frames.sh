#!/usr/bin/env bash
# Extract one frame per scene midpoint for visual checking.
set -euo pipefail
WORK=${VIDEO_WORK:-/tmp/claude-0/video}
MP4=${1:-$(dirname "$0")/../../submission/demo.mp4}
mkdir -p "$WORK/frames"; rm -f "$WORK/frames"/*.jpg
python3 -c "import json;[print(k,v['mid']) for k,v in json.load(open('$WORK/offsets.json')).items()]" |
while read id t; do ffmpeg -nostdin -loglevel error -y -ss "$t" -i "$MP4" -frames:v 1 -q:v 3 "$WORK/frames/$id.jpg"; done
ls "$WORK/frames"
