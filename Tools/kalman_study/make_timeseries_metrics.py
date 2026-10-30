#!/usr/bin/env python3
"""Production-format "Time-Series Metrics" figures for study rollouts.

Replays each run's logged per-step controller results (the same `res` dicts the
production app feeds its metrics logger) through the UNCHANGED production
`usv.app.RunMetricsLogger` on simulation time (released at motion t = 0, snapshot
every 5 s, cumulative statistics exactly as in the app), then plots with the
UNCHANGED production `usv.plot_snapshots.plot_snapshots`. Output paths are
redirected so nothing is written to the production experiment_metrics folder.
Run with the unity_boat Python and PYTHONDONTWRITEBYTECODE=1.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'Assets'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from usv.app import RunMetricsLogger          # noqa: E402  production code, unchanged
from usv import plot_snapshots               # noqa: E402  production code, unchanged
from make_rollout_videos import CASES, run_dir, ARMS   # same fixed seed rule as the videos

KF_ON = {'on_rs'}
TITLE = dict(on_rs='Kalman ON', off_short='Kalman OFF (production)', off_rs='Non-Kalman EMA filter',
             raw='No tracker filter', raw_nogate='No bbox filtering')


def replay(run, out_dir, arm):
    job = json.loads((run/'job.json').read_text())
    name = f'{job["case"]}_seed{job["seed"]}_{arm}'
    logger = RunMetricsLogger(report_interval_sec=5.0)
    logger.output_dir = str(out_dir)
    logger.run_id = name
    logger.snapshots_csv_path = str(out_dir/f'{name}_snapshots.csv')
    logger.summary_csv_path = str(out_dir/'_summaries_unused.csv')
    Path(logger.snapshots_csv_path).unlink(missing_ok=True)
    logger._ensure_output_files()
    started = False
    kf = arm in KF_ON
    with open(run/'steps.jsonl') as f:
        for line in f:
            row = json.loads(line)
            now = float(row['t'])          # motion time; followers released at t = 0
            if now < 0:
                continue
            if not started:
                logger.started_at = logger.last_report_at = logger.kalman_last_time = now
                started = True
            logger.update_kalman_state(kf, now)
            logger.update('Left', row['controls']['Left'], now)
            logger.update('Right', row['controls']['Right'], now)
            if logger.should_report(now):
                logger.write_periodic_snapshot(now, kf, fps=10.0)
    rows = plot_snapshots.read_snapshots(logger.snapshots_csv_path)
    plot_snapshots.plot_snapshots(rows, f'{job["case"]} seed {job["seed"]} · {TITLE[arm]}', str(out_dir/f'{name}_timeseries'), formats=('png',))
    return name


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', type=Path, default=ROOT/'Documentation/KalmanStudy/REPORT_PACKAGE/timeseries_metrics')
    ap.add_argument('--only', default=None)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    for case, seed in CASES:
        if a.only and case.split('_')[0] not in a.only.split(','):
            continue
        for arm, _, _ in ARMS:
            d = run_dir(case, seed, arm)
            if d is None:
                print('missing', case, seed, arm, flush=True)
                continue
            print('wrote', replay(d, a.out, arm), flush=True)
    Path(a.out/'_summaries_unused.csv').unlink(missing_ok=True)
    # Production overlay script: Kalman ON vs production Kalman OFF only (it labels its inputs ON/OFF).
    compare = a.out/'compare_kalman_on_vs_off'
    compare.mkdir(exist_ok=True)
    import os
    import subprocess
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    for case, seed in CASES:
        if a.only and case.split('_')[0] not in a.only.split(','):
            continue
        on = a.out/f'{case}_seed{seed}_on_rs_snapshots.csv'
        off = a.out/f'{case}_seed{seed}_off_short_snapshots.csv'
        if on.exists() and off.exists():
            sub = compare/f'{case}_seed{seed}'
            sub.mkdir(exist_ok=True)
            subprocess.run([sys.executable, '-m', 'usv.plot_compare_snapshots', '--kalman-on', str(on), '--kalman-off', str(off),
                            '--output-dir', str(sub), '--formats', 'png'], cwd=ROOT/'Assets', env=env, check=False,
                           stdout=subprocess.DEVNULL)
            ok = any(sub.glob('*.png'))
            print('compared' if ok else 'COMPARE FAILED (re-run the loop in build_report_package.sh)', case, seed, flush=True)


if __name__ == '__main__':
    main()
