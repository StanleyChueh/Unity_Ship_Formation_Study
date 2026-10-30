# Native application: original Kalman descriptive check

One asynchronous ON/OFF pair; use the original application metric, not the fixed-step follower-only RMSE.

| Arm | Original3-boat mean RMS m | Formation IoU | Sampled RGB hashes checked |
|---|---:|---:|---:|
| off | 73.27 | 0.412 | 74 |
| on | 93.22 | 0.399 | 74 |

The original ON system was worse in this pair. It does not establish a population effect.

selected-targets.jsonl records the candidate BEFORE scheduled suppression and BEFORE control updates. It must not be presented as the bbox actually used during a suppressed interval.

RGB/identity sampled every2s; asynchronous processing can skip sampled frames. Hash-matched subset is diagnostic, not an unbiased detection-rate estimate.
