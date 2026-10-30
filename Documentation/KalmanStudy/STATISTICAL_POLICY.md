# Prospective inference policy for a replacement filter

Written during development, before replacement held-out runs. The candidate and
exact evaluation matrix must be separately frozen after development and before
using unused seeds. This document does not assert that any candidate is effective.

- The experimental unit is a complete scenario/seed episode. The two followers
  and hundreds of frames are repeated observations, not separate replicates.
- Primary replacement comparison: robust KF versus an equal-lifetime non-Kalman
  tracker with shared controller and image preprocessing. Describe the exact
  comparator; do not relabel the old shorter-hold OFF results as equal-lifetime.
- Primary scenario family: huge waves, two-second loss on a turn, and two-second
  loss during speed/S-turn maneuvers (C1, C4, C5). For each fresh seed, average the
  three paired log RMSE ratios, giving each scenario equal weight. Inference
  operates on these independent seed blocks, not on the pooled frames.
- With six fresh seed blocks, use the exact two-sided paired sign-flip test
  (all 64 sign patterns) on the mean block log ratio. Report the exact p-value
  and a seeded bootstrap interval over blocks. The smallest attainable exact
  two-sided p-value is 0.03125; a negative result remains a negative result.
- Translate the aggregate log ratio to geometric RMSE reduction. Also report
  each case, each seed, arithmetic RMSE means, triangle IoU, broken-formation
  fraction, detection availability, scheduled-loss error, recovery and command
  variation. Secondary per-case contrasts are descriptive unless separately
  corrected; do not make eight independent uncorrected significance claims.
- A practically substantial result is predeclared as at least 20% geometric
  RMSE reduction in the primary family, alongside lower formation-break time.
  Statistical significance alone does not establish practical importance.
- Report calm performance and extended unseen-turn/near-total-visibility-loss
  cases as controls/limits. Success in the primary family does not imply every
  weather condition improves or real-world safety is established.
- Preserve all development versions, failures, stopping decisions and hashes.
  If the candidate changes after seeing held-out outcomes, those outcomes become
  development data for the revision. Another evaluation requires new seeds and
  must disclose the sequential development history, rather than replacing files
  or presenting the last successful test as the only test.

Bootstrap intervals with six seed blocks remain limited. The seed distribution
and simulator weather generator define the scope of the experiment; these are
not random samples from all real oceans, cameras or autonomous vessels.
