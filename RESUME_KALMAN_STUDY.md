# Continue this task

Read [the full handoff](Documentation/KalmanStudy/RESUME.md) first. Its top section
(Claude Code era, 2026-10-29) is current. `Documentation/KalmanStudy/LIVE_STATE.json`
is **stale**: its Codex watcher was stopped; check run directories/logs instead
(`Experiments/KalmanStudy/robust_evaluation/logs/e01_run.log`).

## Prompt to paste into Claude Code or Codex

Continue the Kalman formation research in /home/stanley/Github/Unity_Ship_Formation_Study.
Read Documentation/KalmanStudy/RESUME.md (top section), EVALUATION_PROTOCOL.md and
ROBUST_D03.md, then inspect live processes before launching anything (never start a
duplicate Unity/GPU runner). The held-out evaluation e01 is frozen; let it finish or
resume it with the identical command. Do not change hashed sources, cases, seeds or the
protocol. Then run analysis/inference/figures, write the final audit-ready report with all
results including failures, and update the handoff. Do not claim a Kalman-only benefit
from shared controller changes and do not cherry-pick seeds or cases.
