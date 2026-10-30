#!/usr/bin/env python3
"""Run a frozen evaluation batch concurrently with another (Amendment A2).

Identical to run_candidate.py (unchanged, hashed) except for execution plumbing:
a separate private project (--work) and bridge TCP port (--port), so two batches
never share patched Python files or a socket. Cases, arms, seeds, sources and
binary are unchanged; the port actually used is recorded in each job/manifest.
The scene's idle UDP listeners (47600+) bind with address reuse on Linux and
receive nothing in study mode; every run's unity.log is checked for bind errors.

  python3 Tools/kalman_study/run_parallel_batch.py --work /tmp/usv-eval-b --port 47530 -- \\
      --stage evaluation --tag e01b --protocol Documentation/KalmanStudy/eval_e01b_protocol.json
"""
import argparse
from pathlib import Path
import sys

import run_robust as base
import run_candidate as rc

parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
parser.add_argument('--work', type=Path, required=True)
parser.add_argument('--port', type=int, required=True)
args, rest = parser.parse_known_args()
if rest and rest[0] == '--':
    rest = rest[1:]
assert args.port not in (47500, 47510, 47520, 47600), 'port used by another batch/tool'
base.WORK = args.work
original_plan = rc.plan


def plan(*a, **k):
    jobs = original_plan(*a, **k)
    for job in jobs:
        job['port'] = args.port
    return jobs


rc.plan = plan
sys.argv = [sys.argv[0]]+rest
rc.main()
