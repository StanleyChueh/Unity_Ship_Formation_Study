# Resume the Kalman formation study — START HERE

Last checkpoint: 2026-10-29 12:34:15 CST. Workspace:
`/home/stanley/Github/Unity_Ship_Formation_Study`.

**The task is NOT finished. Do not claim Kalman helps significantly yet.**

**Read LIVE_STATE.json for the newest automatic progress/quota checkpoint.**
User requests transfer when the Codex five-hour meter has3% remaining. A local
session token_count event exposes that meter; at the last manual check it had7%
remaining (93%used). quota_checkpoint.py --watch refreshes LIVE_STATE.json every10s
and writes QUOTA_HANDOFF_REQUIRED.json when remaining<=3. It does not kill jobs.
Codex should update this handoff and deliver the root resume prompt at that point.

## User's objective and constraints

Develop and evaluate formation control with Kalman ON/OFF under large waves,
heavy rain, darkness and temporary leader bbox loss. Vary leader turns/speed.
Deliver an honest experiment matrix, keyframes demonstrating benefits AND
failures, reproducible raw data/code/model hashes and audit-ready documentation.
User explicitly authorizes designing a stronger Kalman filter if the original
fails. Preserve negative results; do not cherry-pick, fabricate evidence, feed
leader ground truth into the estimator, or weaken OFF to manufacture a win.
Claude Code Opus will audit the work. User also requests this handoff if usage
approaches its limit. They have not asked to stop the experiments.

## Current checkpoint

- Original frozen v2 study: **60/60** runs complete.
- Original v2 is complete. Replacement d01 is now executing.
- Original root runtime files remain unchanged. Root git changes are Tools,
  Documentation and .gitignore, plus the supplementary model-test observer.
- Replacement tracker exists and numerical/adapter tests pass (7 checks), but
  **one replacement closed-loop pair is complete so far**: C0seed1701 EMA OFF5.08m versus robust KF ON4.88m (4.0% improvement). This is development, not held-out evidence. Read d01/results.json for newer progress; regenerate with --allow-partial if necessary.
- Replacement development d01 is running after all original v2 runs completed. Do not launch another competing Unity/GPU test.
- No replacement filter has been deployed to the production application.

## Live processes / tool sessions

If using this same Codex session, unified exec session IDs:

- `6414`: original v2 runner completed successfully, exit0; no longer running.
- `63339`: initial d01 launch failed at import before Unity started; preserved under d01/diagnostics/initial_import_failure.
- **`90956`**: active resumed d01 runner, `python3 Tools/kalman_study/run_robust.py --cases C0,C1,C4,C5 --seeds 1701 --tag d01`. Missing depth_Anything.py was copied into its private Assets folder from the original isolated project; dependency-fix.json records its hash. Candidate/harness hashes and manifest are unchanged.
- `88123`: initial finalization stopped when the audit caught an ID-box y-coordinate bug.
- **`41545`**: resumed finalization after the documented reader correction; audit passed60 jobs/39060 steps/78120 JPEG hashes,48 matched old-predictor replays saved, figure/video generation completed successfully, exit0. legacy-finalization.complete exists. Matrix, corrected camera overlay, a severe-wave all-seed failure keyframe and the C4 paired keyframe sheet were visually inspected.
- `20002`: supplementary native-app build completed successfully; not running.
- **`11757`**: queued native-app originalON/OFF pair, `python3 Tools/kalman_study/run_actual_app.py --no-build --wait-for Experiments/KalmanStudy/robust_development/d01`. It waits for d01/source-freeze-check.json, then runs the native pair. Do not launch competing GPU jobs or edit root runtime until it finishes. realtime/protocol-manifest.json records pre-outcome source hashes.
- `64847`: d01 archiver completed successfully;8/8 runs analyzed and source-freeze-check.json passed.
- **`7182`**: live quota/checkpoint watcher, no GPU; stops itself after writing the3%-remaining handoff marker.
- **`96828`**: queued d02, `python3 Tools/kalman_study/run_robust_next.py --wait-native --cases C0,C1,C4,C8,C9 --seeds 1701 --tag d02`. Waits for the native original pair to finish, then runs10 development episodes.
- **`42768`**: archive_candidate.py waiting for d02; archives exact sources, checks unchanged through completion, then analyzes.

Session IDs may not transfer to a different agent. Inspect process command lines
and output files before starting anything. Sandbox process listings may not see
escalated processes. Original runner prints progress to its tool session; each
run also has python.log/unity.log. Do not kill the user's editor or broad Python
processes. The original exact stop command, if necessary, is
`pkill -INT -f '^python3 Tools/kalman_study/run_study.py --no-build$'`.
It preserves completed runs but leaves the interrupted run partial. Preserve any
partial directory under a clearly named diagnostics location before resuming;
the runner deliberately refuses to overwrite partial outputs.

## Essential commands

```bash
python3 Tools/kalman_study/progress.py
python3 -m unittest discover -s Tools/kalman_study -p 'test_robust*.py' -v
python3 Tools/kalman_study/analyze_robust.py Experiments/KalmanStudy/robust_development/d01 --allow-partial
```

The last command requires d01/manifest.json to exist (created after the wait).
Do not interpret an incomplete pair as a final matrix.

## Original v2 study: frozen, do not edit its dependencies

Data: `Experiments/KalmanStudy/v2/`, manifest lists all 60 jobs and hashes.
Raw experiment trees are gitignored deliberately; they still exist on disk.
Unity work/build: `/tmp/usv-kalman-study/project` and
`/tmp/usv-kalman-study/build/study.x86_64`.

**While it is running, DO NOT change** root `Assets/usv/vision.py`, `control.py`,
`config.py`, `kalman.py`, `helpers.py`, `state.py`, the detector checkpoint,
`Documentation/KalmanStudy/PROTOCOL.md`, or these frozen harness files:
`run_study.py`, `bridge.py`, `study_runtime.py`, `StudyRig.cs`, `StudyRain.cs`,
`StudyRain.shader`. The patch generator re-reads root Python each episode.
Other listed water/physics source hashes are frozen too (see manifest).

Design: 10 Hz synchronous images/control, native 1280x720 JPEG70, fixed 0.02s
physics, adapted detector `best_realistic.pt`, 5s stationary calibration then
60s motion, analysis t15–60, weather starts t12. Four real detector cameras,
front JPEGs saved every tick, detector outputs/selection/control/GT logged.
GT masks/world poses are evaluation-only; **existing leader-speed and ego-motion
telemetry remain in the production controller**. This is not purely camera-only.
Normal graphics is required; batchmode rendered black water in a rejected pilot.
Manual keyboard axes are zeroed in the private SimpleMove copy; force/wake code
is preserved. Normal application startup is replaced by the synchronous harness.
Scene actuator throttle ramp remains enabled in the primary study; actual app
startup disables it. Read CLARIFICATIONS.md; do not pretend these plants match.

Cases (all seeds1701,1702,1703):
C0 calm circle (sea.55 R360); C1 huge waves (sea3, realized Hs proxy~2.6m);
C2 heavy rain (.9sea, rain1 fog.032); C3 dark storm (sea1.5 rain1 fog.02);
C4 R180 turn with 2s scheduled measurement suppression;
C5 variable speed/S-turn sea1 rain.4 fog.01 and 2s suppression;
C6 rough sea1.2 rain.5 R220 with .5s suppression;
C7 unseen turn inside a single8s suppression (negative control).
Suppression starts motion20, repeats18s except C7. It is applied AFTER YOLO;
raw detections remain logged. It is not physical optical occlusion.
Arms on/off all cases=48, off_matched (same3s lifetime) C4/5/6=9,
on_short (.6s lifetime) C4=3. Total60.

Original v1 and rejected pilots are preserved diagnostics, not pooled with v2.
Corrected duplicate pilot has identical planar poses, but only281/301 image
batches exactly match and297/301 detection batches match. Do not claim perfect
visual determinism. Only three nearby seeds per original case is limited evidence.

Current completed original means (lower RMSE is better):
C0 OFF4.85m ON4.97m, ON wins1/3;
C1 OFF8.43m ON52.22m, ON wins0/3;
C2 OFF378.36m ON362.64m, ON wins2/3;
C3 OFF368.65m ON380.82m, ON wins1/3;
C4 OFF206.32m ON253.05m, ON wins0/3;
C5 OFF127.61m ON157.99m, ON wins1/3;
C6 OFF425.35m ON392.22m, ON wins2/3;
C7 OFF287.35m ON235.69m, ON wins3/3.
Even the positive relative changes in severe-visibility cases do not represent
maintained formation; absolute errors remain enormous. Full matrix is in MATRIX.md.
C1 seed1701 ON130.92m vsOFF10.23m is an important catastrophic counterexample.
Rain/darkness often cause almost continuous visual loss, beyond any3s coast.
C5 also has very low detection availability; do not label it a clean2s-loss test.

`finalize_legacy.py --wait` automatically runs, after completion:
1. archive all manifest-hashed original files under v2/source_snapshot;
2. analyze.py (matrix/run CSV+JSON), audit_study.py (frame hashes/source checks);
3. matched replay of old production predictors with conda Python;
4. make_figures.py (matrix, traces, weather, fixed-middle-seed and all-seed extrema
   keyframes, paired videos C4/C5/C7).
Check `Documentation/KalmanStudy/legacy-finalization.complete` and tool output.
If a stage fails, fix the reporting/audit tool and rerun it, preserving raw data.
Do not change production before the snapshot/audit completes.

## Replacement candidate d01

Files: `robust_tracker.py`, `robust_hooks.py`, `run_robust.py`,
`test_robust_tracker.py`, `test_robust_adapter.py`, `replay_robust.py`,
`analyze_robust.py`, `make_robust_figures.py` in Tools/kalman_study.
Docs: ROBUST_DEVELOPMENT.md, IMPLEMENTATION_FINDINGS.md, STATISTICAL_POLICY.md.

Genuine adaptive constant-velocity KF on normalized offset + log area, 2x2
position/rate covariance blocks, time-integrated continuous white-acceleration Q,
Joseph covariance update, confidence-scaled R, Huber weighting, adaptive noise,
bounded velocities, one propagation timestamp. EMA comparator has common raw
inputs/log-area representation/rate bounds/coast damping/3s lifetime/age-based
confidence. No new sensors or GT. Both new arms disable legacy KF-only approach
D throttle subtraction and alpha boost; both present their posterior to control.
Thus newON vs newOFF is an estimator contrast; newON vs originalOFF is a full
pipeline comparison and must not be described as an isolated mathematical KF gain.

The running d01 batch is C0/C1/C4/C5 seed1701, 8 runs60s. It reuses the exact
legacy Unity binary, handshake47510, private Python `/tmp/usv-robust-study`.
**Do not change candidate/harness/root code while d01 is executing.** Root files
are read each run by the legacy patch generator it delegates to. The runner only
checks hashes at start; the researcher must respect the freeze during execution.
The original and replacement batches share private legacy UDP listener ports,
so do not run them concurrently. The resumed runner is the only active Unity study; do not duplicate it.

Development replay on original OFF trajectories improved fresh horizontal
tracking accuracy, but missing-frame results are mixed (huge-wave missing RMSE
.0204 KF vs.0152 EMA). This is NOT closed-loop evidence or held-out validation.
C0 fresh .0016 KF vs.0044 EMA; C1 fresh .0042 vs.0091; preliminary C4 fresh.0063
vs.0119. New tracker unit and adapter tests currently7/7 pass; including GUI toggles during loss without inventing a measurement.

Known legacy issues documented: double propagation at reacquisition, Q per update
rather than elapsed time, noisy pixel-area rate injection, KF-only braking,
GUI runtime flag not controlling static controller KF condition, raw Euler yaw
ambiguity under waves, stale throttle attenuation causing loss/reacquisition
cascade. Fixes must not silently rewrite historical experiments.

## Latest replacement development findings (update from results.json)

C0seed1701 matched EMA OFF5.08m vs robust KF ON4.88m, +4.0% reduction.
C1seed1701 matched EMA OFF10.79m vs robust KF ON9.54m, +11.6% reduction.
C4 matched EMA OFF253.36m vs KF ON258.82m, -2.2%.
C5 matched EMA OFF91.10m vs KF ON130.81m, -43.6%.
D01 is complete8/8 and its source-freeze check passed. Its archived sources
include the original failed import launch diagnosis/dependency-fix supplement.
These are ONE DEVELOPMENT seed each, not held-out or proof of significance.
The unchanged common stale-target throttle/steering attenuation remains a
major limitation. D02 is now queued with a common confidence-aware short-loss
control policy for BOTH ON and OFF. Read ROBUST_D02.md and
shared_coast_policy.py. It preserves the d01 estimators, tapers stale attenuation
according to the SAME age-based confidence in both arms, and includes disclosed
C8/C9 clear-weather motion cases. Candidate-amendment.json supplements the
inherited manifest description; new wrapper/scenario/policy/doc hashes are included.
Do not claim removing a shared controller defect proves Kalman alone helps.
Do not change d01 sources before its freeze check finishes, or root files while
the queued original native-app check is using them.

## Critical evaluation metadata correction

Read COORDINATE_CORRECTION.md. The frozen720p StudyRig.IdBoxes still serialized
`y=359-y1` instead of719-y1. Every raw GT box y is therefore360px too small.
RGB, YOLO/control, physics, world-pose RMSE and triangle IoU are unaffected.
`analyze.load` now adds360 in memory, retains `_raw_y`, and never rewrites raw
logs. Identity-match statistics and camera overlays have been regenerated through
this reader. Audit now passes corrected box bounds and records the correction.
The same old binary is reused in d01, so it needs the same reader correction.
Any future corrected binary MUST set job id_box_encoded_y_origin=719 to avoid
applying the correction twice. Native-app observer already uses height-1 and
must NOT receive this correction. Two regression tests verify the conversion
and preservation of raw JSONL. The corrected overlay was visually inspected.

## Additional tools prepared

`infer_robust.py` implements whole-seed-block log-RMSE aggregation, an exact
two-sided sign-flip test and seeded bootstrap. Three inference fixture tests pass
(12 tests total including tracker/adapter and metadata regression). These fixtures are synthetic test
data, not experimental evidence. It must only be used with the prospectively
frozen evaluation cases/seeds; its CLI alone does not prove preregistration.
CPU/controller dependency metadata are in environment-*.json.

## Prepared integration draft (NOT applied)

`python3 Tools/kalman_study/prepare_integration.py` generates a reviewable patch
and staged files under `/tmp/kalman-integration-review`. This includes variant
selection, runtime ON/OFF correction and a robust tracker reset on reconnect.
Production is unchanged. Do not apply it before candidate validation and the
original study snapshot/audit; native-app validation is still required afterward.
The draft is d01-specific and must be regenerated/reviewed if the candidate or
shared controller changes.

## Next work (not done)

1. Original matrix and d01 are complete and audited; let the queued native
   check and d02 finish and inspect all outcomes, including failures. Confirm original figure/video
   generation completes and inspect actual images before claiming delivery.
2. If d01 underperforms, develop another tagged candidate using ONLY development
   seeds1701–1703. Preserve d01 sources and raw runs before changing files.
   In particular inspect stale-target throttle/steer reductions: even a good
   prediction currently loses speed because stale throttle is multiplied by.65.
   A common controller change can be justified, but give OFF the same policy and
   attribute improvement honestly. Do not make OFF artificially weak.
3. The original rain cases can be nearly unobservable. Consider adding a
   **prospectively declared** clear-weather variable-speed/S-turn case (same C5
   motion, rain0) and/or transient lens-rain bursts to study recoverable visual
   loss. Keep impossible original cases and disclose rationale. The C8/C9 definitions now exist in observable_cases.py and their rationale
   is in OBSERVABILITY_AMENDMENT.md; neither has been wired into a runner or
   run yet. Import them only into a new tagged study. Do not retroactively call
   them original prespecified cases.
4. Freeze a replacement evaluation protocol and hashes before unused seeds.
   Proposed fresh seeds (NOT used):2701,2869,3007,3163,3299,3461; choose varied
   directions/phases, not just adjacentseeds. Statistical policy currently names
   C1/C4/C5 as primary family; if adding a more observable C8, explicitly amend
   the protocol before any held-out run and retain C5 as a failure/control.
   Suggested6 primary seed blocks, scenario-balanced log RMSE contrast, exact
   two-sided sign-flip test over64 patterns, bootstrap by whole seed blocks;
   practical target20% geometric RMSE reduction. No guarantee of significance.
   All failed seeds/cases must remain reported.
5. The original asynchronous app check is now QUEUED as session11757; inspect
   its status before launching anything. Command to reproduce after it finishes:
   `python3 Tools/kalman_study/run_actual_app.py --no-build` (approved GUI runner).
   Build already passed using Tools/boat_dataset/USVModelTestRig.cs, real app.main,
   private ports and exactJPEG/hash/ID masks every2s. One originalON/OFF pair,
   R180,2s drops,70s motion. Report separately; its3-boat/equilateral metric
   differs from primary follower-only RMSE. See REALTIME_CHECK.md.
6. After stronger candidate passes meaningful closed-loop evaluation, integrate
   into production with a legacy variant option and correct runtime ON/OFF flag
   behavior. Preserve archived original sources and make sure the test runner
   no longer rereads changing root files. Do NOT deploy an unvalidated candidate.
   Native app smoke/behavior test needed for replacement too.
7. Produce final report, both matrices, uncertainty/limitations, keyframes tied
   to predefined loss times, all-seed harmful extrema, raw/audit index and exact
   reproduction commands. Inspect figures/images. Final answer must say what
   actually improved and what failed; do not claim universal victory or realism.

## Environment / practical notes

Unity: `/home/stanley/Unity/Hub/Editor/2022.3.62f3/Editor/Unity`.
Python ML: `/home/stanley/miniconda3/envs/unity_boat/bin/python` (CUDA ultralytics).
Checkpoint spelling is **best_realistic.pt** (not earlier best_realisitc.pt).
Workspace and/tmp writable; GUI/GPU launch scripts require escalation. Existing
approved prefixes include run_study.py, run_robust.py, run_actual_app.py,
boat_dataset/generate_dataset.py. No user Slack/email/publishing authorization.
Do not spawn subagents unless user/applicable instructions explicitly authorize.
Keep user informed; no claims of completion while experiments remain pending.
