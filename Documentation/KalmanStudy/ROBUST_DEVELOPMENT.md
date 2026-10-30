# Stronger tracker development amendment

The original v2 comparison remains frozen and is retained, including failures.
After the original severe-wave results were inspected, the user authorized a
stronger estimator. Seeds 1701–1703 and the original v2 matrix are therefore
**development evidence for the replacement**, not held-out evidence for it.
The original filter was not changed during its matrix.

## Candidate d01

`Tools/kalman_study/robust_tracker.py` implements a genuine constant-velocity
Kalman estimator for normalized horizontal offset and **logarithmic bbox area**.
It uses independent position/rate covariance blocks, continuous-white-acceleration
process noise integrated with elapsed time, confidence-scaled measurement noise,
Huber innovation weighting, bounded rate estimates, an adaptive measurement-noise
estimate, and a Joseph covariance update. Sustained same-sign innovations raise
process noise to permit maneuvers; alternating residuals increase measurement
noise to reduce wave/detector jitter. Parameters are in the immutable `Tuning`
dataclass. No ground-truth boat position, velocity, identity mask, future path,
scenario label or scheduled-censorship flag enters this estimator.

A single `predict_to(timestamp)` clock owns propagation. This fixes the legacy
integration's reacquisition issue: the legacy filter advances during missing
frames, then can predict the full time since the last *measurement* again when
a new measurement arrives. The candidate propagates only elapsed time since its
last prediction, and applies a correction at reacquisition without repeating
the already propagated interval.

Area is positive by construction. Log area makes relative measurement noise
comparable for large and small boxes, instead of applying a pixel-squared noise
setting independent of box scale. This does not establish an exact geometric
range sensor: boat pose, partial visibility and camera pitch/roll still affect
bbox area. The candidate does not use a new IMU or world-coordinate target sensor.

## Fair comparison

The replacement is compared with a non-Kalman EMA plus smoothed finite-difference
velocity tracker. Both receive the same selected raw bbox measurements, use log
area, common bounds and coast damping, a three-second lifetime, the same
age-dependent confidence rule, and the same controller. Per-camera smoothing is
performed once, inside the respective estimator. Both present their posterior
area/offset to control; the old pipeline usually presents its external EMA and
only blends a portion of the Kalman forecast into control.

The legacy controller's KF-only approach-rate throttle damper and throttle-alpha
boost are disabled **in both new arms**. These changes are explicitly part of
the shared replacement pipeline. A replacement ON vs original OFF contrast
therefore measures a software-system upgrade, whereas replacement ON vs matched
replacement OFF is the estimator contrast. The matched OFF tracker has a genuine
velocity coast; it is not deliberately forced to discard measurements early.
All other control gains, plant, detector, rendering and timing remain as in v2.
The binary is reused and hashed; the Python adapter and raw jobs are archived.

## Development and subsequent evaluation

The first development batch d01 is C0, C1, C4 and C5, seed 1701, 60 seconds per
arm. It is queued after the frozen original matrix to avoid competing GPU jobs.
Development outcomes can motivate a new candidate/tag, but no completed batch
will be overwritten. A separate evaluation protocol and immutable hashes will
be written before any replacement closed-loop evaluation on unused seeds.
Neither a chosen parameter nor a significant benefit is assumed in advance.

Numerical tests cover continuous process-noise time-step partition consistency,
positive semidefinite covariance, outlier influence after a converged track,
positive area, increasing coast uncertainty and no repeated propagation at
reacquisition. These checks verify implementation properties, not formation
performance. Matched-input development replay is observational and does not
replace closed-loop trials.

The process-noise convention follows the [FilterPy continuous white-noise
model documentation](https://filterpy.readthedocs.io/en/latest/common/common.html).
The covariance correction uses the [Joseph form shown in FilterPy's Kalman
implementation](https://filterpy.readthedocs.io/en/latest/_modules/filterpy/kalman/kalman_filter.html).
The adaptive robust extensions are this project's implementation, not a claim
that they reproduce a published optimal robust filter.
