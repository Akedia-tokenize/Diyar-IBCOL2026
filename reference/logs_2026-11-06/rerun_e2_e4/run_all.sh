#!/bin/bash
# Full re-run of E2-E4 from the raw BDG2 files with the published scripts (DIYAR-ref v1.1 src/), 6 Nov 2026.
set -e
R=/home/claude/drive-in/v2repo; D=/home/claude/bdg2-data; O=/home/claude/rerun-2026-11-06/out
cd /home/claude/rerun-2026-11-06
(cd $D && sha256sum -c $R/data_manifest.sha256) > $O/00_sha256.log 2>&1
t0=$(date +%s)
python3 -I $R/src/e2_baselines.py $D $O > $O/01_e2_baselines.log 2>&1; echo "e2_baselines $(( $(date +%s)-t0 ))s" >> $O/timing.log
python3 -I $R/src/e2_conformal.py $O/e2_daily_scores.csv.gz $O Fox > $O/02_e2_conformal.log 2>&1; echo "e2_conformal $(( $(date +%s)-t0 ))s" >> $O/timing.log
python3 -I $R/src/e3_prepare.py $D Fox $O/e3_fox_daily.npz > $O/03_e3_prepare.log 2>&1; echo "e3_prepare $(( $(date +%s)-t0 ))s" >> $O/timing.log
python3 -I $R/src/e3a_gates.py $O/e3_fox_daily.npz $O > $O/04_e3a_gates.log 2>&1; echo "e3a_gates $(( $(date +%s)-t0 ))s" >> $O/timing.log
python3 -I $R/src/e3a_quarterly.py $O/e3_fox_daily.npz $O > $O/05_e3a_quarterly.log 2>&1; echo "e3a_quarterly $(( $(date +%s)-t0 ))s" >> $O/timing.log
python3 -I $R/src/e3b_statistical.py $O/e3_fox_daily.npz $O/e3a_quarterly.json $O > $O/06_e3b.log 2>&1; echo "e3b $(( $(date +%s)-t0 ))s" >> $O/timing.log
python3 -I $R/src/e4_review_budget.py $O/e3_fox_daily.npz $O > $O/07_e4.log 2>&1; echo "e4 $(( $(date +%s)-t0 ))s" >> $O/timing.log
echo DONE >> $O/timing.log
