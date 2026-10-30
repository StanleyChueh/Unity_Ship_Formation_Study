#!/usr/bin/env bash
# After e04_wlaps completes: 3-way videos for the W laps, all 3-methods x 3-views videos,
# and one experiment matrix per 3-way video.
set -euo pipefail
ROOT=/home/stanley/Github/Unity_Ship_Formation_Study
PY=/home/stanley/miniconda3/envs/unity_boat/bin/python
EV=$ROOT/Experiments/KalmanStudy/robust_evaluation
PKG=$ROOT/Documentation/KalmanStudy/REPORT_PACKAGE
cd "$ROOT"
export PYTHONDONTWRITEBYTECODE=1 MPLCONFIGDIR=/tmp/robust-study-plots
python3 Tools/kalman_study/analyze_arms.py "$EV/e04_wlaps" > /dev/null && echo "analyzed e04_wlaps"
# The old W1-W4 3-way videos used the 60 s S-turn path (not a circle); keep them, but outside this folder.
mkdir -p "$PKG/rollout_videos_3way_old_nonlap"
mv "$PKG"/rollout_videos_3way/W[1-4]_*_3way.mp4 "$PKG/rollout_videos_3way_old_nonlap/" 2>/dev/null || true
$PY Tools/kalman_study/make_rollout_videos.py --out "$PKG/rollout_videos_3way" --only WL1,WL2,WL3,WL4 --arms on_rs,off_short,raw_nogate --clean --workers 4
$PY Tools/kalman_study/make_views_videos.py --workers 8
python3 Tools/kalman_study/make_video_matrices.py
echo "views package complete"
