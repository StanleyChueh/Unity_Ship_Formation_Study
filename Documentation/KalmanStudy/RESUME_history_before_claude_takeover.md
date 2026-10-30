# Claude Code / Codex handoff — START HERE

Checkpoint updated 2026-10-29 12:44:37 CST.
Workspace: `/home/stanley/Github/Unity_Ship_Formation_Study`.

**UNFINISHED. No stronger held-out validation or production deployment yet.**
Read `LIVE_STATE.json` next: a background watcher updates it every10 seconds,
so its run counts may be newer than this prose. The user requests transfer when
Codex has **3% remaining in its five-hour allowance**. The meter reached **3%remaining (97%used)** and Codex stopped active work
at the user-requested threshold. Background experiments are intentionally left running. `QUOTA_HANDOFF_REQUIRED.json`, if present, records the threshold.

## Objective

Improve and fairly evaluate Kalman-assisted boat formation under extreme waves,
rain/darkness and temporary leader bbox losses. Include turns and speed changes,
a full ON/OFF matrix, recovery/formation metrics and camera keyframes showing
where prediction helps **and fails**. The user authorizes designing a stronger
filter after old KF failures. They will have Claude Code audit the result.
Do not fabricate success, cherry-pick seeds/cases, weaken OFF to force a win, or
feed leader world pose/ID masks/future motion into tracking or control.

## Immediate next actions

1. Inspect live state and processes before launching anything. D02 is already
   running; let it finish. Its archiver will check the source freeze and analyze
   all10 runs. Do NOT launch duplicate or concurrent Unity/GPU batches.
2. Inspect all d02 outcomes and its source-freeze-check.json. Develop further
   only using development seeds1701–1703; preserve each previous version/raw data.
3. Select a candidate and freeze a separate held-out protocol, sources, cases
   and unused seeds BEFORE running evaluation. Run enough paired seed blocks;
   report failures and meaningful uncertainty. See STATISTICAL_POLICY.md.
4. Only after validation, integrate into production, test the actual native app,
   produce final matrices/figures/keyframes/report and reproduction commands.
   A d01 integration draft exists but is NOT ready to apply blindly to d02.
5. Update this handoff before stopping. The user explicitly requests seamless
   continuation if quota reaches3%remaining; do not say the task is done.

## Current state and live jobs

- Original v2: **60/60 complete, archived, audited and reported**.
- D01 replacement development: **8/8 complete**, source freeze passed.
- Original asynchronous native app: **both arms complete**, audit passed.
- D02 replacement development: **4/10 complete at transfer**, C4 turning ON
  running. See LIVE_STATE.json for newer counts. No held-out data yet.
- Production `Assets/usv` algorithms/config are still unchanged. All new filter
  code runs in isolated test copies. Root modifications are Tools/Documentation,
  .gitignore and the supplementary model-test observer.

Unified exec IDs (Codex only; another agent must inspect OS processes/files):

| Session | State / command |
|---|---|
|96828|Active d02: `python3 Tools/kalman_study/run_robust_next.py --wait-native --cases C0,C1,C4,C8,C9 --seeds 1701 --tag d02`|
|42768|Active CPU archiver waiting for d02 completion: `archive_candidate.py Experiments/KalmanStudy/robust_development/d02 --wait`|
|7182|CPU quota/checkpoint watcher; writes handoff marker at remaining<=3 and exits|
|6414|Original v2 runner finished exit0|
|41545|Original finalization/audit/figures finished exit0|
|90956|D01 runner finished8/8; inspect session if needed|
|64847|D01 source archival/freeze check/analysis finished exit0|
|11757|Original native-app pair finished exit0|
|63339|Earlier d01 import failed before simulation; preserved diagnostics, corrected|
|88123|Earlier finalization correctly failed on GT coordinate bug; corrected in reader|

Private work:
`/tmp/usv-kalman-study/project`, `/tmp/usv-kalman-study/build/study.x86_64`;
`/tmp/usv-robust-study/project` (d01/d02 Python copies, exact same binary via link);
`/tmp/usv-model-comparison` (separate native-app binary).
The fixed-step batches share some private UDP listener ports. Never overlap them.
Do not stop the user's Unity editor or broad Python processes. Sandbox process
listings may not show escalated processes; use appropriate access to inspect.

## Data, reports and commands

Raw logs/images are gitignored under `Experiments/KalmanStudy/`, NOT missing.

- `v2/manifest.json`: original60 jobs and frozen source hashes.
- `v2/source_snapshot/`: original source/model archive.
- `v2/runs/*`: job.json,651-step steps.jsonl, exact front JPEGs, logs, completions.
- `robust_development/d01/`: manifest, source_snapshot, results.json/MATRIX.md,
  source-freeze-check.json,8 runs, preserved import failure diagnostics.
- `robust_development/d02/`: same structure,10 planned runs;
  candidate-amendment.json documents the new shared coast policy.
- `v2/realtime/`: native original pair, exact sampled JPEG/hash/ID masks,
  motion.csv, selected-targets.jsonl, normal app summaries, protocol-manifest.json.

Main reports in `Documentation/KalmanStudy/`:
MATRIX.md, matrix.csv/json, run-results.csv/json, audit.json,
matched-replay.json, native-app-audit.json, NATIVE_RESULTS.md,
figures/, keyframes/, C4/C5/C7 paired mp4 files, source-copy diffs,
PROTOCOL.md, CLARIFICATIONS.md, IMPLEMENTATION_FINDINGS.md,
ROBUST_DEVELOPMENT.md, ROBUST_D02.md, OBSERVABILITY_AMENDMENT.md,
STATISTICAL_POLICY.md, COORDINATE_CORRECTION.md, environment-*.json.
`legacy-finalization.complete` confirms original reporting completed.

Safe CPU commands while d02 runs:

```bash
python3 Tools/kalman_study/analyze_robust.py Experiments/KalmanStudy/robust_development/d02 --allow-partial
python3 -m unittest discover -s Tools/kalman_study -p 'test_*.py' -v
```

Twelve meaningful tests currently pass: filter time/noise/PSD/outliers/positive
area, adapter timing/reset/toggle during loss, inference fixtures and GT-coordinate
regressions. Fixtures are not experimental evidence. For final replacement figures:

```bash
python3 Tools/kalman_study/make_robust_figures.py Experiments/KalmanStudy/robust_development/d02
```

Requires completed results. These are development figures; do not label held-out.

## Original v2 design and outcomes

10Hz synchronous image/control co-simulation, fixed physics. Native1280x720
JPEG70, YOLO640 and checkpoint **best_realistic.pt** (correct spelling). Four
real camera streams; exact front images saved each tick.5s stationary calibration,
60s motion, analyze t15–60; weather begins motion12. Original production vision
and control functions run in a private copy with clock/barrier/logging changes.
Manual keyboard axes are zeroed only in private SimpleMove. Normal graphics mode
is required; batchmode rendered black water and was rejected before comparisons.
Normal startup/UI/socket scheduling are replaced by the synchronous bridge.
The primary scene actuator throttle ramp is enabled; actual app startup disables
it. Read CLARIFICATIONS.md. Do not pretend the plant/cadence are identical.

World poses/identity masks are evaluation-only. **Existing ego-motion and leader-
speed telemetry are still supplied to the original controller.** This is not a
pure camera-only blackout-navigation claim. Ship positions from telemetry are
not used by the vision control law. The replacement tracker reads only selected
image measurements and detector confidence, plus its own time/history.

Three seeds1701–1703 per case. ON/OFF all8 cases=48 episodes; OFF matched3s hold
C4/C5/C6=9; ON short.6s hold C4=3; total60. Suppression starts motion20, repeats18s,
except the single8s C7 event. It suppresses selection AFTER YOLO; raw detections
remain. It is a scheduled measurement-censorship experiment, not physical occlusion.

|Case|Original OFF RMSE m|Original ON RMSE m|Mean paired reduction|ON wins|
|---|---:|---:|---:|---:|
|C0 calm R360|4.85|4.97|-2.8%|1/3|
|C1 huge waves sea3|8.43|52.22|-441.8%|0/3|
|C2 heavy rain|378.36|362.64|+3.3%|2/3|
|C3 dark storm|368.65|380.82|-2.9%|1/3|
|C4 R180 turn /2s gap|206.32|253.05|-23.0%|0/3|
|C5 variable speed/S-turn rain.4 /2s gap|127.61|157.99|-29.6%|1/3|
|C6 rough water rain.5 /.5s gap|425.35|392.22|+7.7%|2/3|
|C7 unexpected turn inside8s gap|287.35|235.69|+15.3%|3/3|

Positive relative changes with hundreds of metres error still mean formation
failed. The current filter does NOT show a general benefit. C1seed1701 original
ON130.92m vs OFF10.23m is a major counterexample. Realized fixed-probe Hs proxy
4std is~2.6m in C1, not a claim that nominal sea3 equals a calibrated real Hs.
Rain/darkness cause long near-total visual losses, beyond a3s predictor. Rain is
a synthetic image overlay, not a validated physical rain/sensor model.

Primary metrics: follower-only planar RMSE relative to initial offsets rotated
with leader heading; triangle IoU; P95/peak/broken fraction>10m; separation;
fresh/stale/lost; gaps/recovery; control variation. Frames/followers are not
independent replicates. Original3-seed bootstrap intervals are descriptive only.
Old v1/rejected pilots remain diagnostics and are never pooled with v2.
Duplicate corrected pilot has exactly identical planar poses but281/301 image
batches and297/301 detector batches match. Do NOT claim bitwise visual determinism
or overinterpret tiny cross-batch changes of a few percent.

Original audit passed60 jobs/39060 steps/78120 JPEG hashes. Matrix, corrected
bbox overlay, severe-wave all-seed failure sheet and C4 paired sheet were visually
inspected. Keyframes include fixed middle seed1702 AND favorable/harmful extrema
across all seeds, explicitly labeled extrema. Videos show actual camera JPEGs and
GT formation maps; predicted orange marks are horizontal positions, NOT invented
full2D predicted bboxes.

## Critical GT coordinate correction

Read COORDINATE_CORRECTION.md. Frozen720p StudyRig.IdBoxes encoded `y=359-y1`
instead of719-y1. Every raw GT bbox y is360px too small. RGB/YOLO/control/physics,
world-pose RMSE, triangle IoU, x/width/height/pixel counts are unaffected.
`analyze.load` adds360 IN MEMORY, keeps `_raw_y`, and does NOT rewrite raw JSONL.
All identity-match statistics and camera overlays use the corrected reader.
The same binary is reused in d01/d02, so this correction is required there too.
A future corrected binary MUST set job `id_box_encoded_y_origin=719` to avoid a
second correction. Native observer already uses height-1 and must NOT be shifted.
Do not remove the raw frozen source to hide this bug; it is archived and audited.

## Replacement d01 and d02

`robust_tracker.py`: genuine adaptive constant-velocity Kalman tracker on
normalized image offset and log(pixel area), separate2x2 position/rate blocks,
continuous-acceleration Q integrated with actual dt, Joseph covariance update,
confidence-scaled/adaptive R, Huber innovations, bounded velocities and one
propagation clock. This fixes legacy double prediction through a gap on reacquisition.
No new sensors, target GT, future trajectory or case/suppression labels enter it.
`robust_hooks.py` adapts state to production vision interfaces; GUI toggles during
loss change mode without inventing a new observation or extending lifetime.

The matched comparator is EMA+smoothed finite-difference velocity with the same
raw inputs/log-area representation/bounds/coast damping/3s hold/age confidence.
Both arms smooth once and present posterior estimates to the common controller.
Both disable legacy KF-only approach braking/alpha boost. Thus ON vs matchedOFF
is an estimator comparison, whereas comparing a replacement to originalOFF is
a full pipeline upgrade and cannot isolate the Kalman equations.

D01 seed1701 completed8/8 with frozen source check:
C0 EMA5.08 vs KF4.88m (+4.0%);
C1 EMA10.79 vs KF9.54m (+11.6%);
C4 EMA253.36 vs KF258.82m (-2.2%);
C5 EMA91.10 vs KF130.81m (-43.6%).
These are DEVELOPMENT results, not held-out proof. An initial missing import
failed before simulation; preserved in diagnostics/initial_import_failure.
dependency-fix.json records copying top-level depth_Anything.py into the private
Python folder. Depth inference itself is disabled.

D02 preserves the d01 filter/comparator. `shared_coast_policy.py` gives BOTH arms
identical confidence-aware stale throttle/steer attenuation: avoid immediate
0.65/0.85 reductions for a recent credible forecast, fade to original conservative
scales near3s expiry. This addresses a common controller defect. Any improvement
shared by both arms is NOT a Kalman-only gain. `run_robust_next.py` wraps unchanged
d01 files; wrapper/policy/newcase/doc hashes are in its manifest. Do NOT edit
those sources or root runtime files while it executes; source archiver will fail.

D02 planned C0/C1/C4/C8/C9 seed1701 (10 runs). C8 is C5 motion/sea but rain/fog0;
C9 is C6 motion/sea but rain/fog0. These are openly post-original-outcome design
changes, declared before their own results; not original prespecified cases and
not proof of heavy-rain robustness. Original C5/C6 failures remain reported.
C8/C9 are in observable_cases.py. Read their rationale document.

## Native original application check

One descriptive asynchronous pair, actual app.main/TCP/normal startup, R180,
2s gaps every18s from release20,70s motion. OFF73.27m vs ON93.22m in ORIGINAL
3-boat/equilateral RMS; formation IoU.412 vs.399. NOT pooled with primary metrics.
Each side summary repeats the global RMS; it is not another replicate.
NATIVE_RESULTS.md/native-app-audit.json record source/hash checks.74 sampled
RGB images per arm verified;71/72 match exact processed-frame hashes. In matched
pre-suppression selected-box samples,54/52 match leader and0 match another boat.
These sampled subsets are diagnostic, not unbiased detection-rate estimates.
**selected-targets.jsonl records candidates BEFORE scheduled suppression**, not
what control actually used during a suppressed interval. No360px correction here.

## D02 transfer-time interim results (development only)

C0 matched EMA OFF5.08m vs KF ON4.97m (+2.3%).
C1 matched EMA OFF5.50m vs KF ON5.33m (+3.1%).
The large improvement of BOTH arms relative to d01 illustrates the importance
of the shared coast control correction; it is not a Kalman-only gain. C4/C8/C9
were not complete at transfer. No significance or20% practical-benefit claim is
justified. Do not overinterpret tiny single-seed effects/render nondeterminism.

## Further research and integration

Read IMPLEMENTATION_FINDINGS.md: double gap propagation, cadence-dependent Q,
noise scale/velocity injection, KF-only braking, raw Euler-yaw compensation under
waves, GUI runtime flag vs static controller flag, stale-control slowdown cascade.
D01 fixes several but not all system limitations. Do not assume a confident KF can
know an unseen unexpected maneuver during an8s loss or45s blindness.

Proposed unused seeds:2701,2869,3007,3163,3299,3461 (varied directions/phases).
The existing STATISTICAL_POLICY.md defines a scenario-balanced mean log RMSE
ratio per seed,6 seed blocks, exact two-sided sign-flip test over64 patterns,
bootstrap by WHOLE seed blocks, and practical target>=20% geometric RMSE reduction
plus lower formation-break time. infer_robust.py implements this, with tests.
The current primary family there is C1/C4/C5. If substituting observable C8 for
nearly-unobservable C5, explicitly amend/freeze BEFORE held-out runs and retain
C5 as a secondary/limit case. Six nearby deterministic environments are not a
real-ocean population; label inference assumptions and uncertainty.
If a candidate changes after seeing held-out outcomes, that set becomes
DEVELOPMENT for the revision; use new seeds and disclose the sequence. Do not
keep retesting/replacing failures until a desired p-value appears.

`prepare_integration.py` currently generates a **D01-specific unapplied draft**
under /tmp/kalman-integration-review/candidate.patch. Syntax and git apply --check
passed. Includes legacy/robust variant selection, dynamic GUI ON/OFF braking fix,
reconnect reset. Must be updated for d02/selected candidate before applying.
Do not deploy unvalidated code. Archive original sources first (already done),
ensure no running harness rereads changing production sources, test native app
with the chosen replacement, then produce the final audit-ready report.

## Environment / permissions

Unity `/home/stanley/Unity/Hub/Editor/2022.3.62f3/Editor/Unity`.
ML Python `/home/stanley/miniconda3/envs/unity_boat/bin/python` (CUDA ultralytics).
Ordinary system Python handles reports/tests. GUI/GPU runners need escalated
access; prefixes run_study.py, run_robust.py, run_robust_next.py, run_actual_app.py
are approved in Codex. Workspace and/tmp are writable. Do not publish, send
messages or spawn subagents without appropriate user authorization. No git commit
was made; changes remain reviewable. Root .gitignore hides raw experiments and
new Tools bytecode; existing tracked user caches are not intentionally deleted.
