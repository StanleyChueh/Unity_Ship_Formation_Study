# Weather laps re-run with the weather-trained detector (`best_realistic_v2.pt`)

Batch `Experiments/KalmanStudy/robust_evaluation/e05_weather_v2` (66 runs, all complete, source
freeze check passed for 30 files including both model files). Protocol written before any run:
`Documentation/KalmanStudy/eval_e05_weather_v2_protocol.json`. Runner: `Tools/kalman_study/run_weather_v2.py`.

**Only change vs the earlier laps (e03_laps / e04_wlaps):** the YOLO weights. Each run's config sets
`YOLO_MODEL_PATH = best_realistic_v2.pt` (fine-tuned on `boat_adaptation_v2_weather_yolo`, which adds
rain / fog / night episodes; user-reported val mAP50 0.951). Same simulator binary, cases, leader paths,
scheduled dropouts, controllers, seeds (4903, 5021), and the three report methods:

- **KALMAN ON** (`on_rs`): KF range/speed fusion tracker.
- **KALMAN OFF** (`off_short`): production Kalman-off path (finite-difference predictor, 0.6 s hold).
- **NO bbox filtering** (`raw_nogate`): raw YOLO box, no smoothing / prediction / coasting, and the
  production bbox track gate disabled; same speed controller as KALMAN ON.

Re-run: weather cases only, L04–L10 (full R360 circle lap, 2 s dropouts every 18 s) and WL1–WL4
(non-fixed path: straight, then a full 360° turn of radius ~164 m). L01–L03 (calm / waves only) not re-run.

## Contents

| Path | What |
|---|---|
| `DETECTOR_COMPARISON.md` / `.csv` | v1 vs v2 detector, per case × method, mean of both seeds |
| `detector_v1_vs_v2_*.png` | the same as dumbbell charts (hollow = v1, filled = v2), one per metric |
| `rollout_videos_3way/` | 11 videos (seed 4903), KALMAN ON / KALMAN OFF / NO bbox filtering, + `matrices/` (full metrics) |
| `rollout_videos_views/` | 11 videos: per method, top view + both follower front cameras, + `matrices/` (RMSE, IoU, steer & throttle variation) |

## Results (mean of 2 seeds, t = 15 s → end)

| Case | Leader detected v1 → v2 | RMSE KALMAN ON | RMSE KALMAN OFF | RMSE NO bbox filtering |
|---|---|---:|---:|---:|
| L04 light rain 0.15 | 5–28% → 87–88% | **2.53 m** | 5.29 m | 4.81 m |
| L05 rain 0.25 | 2–22% → 87–88% | **2.48 m** | 5.50 m | 4.91 m |
| L06 rain 0.4 | 1–9% → 88% | **2.65 m** | 5.46 m | 4.91 m |
| L07 heavy rain 1.0 | 0% → 88% | **2.73 m** | 5.62 m | 4.97 m |
| L08 night | 0% → 69–88% | **3.79 m** | 7.06 m | 301.74 m (1 of 2 seeds lost formation) |
| L09 night + rain 0.15 | ~1% → 87–88% | **3.71 m** | 7.00 m | 6.26 m |
| L10 dark storm | 2–3% → 88% | **3.31 m** | 6.14 m | 5.59 m |
| WL1 rain 0.15, non-fixed | 15–22% → 76–85% | **24.8 m** | 125.0 m | 138.6 m |
| WL2 rain 0.25, non-fixed | 7–14% → 77–84% | **35.9 m** | 125.3 m | 122.7 m |
| WL3 night, non-fixed | 0% → 67–79% | **54.8 m** | 118.5 m | 242.5 m |
| WL4 night + rain, non-fixed | ~0.5% → 71–76% | **109.9 m** | 149.9 m | 212.2 m |

(~88% is the ceiling on the laps: the scheduled 2 s dropouts remove ~11% of frames.)

**What changed.** With detector v1 every method failed in rain/night/dark storm (RMSE hundreds of
metres) because the leader was not detected. With v2 the leader is detected in ~88% of frames in every
lap condition, all three methods hold the formation, and **KALMAN ON has the lowest error in all 7 weather
laps, roughly half that of the other two** (and the highest IoU, 0.75–0.83 vs 0.42–0.73).

**Recovery after each 2 s bbox dropout** (L04–L10, v2): KALMAN ON back within its pre-dropout error in
**0.9 s**; KALMAN OFF 5.9–6.6 s; NO bbox filtering 7.5–9.0 s. NO bbox filtering did not recover at all
in L08 night seed 5021: it has no coasting, fell behind after the first dropouts, and lost the leader
from view (no wrong-identity frames in that run).

**Non-fixed laps (WL1–WL4) still fail for every method**, now for a different reason: the leader is
detected by both followers until late in the run, but formation error grows steadily from t ≈ 30 s
during the long tight turn (radius ~164 m), until the inner follower loses the leader from its camera
field of view. This is a controller / formation-geometry limit on sustained tight turns, not a
detector problem. KALMAN ON degrades slowest (WL1 seed 4903 at t = 85 s: 68 m vs 312 m OFF, 379 m no filtering).

**Caveat.** Detector v2 was trained on the same simulated rain overlay, fog and night lighting used in
these tests (different episodes, same renderer), so this shows the simulated weather is learnable; it is
not evidence about real rain or real night cameras. Descriptive batch, 2 seeds per cell; not a
confirmatory test.
