# Implementation clarifications for the audit

The fixed-step matrix is a controlled co-simulation of the production vision,
tracking and control functions, not a bit-for-bit execution of the ordinary
asynchronous app.main startup/UI/socket loop. The following distinctions matter:

- Images and commands advance synchronously at 10 Hz. The normal application
  has asynchronous camera/vision/control cadences. Per-update smoothing and
  coasting behavior can therefore differ; generalization needs the separately
  declared normal-application check.
- The matrix uses the serialized scene actuator plant: follower throttle ramp
  enabled, up 0.65/s, down 1.2/s. The normal application sends startup tuning
  that disables this ramp (`FOLLOWER_THROTTLE_SPEED_RAMP_ENABLE=False`). Both
  matrix arms use the same serialized plant. This difference was found during
  audit inspection; the frozen matrix was not retuned. The supplementary normal
  app check retains its actual startup tuning.
- Primary metrics use planar follower-only RMSE relative to fixed initial
  offsets, not the older app summary's three-boat RMS and equilateral construction.
  Native-app metrics are reported separately and are not numerically pooled.
- The scripted leader's x/z path and speed commands are prescribed; follower
  dynamics, water response and camera motion remain simulated. Broadcast speed
  uses the existing magnitude-of-velocity telemetry, including vertical motion.
- Transparent spray is not an opaque occluder in the evaluation ID masks. A
  boat can have a ground-truth mesh box even when rain/darkness/spray prevents
  YOLO from recognizing it. This separates object presence from detectability.
- The eight-second unseen-turn case is a scripted kinematic negative control;
  it is not a validated model of a particular real boat's turning dynamics.
- Three seeds per matrix case give limited statistical precision. Frame counts
  and two followers are not independent replicates. Bootstrap ranges are
  descriptive; no claim of general statistical proof or real-world robustness
  follows from three repeated simulated episodes.
