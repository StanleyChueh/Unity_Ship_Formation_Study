# Kalman formation study: frozen confirmatory protocol

Purpose: measure whether the existing Kalman-enabled system improves formation
holding, where it helps, and where it fails. A positive result is not assumed.
No Kalman tuning is allowed after comparing confirmatory ON/OFF results.

## Experimental unit and comparisons

Each complete simulated episode is one experimental unit. Pair ON and OFF by
scenario and seed (1701, 1702, 1703). All three seeds are reported; frames and the
two followers are not independent experimental replicates. Use paired descriptive
effects and seeded bootstrap intervals, with the small number of replicates made
explicit. Do not claim a real-world effect from this simulator alone.

Eight cases: calm circle; huge waves; heavy rain; dark/rain storm; tighter turn
with two-second scheduled bbox losses; variable speed/S-turn with two-second
losses; brief half-second losses under rough water; an unexpected turn inside an
eight-second loss as a negative control. All cases use the same adapted detector.

Primary arms use the existing Kalman ON/OFF behavior. Additional OFF-with-matched
three-second-hold episodes in the two-second and brief-loss cases isolate some
benefit due to the longer hold window. ON-with-short-hold in the tighter-turn
case checks the reverse ablation. The production flag also gates approach braking
and confidence behavior; the primary contrast is a complete software-system
ablation, not a mathematical proof about the Kalman equations in isolation.
Matched observation replay is reported separately to examine estimator error.

## Timing, control and ground truth

Use a synchronous 10 Hz image/control handshake and fixed physics steps. Unity
waits after rendering until the real production vision processing and control
functions complete. Python estimator/control timestamps use simulation time.
This avoids comparing different wall-clock detection cadences. The normal GUI,
socket scheduling and startup loop are replaced only in the isolated harness.
The detection selection, EMA preprocessing, Kalman/coasting and control functions
are unchanged apart from a documented coasting-window ablation.

GPU benchmark autotuning/TF32 are disabled equally in all arms after the normal
runtime setup, and camera-batch publication is barrier-synchronized. Preliminary
pilots exposed small confidence differences when the production runtime re-enabled
GPU autotuning; those diagnostics are retained outside confirmatory runs.

The final study is version v2. Version v1 is retained as diagnostics because
manual keyboard movement handlers had not been neutralized. In v2 only the
isolated SimpleMove keyboard-axis reads are replaced by zero; motor forces,
wake-effect updates and the Python control policy are unchanged. Normal graphics
mode is required: the water plugin rendered a black surface in the attempted
batch-mode pilot, which is retained under `pilots_batchmode_unsupported/`.
That invalid pilot was rejected before comparisons. Confirmatory results are
not pooled with v1. No comparison-based Kalman tuning was performed.

Capture at the scene's native 1280x720 and JPEG quality 70, with YOLO inference
size 640 unchanged. An initial 640x360 pilot changed the pixel-area scale and
failed even in calm conditions. It is preserved under
`pilots_resolution_mismatch/` and excluded as an instrumentation error. The
corrected repeatability pilots precede all confirmatory comparisons.

There is a common five-second stationary calibration period. Leader motion then
starts on a fixed schedule, and weather changes after 12 seconds of motion.
Analysis starts after 15 seconds of motion; each episode lasts 60 seconds of
motion. Scheduled loss begins at 20 seconds and repeats every 18 seconds, except
the long-loss negative control, which has one event. Losses are measurement
censorship after YOLO, not a claim of natural optical occlusion. Raw detections
and the censorship mask are retained separately. Natural weather cases have no
scheduled censorship. Failed calibration/runs are reported, not silently excluded.

Both arms receive the same existing leader-speed telemetry and ego-motion data.
Ground-truth relative positions and ID masks are evaluation-only. Leader speed
feedforward means this is a vision controller assisted by speed telemetry, not
a claim of entirely camera-only navigation during blackouts. The leader follows
an identical prescribed motion per case; follower trajectories may diverge.

Weather is visually rendered before inference. Waves use the shared physical and
visual ocean. Rain is a synthetic image/visibility model, not a validated rain
sensor or hydrodynamic model. Darkness changes scene illumination/sky; no claim
of calibrated real camera exposure is made. Nominal ocean amplitude is not
reported as measured significant wave height: surface-height samples and hull
attitude are logged to characterize realized severity. Weather seeds are paired,
although follower-mounted views naturally differ after trajectories diverge.

## Outcomes and evidence selection

Primary: follower position RMSE in metres relative to the fixed initial offsets
rotated with the leader heading, averaged over the analysis window. Secondary:
triangle IoU, 95th/maximum position error, fraction of time formation RMS exceeds
10 m, minimum separation, fresh/missed/stale observations, steering/throttle
variation, loss-window error and post-loss recovery. Report mean paired absolute
and percentage changes, seed-level values and counterexamples.

For recovery, compare with the pre-loss two-second median error plus 2 m, requiring
one continuous second below that threshold. Mark unrecovered events as censored
after ten seconds rather than assigning an invented recovery time.

Keyframe times are tied to predefined loss start, middle, end and recovery.
Additionally show the largest positive and negative ON/OFF error differences,
explicitly labeled as extrema, not representative averages. Use paired raw camera
images, measured/predicted boxes and ground-truth formation/error traces. Include
all raw per-step logs, scenario configs, code/model hashes and reproduction steps
for an independent audit. A same-seed duplicate pilot checks repeatability before
confirmatory comparisons. Pilots verify instrumentation; they are not pooled into
the confirmatory matrix.
