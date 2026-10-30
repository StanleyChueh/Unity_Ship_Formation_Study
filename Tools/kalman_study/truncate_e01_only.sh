#!/usr/bin/env bash
# Amendment A1 (EVALUATION_PROTOCOL.md): stop e01 after its primary group (runs 1-96),
# preserve the single partial run 97, verify the source freeze, (e01b runs in parallel per Amendment A2).
set -euo pipefail
ROOT=/home/stanley/Github/Unity_Ship_Formation_Study
E=$ROOT/Experiments/KalmanStudy/robust_evaluation
LOG=$E/logs/e01_run.log
cd "$ROOT"
until grep -q '^RUN 97/216' "$LOG"; do
    pgrep -f '^python3 Tools/kalman_study/run_candidate.py --stage evaluation --tag e01 ' >/dev/null || { echo 'e01 runner exited before run 97'; exit 1; }
    sleep 2
done
RUNNER=$(pgrep -f '^python3 Tools/kalman_study/run_candidate.py --stage evaluation --tag e01 ')
kill -INT "$RUNNER"            # KeyboardInterrupt -> run()'s finally terminates Unity and the bridge
while kill -0 "$RUNNER" 2>/dev/null; do sleep 1; done
pkill -f '^python3 Tools/kalman_study/archive_candidate.py Experiments/KalmanStudy/robust_evaluation/e01 ' || true
sleep 3
pgrep -f 'study.x86_64|bridge.py' && { echo 'simulator still running'; exit 1; }
mkdir -p "$E/e01/aborted_truncation"
for d in "$E"/e01/runs/*; do
    if [ ! -f "$d/bridge.complete" ] || [ ! -f "$d/unity.complete" ]; then
        mv "$d" "$E/e01/aborted_truncation/"
        echo "moved partial run $(basename "$d") (Amendment A1)"
    fi
done
python3 - <<'EOF'
import hashlib, json
from pathlib import Path
root = Path('/home/stanley/Github/Unity_Ship_Formation_Study')
data = root/'Experiments/KalmanStudy/robust_evaluation/e01'
m = json.loads((data/'manifest.json').read_text())
changed = [n for n, h in m['source_sha256'].items() if hashlib.sha256((root/n).read_bytes()).hexdigest() != h]
snap = [n for n, h in m['source_sha256'].items() if hashlib.sha256((data/'source_snapshot'/n).read_bytes()).hexdigest() != h]
done = sum((Path(j['output'])/'bridge.complete').exists() and (Path(j['output'])/'unity.complete').exists() for j in m['jobs'])
result = dict(status='passed' if not changed and not snap else 'FAILED', checked_files=len(m['source_sha256']),
              changed_sources=changed, snapshot_mismatch=snap, completed_runs=done, planned_runs=len(m['jobs']),
              truncated_per='EVALUATION_PROTOCOL.md Amendment A1',
              manifest_sha256=hashlib.sha256((data/'manifest.json').read_bytes()).hexdigest())
(data/'source-freeze-check.json').write_text(json.dumps(result, indent=2)+'\n')
print(result)
assert result['status'] == 'passed'
EOF
