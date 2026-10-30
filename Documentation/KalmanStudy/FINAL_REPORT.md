# Does a Kalman filter improve vision-based formation holding under extreme conditions?

## UPDATE — second held-out test e02 (redesigned Kalman range/speed system): POSITIVE

The first held-out test (e01, below) of the d02 image-space KF was negative. Its
failure analysis showed every catastrophe was a longitudinal speed-control
failure (falling behind / overshooting the leader in waves), which an image
smoother cannot fix. The redesign d04 (`ROBUST_D04.md`) estimates **range** with
a Kalman filter fusing vision (box-size range), own speed and the leader-speed
telemetry the controller already had, gates wrong-target detections with the
KF innovation covariance, and drives a range/speed control law. It passed its
predeclared development rule, then was tested on **8 never-used seeds** under a
frozen protocol (`EVALUATION_PROTOCOL_E02.md`, `eval_e02_protocol.json`).

### Confirmatory results (C8 clear S-turn + 2 s losses, C10 huge waves sea 3.0 + S-turn + 2 s losses, W1 rain with natural losses; exact sign-flip over 2^8 seed blocks, fixed sequence, α = 0.05)

| Hypothesis | Geometric RMSE change | 95 % bootstrap | Seeds favouring KF | Exact p | Result |
|---|---:|---:|---:|---:|---|
| **H1 KF range/speed vs NO filter (same controller)** | **−68.8 %** | [−72.4, −62.6] | **8/8** | **0.0078** | **confirmed** |
| **H2 KF range/speed vs production Kalman-OFF** | **−48.9 %** | [−59.7, −39.0] | **8/8** | **0.0078** | **confirmed** |
| H3 KF vs matched non-Kalman EMA (same controller) | −33.2 % | [−53.3, −5.5] | 6/8 | 0.078 | not confirmed (trend) |

p = 0.0078 is the smallest value attainable with 8 seeds (every seed favoured KF).
Both confirmed hypotheses also meet the predeclared practical target (≥ 20 %
reduction and lower formation-broken time). Files: `robust_evaluation/e02/inference_primary.json`,
`descriptive_block_tests.json`, `results.json`, `MATRIX.md`.

### Per-case matrix (8 seeds each; broken = time with formation RMS > 10 m)

| Case | Metric | **KF range/speed** | EMA range/speed | Production OFF | No filter |
|---|---|---:|---:|---:|---:|
| C8 clear, S-turn + speed changes, 2 s losses | median RMSE m | **4.3** | 4.6 | 7.4 | 7.8 |
| | broken time % | **0.0** | 4.6 | 23.1 | 24.7 |
| | IoU | **0.775** | 0.747 | 0.660 | 0.673 |
| C10 HUGE waves + S-turn, 2 s losses | median RMSE m | **4.7** | 7.9 | 8.4 | 8.6 |
| | broken time % | **8.1** | 29.5 | 28.3 | 37.3 |
| | catastrophic (> 50 m) | 1/8 | 1/8 | 1/8 | 0/8 |
| | min separation m | **14.3** | 11.1 | 7.0 | 14.4 |
| W1 rain 0.15 + sea 1.5, natural losses (~37 % fresh detections) | median RMSE m | **5.4** | 6.9 | 11.8 | 65.2 |
| | broken time % | **2.2** | 17.0 | 52.4 | 82.0 |
| | catastrophic | **0/8** | 0/8 | 1/8 | **8/8** |

Honest caveats: (1) in C10 the KF arm still has one catastrophic seed (4513:
108 m; production OFF failed the same seed at 133 m). Mechanism: right after a
2 s loss the reacquired box was the **other follower**; after 2 s of coasting in
huge waves the KF's predicted covariance is wide enough that a 4σ position gate
admits it; the follower steered toward it and lost the leader. Because of that
seed, C10 *mean* RMSE of no-filter (12.8 m) is below the KF's (17.4 m), although
median, broken time and IoU favour the KF. (2) H3 is not confirmed: part of the
gain comes from the new range/speed controller, which the EMA arm shares; the
KF adds a further 33 % on average (6/8 seeds) but this is not significant.
(3) Heavy rain, dark storm and night are detector-blind (0 % correct detections)
and were not re-tested; no filter can compensate (e01b). (4) Simulator only.

### What the thesis can now claim (supported by pre-registered held-out evidence)

> Using a Kalman filter to estimate the leader's relative range — fusing camera
> measurements with own-ship and leader speed — and to gate implausible detections
> improves formation holding under huge waves, light rain and temporary leader-box
> loss with a maneuvering leader: −69 % formation error vs. no filtering and −49 %
> vs. the production non-Kalman system, in 8/8 unseen seeds each (p = 0.0078).

It cannot claim that the Kalman filter beats every well-designed non-Kalman
filter (H3 not confirmed), nor robustness when the detector is blind.

### Secondary and control cases (e02, 4 seeds each, descriptive)

| Case | KF range/speed | EMA range/speed | Production OFF | No filter | Reading |
|---|---:|---:|---:|---:|---|
| C0 calm, median RMSE m | 2.5 | 2.6 | 4.4 | 2.5 | no loss → filter irrelevant; new controller holds tighter |
| C1 huge waves, no scheduled loss | 3.7 | 3.5 | 5.0 | 3.5 | same: waves alone are not the problem |
| C4 tight R180 turn + 2 s losses | 11.2 (broken 37 %) | **6.1 (0 %)** | 88.1 (4/4 > 50 m) | 144.5 (4/4 > 50 m) | **counterexample: matched EMA beats the KF here** |
| C7 unexpected turn inside 8 s blackout | 338 (min sep **4.0 m**) | 309 | 252 | 234 | negative control: **all fail**; confident coasting cannot foresee an unseen turn — safety caveat |

### Key frames and figures (`Documentation/KalmanStudy/eval_e02/`)

Exact detector JPEGs; white box = true leader (evaluation-only), magenta = YOLO box
used, orange line = estimate the controller used. Rows: KF range/speed, production
OFF, no filter, EMA range/speed. `keyframe-selection.json` lists every JPEG hash.

- `W1_rain015_rough_s_keyframes.jpg` (preselected middle seed): **no filter is LOST
  from t = 25 s and falls 60 m behind; the KF coasts through rain dropouts with its
  estimate on the leader and stays ≈ 5 m** — the clearest "Kalman helps" evidence.
- `C8_clear_speed_s_dropout_keyframes.jpg`: during the scheduled 2 s loss
  production OFF and no-filter are LOST, the KF arm COASTs on the leader.
- `C10_huge_waves_s_dropout_timeseries.png` / `_keyframes.jpg`: huge-wave case.
- `*_vs_<baseline>_EXTREMUM_largest_benefit/disadvantage.jpg`: largest KF advantage
  and disadvantage instants over all seeds, labelled as extrema (includes the
  C10 seed-4513 wrong-identity failure and the C4/C7 counterexamples).
- `matrix.png`: every run, every seed, no removals.
- `condition_videos/ALL_CONDITIONS_grid.mp4`: what each weather/wave level looks like.

### e02 integrity

Protocol hash `83af4923…` in the manifest; 160/160 runs complete; source-freeze
check passed (26 files, `e02/source-freeze-check.json`); binary hash unchanged
since v2. Inference computed when the 96 primary runs completed and re-computed
after all 160 — identical. Executed as 6 parallel shards (`run_d04.py`), separate
private projects and ports; fixed-step simulation. Development for d04 used
seeds 1701–1703 and the e01 data (declared in `ROBUST_D04.md`).

Reproduce:
```bash
python3 Tools/kalman_study/analyze_arms.py Experiments/KalmanStudy/robust_evaluation/e02
python3 Tools/kalman_study/infer_eval.py Experiments/KalmanStudy/robust_evaluation/e02 --protocol Documentation/KalmanStudy/eval_e02_protocol.json
python3 Tools/kalman_study/make_eval_figures.py Experiments/KalmanStudy/robust_evaluation/e02 --treatment on_rs --baselines off_short,raw,off_rs --output Documentation/KalmanStudy/eval_e02
python3 -m unittest discover -s Tools/kalman_study -p 'test_*.py'    # 26 tests
```

### Recommended next steps

1. Identity-robust reacquisition (appearance/ID cue or tighter post-coast gate) for
   the remaining huge-wave failure mode. 2. Investigate why the KF loses to the
   EMA on the tight turn (C4). 3. Cap coasting speed/closing when the leader is
   unobserved for long (C7 near-collision). 4. Integrate into production only after
   a native-app (real-time, asynchronous) check; the study used a fixed-step harness.

---

# Earlier result (kept): first held-out test e01 of the d02 image-space KF — negative

## Bottom line

1. **The pre-registered confirmatory test is negative.** On 8 never-before-used
   seeds, the pre-selected Kalman candidate (`on`, d02 robust image-space KF) did
   **not** beat production's non-Kalman behaviour (`off_short`) over the primary
   extreme family (huge waves + maneuvering leader + dropouts, clear-weather
   maneuvers + dropouts, light rain with natural detection loss): geometric RMSE
   **−14.1 % (worse)**, bootstrap 95 % [−67 %, +19 %], 4/8 seed blocks favour
   KF, exact sign-flip p = 0.57. The equal-lifetime test (H2) was therefore not
   confirmatory (−18.7 %, p = 0.47).
2. **Where Kalman prediction does help, consistently:** short (2 s) bbox losses
   while the leader changes speed and S-turns in clear weather (C8). Both KF
   variants beat production OFF in 7/8 and 8/8 seeds (+15.7 % / +19.4 % geometric
   RMSE, broken-formation time 27 % → 22 % / 20 %), with **0/8 catastrophic
   failures** for either KF. Keyframes show why: during the loss production OFF
   is LOST (no estimate after 0.6 s), while the KF keeps the coasted estimate on
   the leader's true position. Per-case results are descriptive (uncorrected).
3. **Under huge waves and rain the outcome is dominated by rare catastrophic
   failures in every arm** (C10: 3/8 seeds > 50 m RMSE in *each* arm). These are
   wrong-target reacquisitions / permanent losses after the follower closes on a
   decelerating leader in heavy pitch-roll; no estimator variant prevented them.
4. **Exploratory (not confirmatory):** the ego-motion range KF (`on_ego`, d03),
   which our pre-declared development rule *rejected*, did best on the held-out
   data (vs production OFF +16.3 %, p = 0.44; median C10 RMSE 9.2 m vs 19.0 m;
   vs d02 KF +26.6 %, 6/8 blocks, p = 0.20). This is a hypothesis for a new
   held-out test with fresh seeds, **not** evidence of benefit.
5. **Heavy rain, dark storm and night are detector limits, not filter limits:**
   correct leader detection is 0–4 % there (see e01b and condition videos).
   No tracker can hold formation without measurements.

What this means for the thesis claim: the data support "Kalman-based coasting
keeps the formation through short detection losses during leader maneuvers in
clear conditions", and do **not** support "a Kalman filter makes formation holding
robust in extreme waves or bad weather" in this simulator and pipeline.

## What was compared (shared controller in all arms)

| Arm | Estimator | Coast lifetime |
|---|---|---|
| `on` (pre-registered candidate) | d02 robust image-space KF (offset + log-area, adaptive R, Huber) | 3 s |
| `on_ego` | d02 offset KF + range KF using own-ship speed as known input (d03) | 3 s |
| `off` | non-Kalman EMA + finite-difference velocity (matched comparator) | 3 s |
| `off_short` | same EMA predictor with production's `TRACK_HOLD_SEC = 0.6 s` = **production "Kalman OFF"** | 0.6 s |

All arms share binary, plant, YOLO detector (`best_realistic.pt`), raw selected
measurements, the d01 controller changes and the d02 confidence-aware coast
policy. Improvements shared by all arms are not attributed to the KF. No arm
receives leader pose, ID masks, future trajectory or the dropout schedule.

## Primary held-out results (e01, 8 seeds × 3 cases × 4 arms = 96 runs)

Formation RMSE (m), follower error vs the leader-rotated formation slots, t=15–60 s.

| Case | KF+ego | KF d02 (candidate) | EMA 3 s | Production OFF |
|---|---:|---:|---:|---:|
| C8 clear S-turn/speed + 2 s losses — median | **6.8** | 7.5 | 6.7 | 8.3 |
| C8 — catastrophic (> 50 m) | 0/8 | 0/8 | 1/8 | 0/8 |
| C10 huge waves (sea 3.0) + S-turn + 2 s losses — median | **9.2** | 44.7 | 16.8 | 19.0 |
| C10 — catastrophic | 3/8 | 3/8 | 3/8 | 3/8 |
| W1 rain 0.15 + sea 1.5, natural losses — median | 14.4 | 22.1 | **11.1** | 13.7 |
| W1 — catastrophic | 1/8 | 3/8 | 1/8 | 1/8 |

Full matrix with means, IoU, broken time, fresh %, gap error and gap forecast
error for all contrasts: `Experiments/KalmanStudy/robust_evaluation/e01/MATRIX.md`
(per-seed values in `results.json` / `run-results.csv`).

Seed-block tests (mean over C8/C10/W1 of log RMSE ratio, exact 2^8 sign-flip):

| Contrast | Geometric RMSE change | 95 % bootstrap | Blocks favouring | p | Status |
|---|---:|---:|---:|---:|---|
| **H1 `on` vs `off_short`** | **−14.1 %** | [−67.3, +19.0] | 4/8 | 0.570 | confirmatory, not rejected |
| H2 `on` vs `off` | −18.7 % | [−78.3, +19.2] | 4/8 | 0.469 | descriptive (gate closed) |
| `on_ego` vs `off_short` | +16.3 % | [−19.1, +44.0] | 4/8 | 0.438 | exploratory |
| `on_ego` vs `off` | +12.9 % | [−6.4, +29.7] | 5/8 | 0.273 | exploratory |
| `on_ego` vs `on` | +26.6 % | [−12.4, +52.0] | 6/8 | 0.203 | exploratory |
| `off` vs `off_short` | +3.9 % | [−52.0, +38.5] | 4/8 | 0.883 | exploratory |

Files: `e01/inference.json` (confirmatory), `e01/descriptive_block_tests.json`.

## Key frames (exact detector JPEGs; white = GT leader, evaluation-only)

- `eval_e01/exploratory_on_ego/C8_clear_speed_s_dropout_keyframes.jpg` and
  `eval_e01/candidate_on/C8_clear_speed_s_dropout_keyframes.jpg` — preselected
  middle seed, loss start / middle / end / +2 s: production OFF shows **LOST**
  at t = 21.0 and 21.9 s; KF arms show **COAST** with the orange estimate on the
  leader. This is where Kalman prediction helps.
- `eval_e01/*/C10_huge_waves_s_dropout_timeseries.png` (seed 3299): production
  OFF closes blind on the leader after the 38–40 s loss (box area → 31 000 px),
  loses it permanently and drifts to 350 m; KF+ego and EMA 3 s hold formation;
  the d02 candidate degrades to ~115 m. Same case, other seeds: KF arms fail
  instead (see per-seed table) — this is why the aggregate is not significant.
- `*_EXTREMUM_largest_benefit.jpg` / `*_EXTREMUM_largest_disadvantage.jpg`:
  the single instants of largest KF advantage and disadvantage across all seeds,
  labelled as extrema (not representative). `keyframe-selection.json` lists the
  SHA-256 of every JPEG used.
- `condition_videos/ALL_CONDITIONS_grid.mp4`: all weather/wave levels on one
  timeline, with measured severity (wave Hs proxy, camera pitch/roll, detection %).

## Secondary / limit conditions (e01b, `on` vs `off_short`)

Held-out seeds 2701–3007, `on` (d02 KF) vs `off_short` (production OFF), 28 runs,
source freeze passed (`robust_evaluation/e01b/`). Mean RMSE (m), correct leader detection:

| Case | n | KF d02 | Production OFF | Correct detection | Reading |
|---|---:|---:|---:|---:|---|
| C0 calm | 2 | 4.33 | 4.37 | 100 % | no difference, both hold formation |
| C1 huge waves, no scheduled loss | 3 | 4.82 | 4.86 | 95–98 % | waves alone are handled by both |
| C7 unexpected turn inside 8 s loss | 3 | 263.8 | 251.6 | 11–45 % | both fail (negative control: no filter can see an unseen turn) |
| C2 heavy rain 1.0 | 2 | 329.5 | 365.8 | **0 %** | detector blind, both fail |
| C3 dark storm | 2 | 369.2 | 439.6 | **0 %** (only false boxes) | detector blind, both fail |
| W3 night | 2 | 232.1 | 197.9 | **0 %** | detector blind, both fail |

Huge waves only become a problem when combined with loss of the leader box and
leader maneuvers (C10). Rain/darkness above light rain defeat the detector itself.

## Failure mechanisms (development diagnostics, `ROBUST_D03.md`)

- Huge waves: area-derived range carries ±2 m noise at detector confidence
  0.5–0.7 plus wave-occlusion outliers; a 3 m/s² leader deceleration is not
  observable fast enough; the follower closes to ~12 m. During a loss the offset
  forecast can extrapolate the wrong way while the leader crosses the frame; on
  reacquisition another object is selected (wrong identity) and the track is lost.
- Coast lifetime is condition-dependent; the KF covariance during coasting is
  driven by elapsed time and does not identify when coasting is unsafe.
- Night/heavy rain: YOLO is blind (0 % correct detections); dark storm produces
  false boxes only.
- C4 tight turn: steady-state controller lag while the leader is visible; not an
  estimator problem (excluded from the primary family before held-out data).

## Integrity record

- Development (v2 original 60 runs, d01, d02, d03, d03_weather) used seeds
  1701–1703 only; held-out seeds 2701…3727 were first used in e01.
- Protocol frozen before e01 (`EVALUATION_PROTOCOL.md`, `eval_e01_protocol.json`,
  hash in manifest). Amendments, all recorded before any e01 result was viewed:
  A1 truncation after the primary group (user time limit), A2 parallel e01b,
  A3 computer shutdown/resume, A4 manual truncation after the watcher failed
  (one extra complete run + one partial run preserved unanalyzed).
- Source-freeze checks passed (`e01/source-freeze-check.json`; e01b: see its
  folder). Simulator binary SHA-256 equal across all batches.
- Interrupted and truncated runs are preserved in `e01/interrupted_shutdown/`,
  `e01/aborted_truncation/`, `e01b/interrupted_shutdown/`.
- Known instrumentation caveat: the frozen 720p StudyRig encodes ID-box y with a
  360 px offset; corrected in the reader (`COORDINATE_CORRECTION.md`).
- Simulator scope: rain is an image overlay, darkness is scene lighting; seeds
  are not a sample of real oceans. Both followers and all frames of one episode
  form one experimental unit.

## Reproduce

```bash
python3 Tools/kalman_study/analyze_arms.py Experiments/KalmanStudy/robust_evaluation/e01 --allow-partial
python3 Tools/kalman_study/infer_eval.py Experiments/KalmanStudy/robust_evaluation/e01 --protocol Documentation/KalmanStudy/eval_e01_protocol.json --truncated
python3 Tools/kalman_study/analyze_arms.py Experiments/KalmanStudy/robust_evaluation/e01b
python3 Tools/kalman_study/make_eval_figures.py Experiments/KalmanStudy/robust_evaluation/e01 --treatment on --output Documentation/KalmanStudy/eval_e01/candidate_on
python3 -m unittest discover -s Tools/kalman_study -p 'test_*.py'
```
Re-running simulations: `run_candidate.py` / `run_parallel_batch.py` with the
protocol JSONs (needs the frozen build, backed up in `~/usv_study_tmp_backup`).

## Recommended next step

If the thesis needs a positive confirmatory claim, the defensible one is narrow:
pre-register `on_ego` (unchanged) vs production OFF on C8-type scenarios (short
losses during leader maneuvers, clear-to-moderate seas) with ≥ 8 **new** seeds.
Robustness in huge waves/rain requires fixing wrong-target reacquisition
(identity gating) and a better detector for rain/night, not a different filter.
