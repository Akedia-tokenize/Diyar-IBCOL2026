#!/usr/bin/env bash
# Portable E2–E4 rerun. Historical scripts/logs remain frozen in logs_2026-11-06/.
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
DATA="${1:-$ROOT/data/bdg2}"
OUT="${2:-$ROOT/results/reproduced-e2-e4}"

mkdir -p "$OUT"
DATA="$(cd -- "$DATA" && pwd)"
OUT="$(cd -- "$OUT" && pwd)"

echo "Reference directory: $ROOT"
echo "BDG2 data: $DATA"
echo "Output directory: $OUT"

if ! (cd "$DATA" && sha256sum -c "$ROOT/data_manifest.sha256"); then
  echo "BDG2 source checksum validation failed; refusing to run." >&2
  exit 1
fi

cd "$ROOT"
python3 -I src/e2_baselines.py "$DATA" "$OUT" > "$OUT/01_e2_baselines.log" 2>&1
python3 -I src/e2_conformal.py "$OUT/e2_daily_scores.csv.gz" "$OUT" Fox > "$OUT/02_e2_conformal.log" 2>&1
python3 -I src/e3_prepare.py "$DATA" Fox "$OUT/e3_fox_daily.npz" > "$OUT/03_e3_prepare.log" 2>&1
python3 -I src/e3a_gates.py "$OUT/e3_fox_daily.npz" "$OUT" > "$OUT/04_e3a_gates.log" 2>&1
python3 -I src/e3a_quarterly.py "$OUT/e3_fox_daily.npz" "$OUT" > "$OUT/05_e3a_quarterly.log" 2>&1
python3 -I src/e3b_statistical.py "$OUT/e3_fox_daily.npz" "$OUT/e3a_quarterly.json" "$OUT" > "$OUT/06_e3b.log" 2>&1
python3 -I src/e4_review_budget.py "$OUT/e3_fox_daily.npz" "$OUT" > "$OUT/07_e4.log" 2>&1
python3 -I src/e2_out_of_time.py "$OUT/e3_fox_daily.npz" "$OUT" > "$OUT/08_e2_out_of_time.log" 2>&1
python3 -I src/e3a_extra.py "$OUT/e3_fox_daily.npz" "$OUT/e3a_extra.json" > "$OUT/09_e3a_extra.log" 2>&1

printf 'E2–E4 rerun complete. Output: %s\n' "$OUT"
