# Proposed observable-motion cases — not yet run

During the original frozen matrix, before any replacement closed-loop result,
C5 and C6 showed near-continuous visual loss in rain, even outside their scheduled
suppression windows. They remain reported unchanged. A three-second tracker has
little information with which to recover from that duration of optical failure.

Two new cases are defined in `Tools/kalman_study/observable_cases.py` for a
subsequent explicitly tagged study:

- C8: C5's variable-speed/S-turn motion, sea1.0 and two-second measurement gaps,
  with rain/fog removed. This tests short loss under maneuvers while preserving
  a chance of seeing the leader between events.
- C9: C6's rough sea1.2,220m circle and half-second measurement gaps, with rain/fog
  removed. This is an equal-lifetime brief-gap comparison under camera motion.

They are **post-original-outcome development design changes**, not original
prespecified matrix cases. No performance result exists for them yet. If either
is used in the replacement primary hypothesis, the exact scenario family,
candidate and seeds must be frozen before held-out evaluation. Report C5/C6 as
well; do not hide them or claim C8/C9 demonstrate robustness in continuous heavy
rain. Neither case requires a different renderer/physics binary.

The statistical policy's current C1/C4/C5 primary family is not automatically
changed by this proposal. A later evaluation protocol must explicitly state
whether C8 replaces the nearly-unobservable C5 in the primary family and why.
The original C5 outcome must remain a reported secondary/limit case.
