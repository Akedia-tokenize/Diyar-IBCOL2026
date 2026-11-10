#!/bin/sh
# Download the three BDG2 files this repository uses and verify them against data_manifest.sha256.
# Usage: sh scripts/get_bdg2.sh <bdg2_root>      (then pass <bdg2_root> to run_pipeline.py / src/*)
set -e
ROOT="$1"; [ -n "$ROOT" ] || { echo "usage: sh scripts/get_bdg2.sh <bdg2_root>"; exit 2; }
MANIFEST="$(cd "$(dirname "$0")/.." && pwd)/data_manifest.sha256"
BASE=https://media.githubusercontent.com/media/buds-lab/building-data-genome-project-2/master
for f in data/metadata/metadata.csv data/weather/weather.csv data/meters/cleaned/electricity_cleaned.csv; do
  mkdir -p "$ROOT/$(dirname "$f")"
  curl -fL --retry 3 -o "$ROOT/$f" "$BASE/$f"
done
(cd "$ROOT" && sha256sum -c "$MANIFEST")
