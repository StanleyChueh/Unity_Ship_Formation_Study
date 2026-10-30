# Development d02: common short-loss control correction

Written after d01 development results, before d02 execution. This is development,
not held-out validation. Original v2 and d01 outcomes/sources remain archived.

D01 did not solve the two-second turning loss. Even with an age-credible track,
the shared old controller immediately multiplied throttle by0.65 and steering
by0.85. The resulting speed/direction error could grow until the leader's box
fell below the detector selection area cutoff and was not reacquired. This is
a control-policy defect that better filter equations alone cannot remove.

D02 preserves the exact d01 KF and EMA estimators. **Both arms** now use the
same confidence-aware coast policy: blend the original stale attenuation scales
back toward1.0 while the common age-based prediction confidence is high, then
return to the original conservative scales near the unchanged3s expiry.
The controller still uses the forecast, existing leader-speed telemetry and
ordinary blind fallback after expiry. It receives no target world pose or future
trajectory. The estimator contrast remains KF vs matched EMA under this common
policy. Improvements shared by both arms are attributed to the controller fix.

The planned first batch is C0, C1, C4, C8 and C9, seed1701,60s per arm (10 runs).
C8/C9 are the disclosed clear-weather counterparts to nearly-unobservable C5/C6;
see OBSERVABILITY_AMENDMENT.md. Continuous heavy rain/darkness failures remain
reported in original v2 and are not reinterpreted as successes.

Runner: run_robust_next.py wraps the unchanged run_robust.py, adds the two case
definitions and patches shared_coast_policy.py into the private controller. It
also copies the necessary top-level depth_Anything.py import dependency; depth
inference itself is disabled. The wrapper and these sources are hashed. A
candidate-amendment.json supplements the inherited manifest's d01 description.

D02 is queued after the already-queued native-app original pair. No concurrent
Unity/GPU batches are intended. Do not tune or edit these files while d02 runs.
Select/freeze a separate evaluation only after inspecting all development data.
