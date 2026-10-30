#!/usr/bin/env python3
"""Detector v1 (best_realistic.pt: e03_laps / e04_wlaps) vs detector v2 (best_realistic_v2.pt,
weather-trained: e05_weather_v2) on the same weather laps, seeds and methods.

Per case x method: mean over both seeds (4903, 5021) of formation RMSE, broken time, triangle
IoU and fresh leader detection, metrics over t = 15 s -> end. Writes DETECTOR_COMPARISON.md/.csv
and dumbbell figures (hollow = v1, filled = v2) into REPORT_PACKAGE/weather_v2_detector/.
"""
import csv
import json
import os
from pathlib import Path
os.environ.setdefault('MPLCONFIGDIR', '/tmp/robust-study-plots')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
EV = ROOT/'Experiments/KalmanStudy/robust_evaluation'
OUT = ROOT/'Documentation/KalmanStudy/REPORT_PACKAGE/weather_v2_detector'
ARMS = [('on_rs', 'KALMAN ON'), ('off_short', 'KALMAN OFF'), ('raw_nogate', 'NO bbox filtering')]
COLOR = dict(on_rs='#1baf7a', off_short='#2a78d6', raw_nogate='#e87ba4')
INK, MUTED, GRID = '#262624', '#6b6a63', '#e4e3dc'
METRICS = [('rmse_m', 'Formation RMSE (m)', '.2f', False),
           ('broken_pct', 'Formation broken, error > 10 m (% time)', '.1f', False),
           ('mean_iou', 'Triangle IoU (0-1)', '.3f', True),
           ('fresh_pct', 'Fresh YOLO leader detection (% frames)', '.1f', True),
           ('recovery_s', 'Recovery after a 2 s bbox dropout (s, recovered dropouts only)', '.1f', False),
           ('unrecovered_pct', 'Dropouts not recovered within 10 s (%)', '.0f', False)]


def runs(batches):
    out = []
    for b in batches:
        p = EV/b/'results.json'
        if p.exists():
            out += json.loads(p.read_text())['run_results']
    for r in out:   # scheduled-dropout recovery (L laps only; WL laps have no scheduled dropouts)
        ev = r.get('events') or []
        rec = [e['recovery_confirmed_s'] for e in ev if not e['recovery_censored']]
        r['recovery_s'] = float(np.mean(rec)) if rec else None
        r['unrecovered_pct'] = 100.0*sum(e['recovery_censored'] for e in ev)/len(ev) if ev else None
    return out


def mean(recs, case, arm, key):
    v = [r[key] for r in recs if r['case'] == case and r['arm'] == arm and r[key] is not None]
    return (float(np.mean(v)), len(v)) if v else (None, 0)


def short(case):
    return case.replace('_lap_', ' ').replace('_nonfixed', ' (non-fixed)').replace('_', ' ')


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    v1, v2 = runs(['e03_laps', 'e04_wlaps']), runs(['e05_weather_v2'])
    cases = sorted({r['case'] for r in v2}, key=lambda c: (c[0] != 'L', c))
    rows = []
    for case in cases:
        for arm, label in ARMS:
            row = dict(case=case, arm=arm, method=label)
            for key, *_ in METRICS:
                row[key+'_v1'], row['n_v1'] = mean(v1, case, arm, key)
                row[key+'_v2'], row['n_v2'] = mean(v2, case, arm, key)
            rows.append(row)
    with (OUT/'DETECTOR_COMPARISON.csv').open('w') as f:
        w = csv.writer(f)
        w.writerow(['case', 'method', 'n_v1', 'n_v2']+[k+s for k, *_ in METRICS for s in ['_v1', '_v2']])
        w.writerows([r['case'], r['method'], r['n_v1'], r['n_v2']]+[r[k+s] for k, *_ in METRICS for s in ['_v1', '_v2']] for r in rows)
    fmt = lambda v, f: '—' if v is None else format(v, f)
    md = ['# Detector v1 vs weather-trained detector v2 — weather laps', '',
          'Same cases, seeds (4903, 5021), durations, dropouts and methods; only the YOLO weights differ: '
          '**v1** = `best_realistic.pt` (batches e03_laps / e04_wlaps), **v2** = `best_realistic_v2.pt` '
          '(batch e05_weather_v2). Values = mean over both seeds, t = 15 s → end. '
          'Bold = better detector for that method.', '']
    for key, label, f, higher in METRICS:
        md += [f'## {label}', '', '| Case | ' + ' | '.join(f'{l} v1 | {l} v2' for _, l in ARMS) + ' |',
               '|---|' + '---:|'*(2*len(ARMS))]
        for case in cases:
            cells = []
            for arm, _ in ARMS:
                r = next(r for r in rows if r['case'] == case and r['arm'] == arm)
                a, b = r[key+'_v1'], r[key+'_v2']
                better = None if a is None or b is None or a == b else ((b > a) == higher)
                cells += [f'**{fmt(a, f)}**' if better is False else fmt(a, f), f'**{fmt(b, f)}**' if better else fmt(b, f)]
            md.append(f'| {case} | ' + ' | '.join(cells) + ' |')
        md.append('')
    (OUT/'DETECTOR_COMPARISON.md').write_text('\n'.join(md)+'\n')
    # Dumbbell small multiples: one figure per metric, one panel per method.
    for key, label, f, higher in METRICS:
        fig, axes = plt.subplots(1, 3, figsize=(15, 0.42*len(cases)+2.0), sharey=True, sharex=True)
        for ax, (arm, mlabel) in zip(axes, ARMS):
            for i, case in enumerate(cases):
                r = next(r for r in rows if r['case'] == case and r['arm'] == arm)
                a, b = r[key+'_v1'], r[key+'_v2']
                if a is None or b is None:
                    continue
                ax.plot([a, b], [i, i], color=GRID, lw=2.5, zorder=1, solid_capstyle='round')
                ax.scatter(a, i, s=60, facecolor='white', edgecolor=COLOR[arm], linewidth=2, zorder=3, label='detector v1' if i == 0 else None)
                ax.scatter(b, i, s=60, color=COLOR[arm], edgecolor='white', linewidth=1.5, zorder=4, label='detector v2 (weather-trained)' if i == 0 else None)
            ax.set_title(mlabel, fontsize=11, loc='left', color=INK, fontweight='bold')
            if key == 'rmse_m':
                ax.set_xscale('log')
            ax.grid(axis='x', color=GRID, lw=0.8)
            ax.set_axisbelow(True)
            for s in ['top', 'right']:
                ax.spines[s].set_visible(False)
            for s in ['left', 'bottom']:
                ax.spines[s].set_color(MUTED)
            ax.tick_params(colors=MUTED, labelsize=9)
        axes[0].legend(loc='best', frameon=False, fontsize=8.5)
        axes[0].set_yticks(range(len(cases)), [short(c) for c in cases], color=INK)
        axes[0].invert_yaxis()
        fig.supxlabel(label + ('  (higher = better)' if higher else '  (lower = better)'), fontsize=10, color=INK)
        fig.suptitle(f'{label}: detector v1 (hollow) → weather-trained detector v2 (filled), mean of 2 seeds',
                     x=0.01, ha='left', fontsize=12.5, fontweight='bold', color=INK)
        fig.tight_layout()
        fig.savefig(OUT/f'detector_v1_vs_v2_{key}.png', dpi=180, bbox_inches='tight', facecolor='white')
        plt.close(fig)
    print('wrote', OUT)


if __name__ == '__main__':
    main()
