#!/usr/bin/env python3
"""Run your own scenario, isolated from the study (NOT part of any study data).

Uses a separate private project (/tmp/usv-user-play), port 47600 and output folder
Experiments/KalmanStudy/user_play/, so it can run while a study batch is running
without touching its files. Shares only the read-only simulator binary and model.

Examples:
  python3 Tools/kalman_study/play_case.py --sea 3.0 --motion variable --gap 2 --arms on,off_short
  python3 Tools/kalman_study/play_case.py --rain 1.0 --fog 0.032 --sea 0.9 --arms on
  python3 Tools/kalman_study/play_case.py --dark --rain 1.0 --fog 0.02 --sea 1.5 --arms on
"""
import argparse
import fcntl
import json
import math
from pathlib import Path
import time

import run_candidate as rc
import run_robust as base
from analyze import load, traces, summary

WORK = Path('/tmp/usv-user-play')


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--sea', type=float, default=0.55, help='large-wave height: 0.55 calm, 1.0-1.5 rough, 3.0 huge (C1/C10)')
    p.add_argument('--rain', type=float, default=0.0, help='rain overlay 0..1: 0.15 intermittent, >=0.25 detector mostly blind, 1.0 heavy (C2)')
    p.add_argument('--fog', type=float, default=0.0, help='fog density (exp^2): 0.008 light, 0.032 heavy (C2)')
    p.add_argument('--dark', action='store_true', help='night/storm lighting (detector ~blind in development)')
    p.add_argument('--motion', choices=['circle', 'variable', 'unexpected'], default='circle',
                   help='circle = constant 18 m/s turn; variable = speed 14/20/10/18 m/s + S-turn; unexpected = straight then sharp turn at 22 s')
    p.add_argument('--radius', type=float, default=360, help='turn radius for circle motion (m); 180 = tight (C4)')
    p.add_argument('--gap', type=float, default=0.0, help='scheduled bbox suppression length (s), at 20, 38, 56 s; 0 = none')
    p.add_argument('--seed', type=int, default=4001, help='wave direction / rain pattern seed')
    p.add_argument('--duration', type=int, default=60, help='seconds of leader motion')
    p.add_argument('--arms', default='on,off_short', help='comma list of: on (KF d02), on_ego (KF+ego), off (EMA 3 s), off_short (production OFF)')
    p.add_argument('--name', default=None, help='output folder name prefix')
    a = p.parse_args()
    WORK.mkdir(exist_ok=True)
    lock = open(WORK/'lock', 'w')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise SystemExit('Another play_case.py is running; run one at a time.')
    base.WORK = WORK
    base.legacy.WORK = WORK
    base.legacy.patch_python = rc.patch_python
    rc.prepare()
    name = a.name or time.strftime('%m%d_%H%M%S')
    case = dict(case=f'U_{name}', sea=a.sea, rain=a.rain, dark=a.dark, fog=a.fog, motion=a.motion, radius=a.radius, gap=a.gap)
    out = base.ROOT/'Experiments/KalmanStudy/user_play'
    rows_out = []
    for arm in a.arms.split(','):
        assert arm in rc.ARMS, arm
        job = dict(case, seed=a.seed, arm=arm, duration=a.duration, port=47600, output=str(out/f'{name}_{arm}'))
        print('RUN', arm, '-> watch the 640x360 simulator window; frames saved to', job['output']+'/frames', flush=True)
        base.legacy.run(job)
        rows = load(job)
        s = summary(job, rows, traces(rows, job))
        rows_out.append((arm, s))
    print('\nResult (motion t=15..end; error relative to the formation slot):')
    print(f'{"arm":10s} {"RMSE m":>8s} {"IoU":>6s} {"broken>10m %":>13s} {"fresh %":>8s} {"lost %":>7s}')
    for arm, s in rows_out:
        print(f'{arm:10s} {s["rmse_m"]:8.2f} {s["mean_iou"]:6.3f} {s["broken_pct"]:13.1f} {s["fresh_pct"]:8.1f} {s["lost_pct"]:7.1f}')
    (out/f'{name}_summary.json').write_text(json.dumps([dict(arm=a_, **{k: v for k, v in s.items() if k != 'events'}) for a_, s in rows_out], indent=2))
    print('\nView frames:  eog', out/f'{name}_{rows_out[0][0]}'/'frames')


if __name__ == '__main__':
    main()
