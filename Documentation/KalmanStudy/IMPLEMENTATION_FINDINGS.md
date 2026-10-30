# Tracking implementation findings

These are code findings, not claims that a single issue explains every failure.
The original frozen comparisons retain all of these behaviors.

1. **Reacquisition can propagate elapsed time twice.** The legacy update uses
   `current_time - track_prev_measurement_time`, while coasting has already
   propagated using `kf_coast_time`. A later detection can therefore advance the
   state through the missing interval again before correcting it. The new
   estimator has one propagation timestamp.
2. **Process noise depends on update count.** Legacy diagonal Q is multiplied
   by `max(1, dt)`, adding approximately the same uncertainty at 10 Hz and 30 Hz
   per update. The replacement integrates a continuous acceleration-noise model
   with actual dt and includes position/rate cross covariance.
3. **Area noise and rate estimates have inconsistent scales.** Legacy raw pixel
   area shares process-noise settings with normalized offset, and a noisy finite
   difference is injected into the velocity estimate before the Kalman update.
   The replacement uses log area and learns rates through its Kalman correction.
4. **Filter and controller effects are coupled.** The legacy ON flag also enables
   an area-approach throttle subtraction of up to 0.35 and a faster throttle
   smoothing response. Wave/pose-induced bbox growth can resemble actual closing
   motion. The new matched comparison disables these two extras equally; it does
   not attribute their removal to the mathematical filter.
5. **Prediction is not generally the fresh measurement supplied to control.**
   Legacy fresh `target_area` and `target_center_offset` retain the external EMA;
   the Kalman forecast is blended separately. The replacement passes its
   posterior estimate to the common controller, with a small common lookahead.
6. **Stale detections trigger throttle and steering attenuation.** Legacy hold
   length alone cannot guarantee better control: continuing to use a coasted
   target also continues stale-target policy. The matrix includes matched-hold
   ablations; original OFF is not a strong equal-lifetime comparator by itself.
7. **The GUI flag is not the complete controller ablation.** Vision reads the
   runtime KF flag, but the legacy approach-rate damper reads the imported static
   `ENABLE_KALMAN_FILTER` constant. A hotkey OFF run can differ from starting with
   OFF in config. Frozen matrix arms patch config before process launch and
   therefore avoid confusing those two interventions. Production integration
   should fix this discrepancy rather than silently changing historical trials.
8. **Ego yaw telemetry can be misleading under large tilt.** The Unity telemetry
   uses raw Transform Euler Y despite the boat's authored local forward axis and
   hull pitch/roll. The legacy image-velocity compensation uses that value.
   Replacement image-space tracking does not subtract this ad hoc compensation;
   both replacement arms receive the same image measurements and ignore that
   compensation. Own speed and the existing leader-speed feedforward remain in
   the common controller.

Numerical stability and short-loss prediction do not provide information about
an unseen, unexpected maneuver during a long loss. Complete visual failure
requires another sensor, a validated maneuver prior, communications, or a
bounded safe fallback; a more confident Kalman estimate is not a substitute.
