#!/usr/bin/env bash
# After e05_weather_v2 completes: 3-way videos + matrices, views videos + 4-metric matrices,
# and the detector v1 vs v2 comparison, all in REPORT_PACKAGE/weather_v2_detector/.
set -euo pipefail
ROOT=/home/stanley/Github/Unity_Ship_Formation_Study
PY=/home/stanley/miniconda3/envs/unity_boat/bin/python
EV=$ROOT/Experiments/KalmanStudy/robust_evaluation
OUT=$ROOT/Documentation/KalmanStudy/REPORT_PACKAGE/weather_v2_detector
ONLY=L04,L05,L06,L07,L08,L09,L10,WL1,WL2,WL3,WL4
cd "$ROOT/Tools/kalman_study"
export PYTHONDONTWRITEBYTECODE=1 MPLCONFIGDIR=/tmp/robust-study-plots KS_BATCHES=e05_weather_v2
python3 analyze_arms.py "$EV/e05_weather_v2" > /dev/null && echo "analyzed e05_weather_v2"
mkdir -p "$OUT/rollout_videos_3way" "$OUT/rollout_videos_views"
$PY make_rollout_videos.py --out "$OUT/rollout_videos_3way" --only $ONLY --arms on_rs,off_short,raw_nogate --clean --workers 4
KS_3WAY_DIR=$OUT/rollout_videos_3way python3 make_video_matrices.py
KS_DETECTOR_LABEL='detector v2 (weather-trained)' $PY make_views_videos.py --out "$OUT/rollout_videos_views" --only $ONLY --workers 6
KS_VIEWS_DIR=$OUT/rollout_videos_views python3 make_views_matrices.py
python3 make_detector_comparison.py
echo "weather v2 package complete"
