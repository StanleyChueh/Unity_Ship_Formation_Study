# Held-out evaluation e01 — frozen protocol

Frozen 2026-10-29 by Claude Code **before any e01 run**, after all development
(v2 original matrix, d01, d02, d03, d03_weather) was inspected. Machine-readable
spec: `eval_e01_protocol.json`; its SHA-256 is stored in the e01 manifest and
`infer_eval.py` refuses any other protocol. Supersedes the primary family in
`STATISTICAL_POLICY.md` (C1/C4/C5), which is kept as a descriptive secondary
family. This amendment is made before held-out data, for the reasons below.

## What is compared

All arms share the same binary, plant, detector, raw selected measurements,
controller (d01 shared changes + d02 confidence-aware coast policy) and timing.

| Arm | Meaning |
|---|---|
| `on` (**candidate**, d02) | robust image-space Kalman filter, 3 s coast |
| `on_ego` (d03) | `on` + ego-motion range Kalman channel, 3 s coast |
| `off` | matched non-Kalman EMA + finite-difference velocity, 3 s coast |
| `off_short` | same EMA predictor with production's 0.6 s non-Kalman hold |

`off_short` is the production meaning of "Kalman OFF" (production's non-KF path
is a finite-difference predictor with `TRACK_HOLD_SEC = 0.6`). The candidate was
chosen by the rule predeclared in `ROBUST_D03.md`.

## Cases

- **Primary family** (measurement loss with a maneuvering leader; equal weight):
  C8 clear variable-speed/S-turn + 2 s scheduled losses; C10 sea 3.0 huge waves
  + variable-speed/S-turn + 2 s losses; W1 rain 0.15 + sea 1.5 + S-turn with
  natural intermittent detector loss (selected by the predeclared visibility
  rule). 8 held-out seeds: 2701, 2869, 3007, 3163, 3299, 3461, 3581, 3727.
- **Secondary** (descriptive, 5 seeds, all arms): C1 huge waves without
  scheduled loss; C4 R180 turn + 2 s losses (controller-lag limited, see d03);
  C7 unexpected turn inside an 8 s loss (negative control); C5 rain 0.4 S-turn
  (near-blind original case, retained as required by OBSERVABILITY_AMENDMENT).
- **Control**: C0 calm, `on` vs `off_short`, 5 seeds.
- **Limits**: C2 heavy rain, C3 dark storm, W3 night (detector ~0 % fresh in
  development), `on` vs `off_short`, 5 seeds. Expected to fail in every arm;
  reported, not interpreted as successes.

Why C4/C5 left the primary family: d02/d03 showed C4 error is a steady-state
controller lag present while the leader is continuously detected, and C5 is
near-blind outside its scheduled gaps; neither discriminates estimators.

## Hypotheses and tests

Block statistic per held-out seed = mean over C8/C10/W1 of log(RMSE_arm /
RMSE_baseline). Exact two-sided paired sign-flip test over all 2^8 = 256
patterns; seeded bootstrap of whole seed blocks for a 95 % interval.
Fixed-sequence gatekeeping at α = 0.05 (FWER-controlling):

1. H1: `on` vs `off_short` — does the Kalman pipeline beat production's
   non-Kalman OFF behaviour under the shared controller?
2. H2 (only if H1 rejected): `on` vs `off` — does the Kalman filter beat an
   equal-lifetime model-free predictor (estimator contribution alone)?

Practically substantial = ≥ 20 % geometric RMSE reduction **and** lower mean
formation-broken (>10 m) time. All other contrasts (`on_ego` vs each,
`off` vs `off_short`, per-case, secondary family C1/C4/C5) are descriptive and
uncorrected. A two-sided result in the harmful direction is reported as harm.

## Integrity rules

- No source, tuning, case or seed changes after the first e01 run; the archiver
  snapshots and re-checks all hashed sources. Every run is reported, including
  crashes (a crash is reported, not re-run silently) and catastrophic failures.
- If any arm/candidate is revised after seeing e01, e01 becomes development
  data for that revision and new seeds are required.
- Metrics: follower RMSE vs rotated initial offsets, triangle IoU, broken
  fraction, P95/peak error, fresh/stale/lost, scheduled-gap RMSE, recovery,
  evaluation-only gap forecast error, command variation. Seeds are blocks;
  frames and followers are not replicates. Simulator seeds are not a sample of
  real oceans; rain is a synthetic overlay; darkness is scene lighting only.

## Amendment A1 — truncation for time (recorded before any e01 result was viewed)

Recorded 2026-10-29 while e01 was at run ~15/216, at the user's request to save
time; no e01 outcome had been analyzed or viewed. The **primary group and its
confirmatory inference are unchanged** (C8/C10/W1 × 8 seeds × 4 arms = runs
1–96; `infer_eval.py` hypotheses and fixed sequence unchanged). The runner is
stopped when run 97 begins; that single partial run directory is moved to
`e01/aborted_truncation/` (preserved, not analyzed). e01's remaining secondary,
control and limit groups (runs 97–216, including C4 and C5) are **not run**.
They are replaced by the smaller descriptive batch `e01b`
(`eval_e01b_protocol.json`): C1 and C7 (3 seeds), C0 calm and limits C2/C3/W3
(2 seeds), `on` vs `off_short` only. Consequences: no held-out C4/C5 data (their
development and original-matrix results are reported instead), and the
STATISTICAL_POLICY C1/C4/C5 descriptive family cannot be computed on held-out
seeds. The source-freeze check for truncated e01 is performed by comparing the
archived snapshot hashes with the sources after run 96.

## Amendment A2 — parallel execution of e01b (recorded before any e01 result was viewed)

Recorded 2026-10-29 at e01 run 77/96, to save time. e01b (unchanged protocol,
`eval_e01b_protocol.json`) starts now and runs concurrently with the remaining
e01 primary runs, via `run_parallel_batch.py`: separate private project
`/tmp/usv-eval-b` and bridge TCP port 47530 (recorded in its jobs). Sources,
binary, cases, arms and seeds are unchanged. The simulation is fixed-step and
synchronous, so concurrency changes wall-clock speed, not the simulated timeline.
Verified before launch: all 77 completed e01 runs and all overlapping user
`play_case.py` runs logged 3 boat UDP binds + 1 wave bind and no bind errors
(the scene's idle UDP listeners share ports with address reuse and receive
nothing in study mode). The truncation of e01 (A1) is now done by
`truncate_e01_only.sh`, which no longer launches e01b.

## Amendment A3 — interruption for a computer shutdown (before any e01 result was viewed)

2026-10-29 ~16:05: the user had to shut the computer down. Both runners were stopped
with SIGINT (simulator/bridge terminated by the runner's cleanup). State at stop:
e01 83/96 primary runs complete, e01b 5/28 complete. The two in-progress runs
(`e01/runs/W1_rain015_rough_s_3299_off`, `e01b/runs/C1_huge_waves_3007_on`) were moved,
unanalyzed, to `*/interrupted_shutdown/` and are re-run from scratch on resume.
Because Ubuntu clears /tmp at boot, the frozen simulator build and baseline project
were copied to `/home/stanley/usv_study_tmp_backup/` (binary SHA-256 verified equal
to the manifests). `Tools/kalman_study/resume_after_reboot.sh` restores them, verifies
the binary and every hashed source against both manifests, and relaunches the same
commands; completed runs are skipped. No case, arm, seed or source changed.

## Amendment A4 — manual truncation (execution deviation, recorded before analysis)

After the A3 resume, `truncate_e01_only.sh` did not stop the runner at run 97 (the
resumed runner was a background job of a non-interactive shell, so SIGINT was
ignored; the watcher logged nothing). The runner completed run 97
(`C1_huge_waves_2701_off`) and started run 98 (`C1_huge_waves_2701_off_short`)
before Claude Code stopped it with SIGTERM and terminated its simulator/bridge.
Both directories were moved, unanalyzed, to `e01/aborted_truncation/` as A1
requires. All 96 primary runs are complete; `e01/source-freeze-check.json` passed
(21 sources, binary hash equal). No e01 outcome had been viewed at this point.
