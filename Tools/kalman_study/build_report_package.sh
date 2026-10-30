#!/usr/bin/env bash
# Builds Documentation/KalmanStudy/REPORT_PACKAGE from the completed e02, e02x and e03_laps batches.
set -euo pipefail
ROOT=/home/stanley/Github/Unity_Ship_Formation_Study
PY=/home/stanley/miniconda3/envs/unity_boat/bin/python
EV=$ROOT/Experiments/KalmanStudy/robust_evaluation
PKG=$ROOT/Documentation/KalmanStudy/REPORT_PACKAGE
cd "$ROOT"
export PYTHONDONTWRITEBYTECODE=1 MPLCONFIGDIR=/tmp/robust-study-plots
for b in e02 e02x e03_laps; do
    python3 Tools/kalman_study/analyze_arms.py "$EV/$b" > /dev/null
    echo "analyzed $b"
done
python3 Tools/kalman_study/make_report_package.py
rm -rf "$PKG/rollout_videos" "$PKG/timeseries_metrics"
nice -n 5 $PY Tools/kalman_study/make_rollout_videos.py --out "$PKG/rollout_videos" --workers 6
nice -n 5 $PY Tools/kalman_study/make_rollout_videos.py --out "$PKG/rollout_videos_3way" --only L01,L02,L03,L04,L05,L06,L07,L08,L09,L10 --arms on_rs,off_short,raw_nogate --workers 6
nice -n 5 $PY Tools/kalman_study/make_timeseries_metrics.py --out "$PKG/timeseries_metrics"
T=$PKG/timeseries_metrics
for on in "$T"/*_on_rs_snapshots.csv; do
    b=$(basename "$on" _on_rs_snapshots.csv); off=$T/${b}_off_short_snapshots.csv
    [ -f "$off" ] || continue
    ls "$T/compare_kalman_on_vs_off/$b"/*.png > /dev/null 2>&1 && continue
    (cd "$ROOT/Assets" && $PY -m usv.plot_compare_snapshots --kalman-on "$on" --kalman-off "$off" --output-dir "$T/compare_kalman_on_vs_off/$b" --formats png > /dev/null)
done
echo "package complete: $PKG"
