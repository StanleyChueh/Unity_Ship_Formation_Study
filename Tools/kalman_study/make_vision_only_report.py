#!/usr/bin/env python3
"""Report for the vision-only test: can the fleet hold formation without leader speed?

Reads one analyzed batch (default e06_vision_only) and writes into
REPORT_PACKAGE/vision_only/: VISION_ONLY_MATRIX.md/.csv and three figures.

  fig_a  cost of removing leader speed: KF with telemetry vs the two vision-only KFs
  fig_b  value of the filter once leader speed is gone: vision-only KF vs the two baselines
  fig_c  leader speed recovered from images vs the true leader speed
Five methods fail the colour check together, so they are split into two validated sets
(dataviz validator, all pairs): aqua/yellow/violet and yellow/blue/magenta.
"""
import argparse
import csv
import json
import math
import os
from pathlib import Path
os.environ.setdefault('MPLCONFIGDIR', '/tmp/robust-study-plots')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from make_rollout_videos import load

ROOT = Path(__file__).resolve().parents[2]
EV = ROOT/'Experiments/KalmanStudy/robust_evaluation'
OUT = ROOT/'Documentation/KalmanStudy/REPORT_PACKAGE/vision_only'
ARMS = [('on_rs', 'Kalman + leader speed (radio)'), ('on_vo', 'Kalman, vision + own speed'), ('on_pv', 'Kalman, vision only (strict)'),
        ('off_short_vo', 'Kalman OFF, vision estimate'), ('raw_nogate_vo', 'No bbox filtering, vision estimate')]
LABEL = dict(ARMS)
COLOR = dict(on_rs='#1baf7a', on_vo='#eda100', on_pv='#6250d6', off_short_vo='#2a78d6', raw_nogate_vo='#e87ba4')
MARKER = dict(on_rs='o', on_vo='s', on_pv='^', off_short_vo='D', raw_nogate_vo='v')
INK, MUTED, GRID = '#262624', '#6b6a63', '#e4e3dc'
METRICS = [('rmse_m', 'Formation RMSE (m)', '.2f'), ('median', 'Median seed RMSE (m)', '.2f'), ('broken_pct', 'Broken, error > 10 m (% time)', '.1f'),
           ('mean_iou', 'Triangle IoU', '.3f'), ('min_separation_m', 'Min boat separation (m)', '.1f'), ('fresh_pct', 'Fresh detection (% frames)', '.1f'),
           ('recovery_s', 'Recovery after 2 s dropout (s)', '.1f')]


NAMES = dict(C0_calm_circle='Calm, constant speed', C8_clear_speed_s_dropout='Clear, speed changes + S-turns',
             W3_night_rough_s='Night, speed changes + S-turns', C10_huge_waves_s_dropout='Huge waves, speed changes + S-turns')


def short(case):
    return NAMES.get(case, case.replace('_lap_', ' lap ').replace('_nonfixed', ' (non-fixed)').replace('_', ' '))


def stats(rs):
    out = dict(n=len(rs))
    for key, *_ in METRICS:
        if key == 'median':
            out[key] = float(np.median([r['rmse_m'] for r in rs]))
        elif key == 'recovery_s':
            rec = [e['recovery_confirmed_s'] for r in rs for e in (r.get('events') or []) if not e['recovery_censored']]
            out[key] = float(np.mean(rec)) if rec else None
        else:
            v = [r[key] for r in rs if r.get(key) is not None]
            out[key] = float(np.mean(v)) if v else None
    return out


def panel(ax, cases, table, arms, key, title, log=False):
    for i, case in enumerate(cases):
        vals = [table[case][a][key] for a in arms if a in table[case]]
        ax.plot([min(vals), max(vals)], [i, i], color=GRID, lw=2, zorder=1, solid_capstyle='round')
        for a in arms:
            if a in table[case]:
                ax.scatter(table[case][a][key], i, s=62, marker=MARKER[a], color=COLOR[a], edgecolor='white', linewidth=1.4, zorder=3,
                           label=LABEL[a] if i == 0 else None)
    if log:
        ax.set_xscale('log')
        ax.set_xticks([1, 2, 5, 10, 20], ['1', '2', '5', '10', '20'])
        ax.minorticks_off()
    ax.set_title(title, fontsize=10.5, loc='left', color=INK)
    ax.grid(axis='x', color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    for s in ['top', 'right']:
        ax.spines[s].set_visible(False)
    for s in ['left', 'bottom']:
        ax.spines[s].set_color(MUTED)
    ax.tick_params(colors=MUTED, labelsize=9)


def figure(cases, table, arms, title, path):
    fig, axes = plt.subplots(1, 2, figsize=(13, 0.5*len(cases)+2.0), sharey=True)
    panel(axes[0], cases, table, arms, 'median', 'Median formation RMSE (m, log scale, lower = better)', log=True)
    panel(axes[1], cases, table, arms, 'broken_pct', 'Formation broken, error > 10 m (% of time, lower = better)')
    axes[0].set_yticks(range(len(cases)), [short(c) for c in cases], color=INK)
    axes[0].invert_yaxis()
    handles, labels = axes[0].get_legend_handles_labels()
    fig.suptitle(title, x=0.01, ha='left', fontsize=13, fontweight='bold', color=INK)
    fig.legend(handles, labels, loc='upper left', ncol=len(arms), frameon=False, bbox_to_anchor=(0.01, 0.95), fontsize=10)
    fig.tight_layout(rect=(0, 0, 1, 0.92))
    fig.savefig(path, dpi=180, bbox_inches='tight', facecolor='white')
    plt.close(fig)


def speed_figure(run, path):
    rows = [r for r in load(run) if r['t'] >= 0]
    t = np.array([r['t'] for r in rows])
    true = np.array([r['boats'][0]['speed'] for r in rows])
    est = np.array([(r['controls']['Left']['leader_speed_knots']+r['controls']['Right']['leader_speed_knots'])/2/1.94384 for r in rows])
    sel = t >= 15
    fig, ax = plt.subplots(figsize=(11, 3.6))
    ax.plot(t, true, color=INK, lw=2, label='True leader speed (evaluation only, never given to the controller)')
    strict = run.name.endswith('on_pv')
    ax.plot(t, est, color=COLOR['on_pv' if strict else 'on_vo'], lw=2, label='Kalman estimate from camera + own commands' if strict else 'Kalman estimate from camera + own speed')
    ax.set_xlabel('Time (s)', color=MUTED)
    ax.set_ylabel('Leader speed (m/s)', color=MUTED)
    ax.grid(axis='y', color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    for s in ['top', 'right']:
        ax.spines[s].set_visible(False)
    for s in ['left', 'bottom']:
        ax.spines[s].set_color(MUTED)
    ax.tick_params(colors=MUTED)
    ax.legend(frameon=False, loc='lower right', fontsize=9.5)
    rms = math.sqrt(np.mean((est[sel]-true[sel])**2))
    ax.set_title(f'Leader speed recovered from images: RMS error {rms:.1f} m/s after t = 15 s', loc='left', fontsize=12, fontweight='bold', color=INK)
    fig.tight_layout()
    fig.savefig(path, dpi=180, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    return rms


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--batch', type=Path, default=EV/'e06_vision_only')
    ap.add_argument('--out', type=Path, default=OUT)
    ap.add_argument('--speed-run', default='C8_clear_speed_s_dropout_4903_on_vo')
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    recs = json.loads((a.batch/'results.json').read_text())['run_results']
    order = list(NAMES)
    cases = sorted({r['case'] for r in recs}, key=lambda c: (order.index(c) if c in order else len(order), c))
    table = {c: {arm: stats([r for r in recs if r['case'] == c and r['arm'] == arm]) for arm, _ in ARMS if any(r['case'] == c and r['arm'] == arm for r in recs)} for c in cases}
    with (a.out/'VISION_ONLY_MATRIX.csv').open('w') as f:
        w = csv.writer(f)
        w.writerow(['case', 'method', 'n']+[k for k, *_ in METRICS])
        for c in cases:
            for arm, label in ARMS:
                if arm in table[c]:
                    w.writerow([c, label, table[c][arm]['n']]+[table[c][arm][k] for k, *_ in METRICS])
    md = ['# Vision-only matrix', '', f'Batch `{a.batch.name}`. Mean over seeds unless stated, t = 15 s → end. Bold = best in that row.', '']
    for key, label, f_ in METRICS:
        higher = key in ('mean_iou', 'min_separation_m', 'fresh_pct')
        md += [f'## {label}', '', '| Case | '+' | '.join(l for _, l in ARMS)+' |', '|---|'+'---:|'*len(ARMS)]
        for c in cases:
            vals = [table[c].get(arm, {}).get(key) for arm, _ in ARMS]
            present = [v for v in vals if v is not None]
            best = (max if higher else min)(present) if present else None
            md.append(f'| {c} | '+' | '.join('—' if v is None else (f'**{v:{f_}}**' if v == best else f'{v:{f_}}') for v in vals)+' |')
        md.append('')
    (a.out/'VISION_ONLY_MATRIX.md').write_text('\n'.join(md)+'\n')
    figure(cases, table, ['on_rs', 'on_vo', 'on_pv'], 'What removing leader speed costs the Kalman tracker', a.out/'fig_a_cost_of_removing_leader_speed.png')
    if any('off_short_vo' in table[c] for c in cases):
        figure(cases, table, ['on_vo', 'off_short_vo', 'raw_nogate_vo'], 'Does the Kalman filter still help once leader speed is gone?', a.out/'fig_b_filter_value_vision_only.png')
    run = a.batch/'runs'/a.speed_run
    if run.exists():
        print('leader speed RMS error', speed_figure(run, a.out/'fig_c_leader_speed_estimate.png'))
    print('wrote', a.out)


if __name__ == '__main__':
    main()
