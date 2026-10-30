# Development d04: Kalman range estimator + range/speed control (pre-declaration)

Written 2026-10-29 after e01/e01b were complete and analyzed. **e01 is therefore
development data for d04** (EVALUATION_PROTOCOL.md integrity rule); d04 must be
confirmed on new seeds (e02). Development runs use seeds 1701–1702.

## Motivation (e01 failure taxonomy, FINAL_REPORT.md)

All 23 catastrophic follower-tracks in e01 were longitudinal: (A) falling behind
when the leader accelerates (throttle ceiling 0.9 ≈ 21 m/s vs leader 20 m/s, no
catch-up margin); (B) overshooting a decelerating leader in huge waves (box
area ±50 % jitter; the original feed-forward leads only on acceleration) to
9–17 m, then losing it out of frame or selecting another object; (C) falling
behind during long rain coasting. The prior KF only smoothed image quantities
for an area-error controller; it never gave the controller a range/speed state.

## Arms

| Arm | Estimator | Controller |
|---|---|---|
| `on_rs` | **FusionRangeTracker**: range KF with process model r' = κ(v_leader − v_own) + b (own speed + existing leader-speed telemetry as known inputs; vision range c/√area corrects; b = bias state), 4σ innovation gating against wrong targets (re-acquire after 5 consecutive rejections), d02 offset KF | shared range/speed law |
| `off_rs` | matched EMA tracker (vision only); range = c/√EMA-area, rate from EMA log-area derivative | shared range/speed law |
| `off_short` | production non-Kalman behaviour (0.6 s hold) | original area controller |

Shared range/speed law (`range_speed_policy.py`): v_cmd = v_leader +
clamp(0.6·(r̂ − 25.6) + 0.5·ṙ̂, −8, +4) m/s, throttle = 0.043·v_cmd, ceiling 1.0,
too-close brake below 14 m; steering, coast policy, lost-track fallback unchanged.
`on_rs` vs `off_rs` isolates the estimator (identical controller, identical
telemetry in the control law; only the KF fuses telemetry into the range state
and gates measurements). `on_rs` vs `off_short` is the full system upgrade.

## d04 batch and predeclared decision rule

C8, C10, W1 × seeds 1701, 1702 × {on_rs, off_rs, off_short} = 18 runs (3 shards).
Proceed to a frozen held-out e02 with `on_rs` as the candidate if: (a) all runs
complete; (b) `on_rs` has no more catastrophic (> 50 m RMSE) runs than
`off_short`; (c) mean paired log-RMSE ratio `on_rs` vs `off_short` over the 6
case-seeds ≤ 0. If (b) or (c) fails: at most one diagnosed revision (d05) on
seed 1703, otherwise stop and report. No gains are tuned on e01 seeds.
