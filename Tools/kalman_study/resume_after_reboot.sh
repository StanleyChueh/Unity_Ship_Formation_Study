#!/usr/bin/env bash
# Amendment A3: resume e01 (primary, then truncation per A1) and e01b (parallel per A2)
# after the 2026-10-29 shutdown. Completed runs are skipped by the runner; runs that
# were in progress at shutdown are preserved in */interrupted_shutdown/ and re-run.
set -euo pipefail
ROOT=/home/stanley/Github/Unity_Ship_Formation_Study
BACKUP=/home/stanley/usv_study_tmp_backup
E=$ROOT/Experiments/KalmanStudy/robust_evaluation
cd "$ROOT"

if pgrep -f 'run_candidate.py|run_parallel_batch.py|study.x86_64|kalman_study/bridge.py' >/dev/null; then
    echo 'A study runner/simulator is already running; not starting duplicates.'; exit 1
fi
# 1. Restore the frozen simulator build and baseline project (Ubuntu clears /tmp at boot).
for d in usv-kalman-study usv-model-comparison kalman-integration-review; do
    [ -e /tmp/$d ] || { [ -e $BACKUP/$d ] && cp -a $BACKUP/$d /tmp/ && echo "restored /tmp/$d"; }
done
# 2. Verify binary + every frozen source against both manifests (abort on any change).
python3 - <<'EOF'
import hashlib, json, sys
from pathlib import Path
root = Path('/home/stanley/Github/Unity_Ship_Formation_Study')
ok = True
for tag in ['e01', 'e01b']:
    m = json.loads((root/'Experiments/KalmanStudy/robust_evaluation'/tag/'manifest.json').read_text())
    binary = hashlib.sha256(Path('/tmp/usv-kalman-study/build/study.x86_64').read_bytes()).hexdigest()
    changed = [n for n, h in m['source_sha256'].items() if hashlib.sha256((root/n).read_bytes()).hexdigest() != h]
    print(tag, 'binary', 'OK' if binary == m['binary_sha256'] else 'MISMATCH', '| changed sources:', changed or 'none')
    ok &= binary == m['binary_sha256'] and not changed
sys.exit(0 if ok else 1)
EOF
# 3. Relaunch (detached, logs appended). Archivers re-verify snapshots; truncation watcher per A1.
nohup setsid python3 Tools/kalman_study/archive_candidate.py "$E/e01" --wait >> "$E/logs/e01_archive.log" 2>&1 < /dev/null &
nohup setsid python3 Tools/kalman_study/archive_candidate.py "$E/e01b" --wait >> "$E/logs/e01b_archive.log" 2>&1 < /dev/null &
echo "=== resumed $(date) ===" >> "$E/logs/e01_run.log"
nohup setsid python3 Tools/kalman_study/run_candidate.py --stage evaluation --tag e01 \
    --protocol Documentation/KalmanStudy/eval_e01_protocol.json >> "$E/logs/e01_run.log" 2>&1 < /dev/null &
sleep 5
nohup setsid bash Tools/kalman_study/truncate_e01_only.sh >> "$E/logs/truncate_e01.log" 2>&1 < /dev/null &
echo "=== resumed $(date) ===" >> "$E/logs/e01b_run.log"
nohup setsid python3 Tools/kalman_study/run_parallel_batch.py --work /tmp/usv-eval-b --port 47530 -- \
    --stage evaluation --tag e01b --protocol Documentation/KalmanStudy/eval_e01b_protocol.json >> "$E/logs/e01b_run.log" 2>&1 < /dev/null &
sleep 2
echo 'Resumed. Progress:'
echo "  grep -c COMPLETE $E/logs/e01_run.log   (primary target: 96)"
echo "  grep -c COMPLETE $E/logs/e01b_run.log  (target: 28)"
