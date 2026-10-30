# Development d03: ego-motion range Kalman candidate (pre-declaration)

Written 2026-10-29 by Claude Code after taking over from Codex, after inspecting
all d01/d02 development outcomes and **before any d03 run**. Development only
(seeds 1701–1703). d01/d02 sources, raw data and results are unchanged.

## Why a new candidate

Evaluation-only gap-forecast analysis (`gap_prediction.py`) compares the coasted
estimate the controller used during censored frames with the raw YOLO box that
matched the leader ID mask (YOLO still runs during censorship). In d02 the KF's
log-area forecast error was **worse** than the matched EMA in every gap case
(C8 0.28 vs 0.19, C4 0.18 vs 0.15, C9 0.09 vs 0.08), with similar offset error.
The true box shrank 25–55 % during many 2 s gaps because the *follower itself*
slows/changes speed under closed-loop control while coasting. An image-space
constant-rate extrapolator cannot see that.

Also: d02 C4 formation error is dominated by a **steady-state controller lag**
on the R180 turn (left follower drifts 10→27 m while continuously detecting the
leader). C4 cannot discriminate estimators and is a secondary case from now on.

## Candidate `on_ego`

`ego_tracker.py`: the unchanged d02 offset Kalman channel plus a range Kalman
channel. Area → range via the pinhole relation r = c/√area (measured
range·√area is constant within ±6 % in d02 C8). Process model
r' = w − κ·v_own, w' = white noise; own-ship speed (existing ego telemetry,
already given to both arms' controllers) is a known input. w (≈κ·leader speed)
is estimated **only from image measurements**. c comes from the controller's
own visual calibration area at the designed 25.6 m slot range; κ = 22/25.6 from
the designed formation geometry. No leader telemetry, pose, ID or schedule.
Side cameras keep the d02 tracker. Tests: `test_ego_tracker.py`.

## Arms (identical controller, coast policy, measurements, binary)

| Arm | Estimator | Lifetime |
|---|---|---|
| `on_ego` | d02 offset KF + ego-motion range KF | 3 s |
| `on` | d02 image-space robust KF | 3 s |
| `off` | matched EMA + finite-difference velocity (d01/d02 comparator) | 3 s |
| `off_short` | same EMA predictor, production non-Kalman `TRACK_HOLD_SEC` | 0.6 s |

`off_short` represents what Kalman OFF means in production (a finite-difference
predictor with a 0.6 s hold), but under the shared d02 controller/coast policy.
`on_ego` vs `off_short` therefore combines estimator **and** the longer coast the
filter justifies; `on_ego` vs `off` isolates the estimator at equal lifetime;
`on_ego` vs `on` isolates the ego-motion model.

## d03 batch (seed 1701)

1. C8, C10, C4 × all four arms (12 runs). C10 = new: sea 3.0 huge waves +
   variable-speed/S-turn leader + 2 s gaps (`extreme_cases.py`).
2. Weather observability probes, **arm `off` only** (4 runs), sea 1.5,
   variable-speed/S-turn leader, natural detector loss only:
   W1 rain 0.15, W2 rain 0.25, W3 night, W4 night + rain 0.15.

## Predeclared selection rules (fixed before d03 outcomes)

- **Weather cases for evaluation:** a probe qualifies if its analysis-window
  fresh-measurement fraction is between 35 % and 90 % (genuinely intermittent).
  Pick the most severe qualifying rain probe (lowest fresh %) and the most
  severe qualifying night probe; at most two. If none qualifies, no new weather
  case is added and the original C2/C3 total-blindness results stand as limits.
- **Candidate:** `on_ego` becomes the evaluation candidate if, in d03, (a) all
  its runs complete without errors, (b) its mean gap log-area forecast MAE over
  C8/C10/C4 is lower than `on`'s, and (c) its mean paired log-RMSE ratio vs `off`
  over C8/C10 is ≤ 0 (not worse). Otherwise `on` (d02) is the candidate. Both KF
  variants are run as arms in evaluation regardless, so nothing is hidden.
- The evaluation protocol (cases, unused seeds, arms, hypotheses, tests) is then
  frozen in a separate JSON + document before its first run.

---

## d03 outcomes (appended after the run; pre-declaration above unchanged)

Seed 1701, 12/12 four-arm runs complete, source freeze passed
(`Experiments/KalmanStudy/robust_development/d03/`). Formation RMSE (m):

| Case | KF+ego `on_ego` | KF d02 `on` | EMA 3 s `off` | EMA 0.6 s `off_short` |
|---|---:|---:|---:|---:|
| C8 clear S-turn/speed, 2 s gaps | 6.91 | 8.07 | 6.98 | 8.65 |
| C10 huge waves + S-turn, 2 s gaps | 41.61 | 131.19 | 29.90 | 11.89 |
| C4 R180 turn, 2 s gaps | 74.62 | 27.64 | 37.12 | 85.15 |

Reproducibility: C4 `on`/`off` reproduce d02 (27.72/37.12 m) to within 0.3 %.

**Rule application:** (a) all runs completed; (b) mean gap log-area forecast
MAE `on_ego` 0.347 < `on` 0.488 — passes; (c) mean paired log-RMSE ratio of
`on_ego` vs `off` over C8/C10 = +0.161 (worse) — **fails**. Per the rule the
evaluation candidate is **`on` (d02)**. Both KF variants remain evaluation arms.
(Note: `off_short` gap forecast MAE covers only the first 0.6 s of each gap,
because afterwards no forecast is used; it is not comparable to 3 s arms.)

**Failure mechanism found (C10, `on_ego`, right follower, t=32–44):** the leader
decelerates 18→10 m/s at 3 m/s² while every area-derived range carries ~±2 m
wave noise at detector confidence 0.5–0.7 and one wave-occluded outlier
(41 m vs true 21.5 m). The range filter's leader-speed state cannot follow the
deceleration in time; the follower closes to ~12 m at 7–9 m/s. During the
38–40 s gap the offset forecast extrapolates left while the leader crosses right
and leaves the frame; on reacquisition the selected box is **another object**
(leader ID box out of frame), then the track expires and the follower stays
blind (140 m). d02 `on` shows the same kind of permanent loss (left follower,
t≈46). Both EMA arms recover in this seed.

**Coast lifetime is condition-dependent:** in C8 a 3 s coast helps (EMA 3 s
6.98 vs 0.6 s 8.65 m); in C10 it hurts (29.90 vs 11.89 m). The KF's coast
covariance is driven almost entirely by elapsed time and barely separates C8
from C10 (offset 1σ at 1 s: d02 0.133 vs 0.143), so covariance-gated coasting
would act as an arbitrary time cut. Not pursued.

**Stopping decision:** a maneuver-adaptive Huber release
(`maneuver_tracker.py`) was written and replayed open-loop on the logged C10
measurements; it barely reduced the lag (observability-limited), and was
**never run closed-loop**. Remaining failures are observability/control limits
(wave-corrupted range, unseen leader deceleration, wrong-identity
reacquisition, steady-state turn lag), not filter equations. Further tuning on
one or two development seeds would overfit, so estimator development stops here.
