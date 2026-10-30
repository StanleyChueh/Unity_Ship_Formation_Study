#!/usr/bin/env python3
"""Assemble Documentation/KalmanStudy/REPORT_PACKAGE: matrices, statistics, figures, README.

Inputs are the analyzed batches e02 (frozen confirmatory test) and e02x (descriptive
extension: no-bbox-filter arm on the e02 seeds + all weather/wave levels on two fresh
seeds). Every completed run is included; nothing is filtered.
"""
import csv
import json
import math
import os
import shutil
from pathlib import Path
os.environ.setdefault('MPLCONFIGDIR', '/tmp/robust-study-plots')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from analyze_arms import pairwise

ROOT = Path(__file__).resolve().parents[2]
EV = ROOT/'Experiments/KalmanStudy/robust_evaluation'
DOC = ROOT/'Documentation/KalmanStudy'
OUT = DOC/'REPORT_PACKAGE'
ARMS = ['on_rs', 'off_short', 'off_rs', 'raw', 'raw_nogate']
NAME = dict(on_rs='Kalman ON (KF range/speed fusion)', off_short='Kalman OFF (production)', off_rs='Non-Kalman EMA filter',
            raw='No tracker filter (bbox gate kept)', raw_nogate='No bbox filtering at all')
SHORT = dict(on_rs='Kalman ON', off_short='Kalman OFF', off_rs='EMA filter', raw='No tracker filter', raw_nogate='No bbox filter')
LAPS = ['L01_lap_calm', 'L02_lap_rough_sea1.5', 'L03_lap_huge_waves_sea3', 'L04_lap_light_rain0.15', 'L05_lap_rain0.25',
        'L06_lap_rain0.4', 'L07_lap_heavy_rain1.0', 'L08_lap_night', 'L09_lap_night_rain0.15', 'L10_lap_dark_storm']
NONFIXED = ['C8_clear_speed_s_dropout', 'C10_huge_waves_s_dropout', 'W1_rain015_rough_s', 'W2_rain025_rough_s', 'C5_speed_s_dropout',
            'W3_night_rough_s', 'W4_night_rain015_rough_s', 'C7_unseen_turn_8s']
OTHER = ['C0_calm_circle', 'C1_huge_waves', 'C9_clear_rough_brief_dropout', 'C4_turn_dropout_2s', 'C2_heavy_rain', 'C3_dark_storm']
MOTION = dict(circle='fixed circle, constant 18 m/s', variable='NON-FIXED: speed 14/20/10/18 m/s + S-turns', unexpected='NON-FIXED: straight then sudden turn')


def records():
    out = []
    for batch in ['e02', 'e02x', 'e03_laps']:
        if not (EV/batch/'results.json').exists():
            continue
        for r in json.loads((EV/batch/'results.json').read_text())['run_results']:
            r = dict(r, batch=batch)
            if r['motion'] == 'circle':
                r['leader_turn_deg'] = leader_turn(Path(r['raw_output']))
            out.append(r)
    return out


def leader_turn(run):
    turned, prev = 0.0, None
    for line in (run/'steps.jsonl').read_text().splitlines():
        b = json.loads(line)['boats'][0]
        h = math.atan2(b['fx'], b['fz'])
        if prev is not None:
            turned += abs((h-prev+math.pi) % (2*math.pi)-math.pi)
        prev = h
    return math.degrees(turned)


def row_md(c, rows):
    cells = []
    for a in ARMS:
        r = next((q for q in rows if q['case'] == c and q['arm'] == a), None)
        cells.append('—' if r is None else f'{r["median_rmse_m"]:.1f} / {r["formation_broken_pct"]:.0f} % (n={r["n_seeds"]})')
    x0 = next(q for q in rows if q['case'] == c)
    cond = f'{c} (sea {x0["sea"]}, rain {x0["rain"]}{", NIGHT" if x0["dark"] else ""}{", dropouts "+str(x0["bbox_dropout_s"])+" s" if x0["bbox_dropout_s"] else ""})'
    lap = f', turned {x0["leader_turn_deg_min"]:.0f}°' if x0.get('leader_turn_deg_min') is not None and c[0] == 'L' else ''
    return f'| {cond} | {x0["leader_motion"]}{lap} | ' + ' | '.join(cells) + ' |'


def main():
    (OUT/'matrix').mkdir(parents=True, exist_ok=True)
    (OUT/'keyframes').mkdir(exist_ok=True)
    recs = records()
    cases = [c for c in LAPS+NONFIXED+OTHER if any(r['case'] == c for r in recs)]
    rows = []
    for c in cases:
        x0 = next(r for r in recs if r['case'] == c)
        for a in ARMS:
            x = [r for r in recs if r['case'] == c and r['arm'] == a]
            if not x:
                continue
            g = [r['scheduled_gap_rmse_m'] for r in x if r['scheduled_gap_rmse_m'] is not None]
            rows.append(dict(case=c, sea=x0['sea'], rain=x0['rain'], fog=x0['fog'], dark=x0['dark'], leader_motion=MOTION[x0['motion']],
                             bbox_dropout_s=x0['gap'], arm=a, arm_name=NAME[a], n_seeds=len(x), seeds=' '.join(str(r['seed']) for r in sorted(x, key=lambda r: r['seed'])),
                             median_rmse_m=float(np.median([r['rmse_m'] for r in x])), mean_rmse_m=float(np.mean([r['rmse_m'] for r in x])),
                             catastrophic_runs_gt50m=sum(r['rmse_m'] > 50 for r in x), formation_broken_pct=float(np.mean([r['broken_pct'] for r in x])),
                             triangle_iou=float(np.mean([r['mean_iou'] for r in x])), fresh_detection_pct=float(np.mean([r['fresh_pct'] for r in x])),
                             correct_leader_detection_pct=float(np.mean([r['correct_measurement_pct'] for r in x])),
                             min_separation_m=float(min(r['min_separation_m'] for r in x)), dropout_rmse_m=float(np.mean(g)) if g else None,
                             leader_turn_deg_min=min((r['leader_turn_deg'] for r in x if 'leader_turn_deg' in r), default=None),
                             duration_s=60 if x0['case'][0] != 'L' else 135,
                             source_batches=' '.join(sorted({r['batch'] for r in x}))))
    keys = list(rows[0])
    with (OUT/'matrix/experiment_matrix.csv').open('w') as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)
    with (OUT/'matrix/all_runs.csv').open('w') as f:
        k = ['batch', 'case', 'seed', 'arm', 'leader_turn_deg', 'rmse_m', 'broken_pct', 'mean_iou', 'p95_error_m', 'peak_follower_error_m', 'min_separation_m',
             'fresh_pct', 'correct_measurement_pct', 'scheduled_gap_rmse_m', 'raw_output']
        w = csv.DictWriter(f, fieldnames=k)
        w.writeheader()
        w.writerows({kk: r.get(kk) for kk in k} for r in sorted(recs, key=lambda r: (r['case'], r['seed'], r['arm'])))
    f2 = lambda v, s='.1f': '—' if v is None else format(v, s)
    md = ['# Experiment matrix — all conditions × all filtering arms', '',
          'Cell = median formation RMSE (m) / formation-broken time (% of the analysis window with RMS error > 10 m); n = seeds. '
          'Analysis window: t = 15 s to end of run (60 s runs, or 135 s full-lap runs). Every completed run is included. '
          'Sources: e02 (frozen confirmatory test), e02x and e03_laps (descriptive extensions with identical code).', '',
          ]
    sections = [('A. FIXED trajectory — one complete R360 circle lap (135 s, leader turns >= 360°) under every weather/wave level, 2 s bbox dropouts every 18 s', LAPS),
                ('B. NON-FIXED trajectories — leader changes speed (14/20/10/18 m/s) and S-turns, or turns unexpectedly (60 s)', NONFIXED),
                ('C. Other conditions (60 s; fixed circles)', OTHER)]
    for title, group in sections:
        md += ['', '### '+title, '', '| Condition | Leader motion | ' + ' | '.join(SHORT[a] for a in ARMS) + ' |', '|---|---|' + '---:|'*len(ARMS)]
        for c in [c for c in group if c in cases]:
            md.append(row_md(c, rows))
    md += ['', 'Full metrics (mean RMSE, catastrophic runs, IoU, detection rates, min separation, dropout error, measured leader turn): `experiment_matrix.csv`; per run: `all_runs.csv`.']
    # statistics
    inf = json.loads((EV/'e02/inference.json').read_text())
    desc = json.loads((EV/'e02/descriptive_block_tests.json').read_text())
    md += ['', '## Confirmatory statistics (e02 primary family C8 + C10 + W1, 8 unseen seeds, exact sign-flip, fixed sequence α = 0.05)', '',
           '| Hypothesis | RMSE change | 95 % bootstrap | Seeds favouring | Exact p | Result |', '|---|---:|---:|---:|---:|---|']
    for t in inf['tests']:
        lo, hi = t['bootstrap95_reduction_pct']
        md.append(f'| {SHORT[t["treatment"]]} vs {SHORT[t["baseline"]]} | {-t["geometric_rmse_reduction_pct"]:+.1f} % | [{-hi:+.1f}, {-lo:+.1f}] % | '
                  f'{t["blocks_favoring_treatment"]}/{t["n_seed_blocks"]} | {t["exact_two_sided_sign_flip_p"]:.4f} | {"CONFIRMED" if t["rejected_null_at_alpha"] else "not confirmed"} |')
    for t in desc:
        lo, hi = t['bootstrap95_reduction_pct']
        md.append(f'| {SHORT[t["treatment"]]} vs {SHORT[t["baseline"]]} (descriptive) | {-t["geometric_rmse_reduction_pct"]:+.1f} % | [{-hi:+.1f}, {-lo:+.1f}] % | '
                  f'{t["blocks_favoring_treatment"]}/{t["n_seed_blocks"]} | {t["exact_two_sided_sign_flip_p"]:.4f} | descriptive |')
    # paired descriptive vs no-bbox-filter on e02 seeds
    paired = pairwise([r for r in recs if r['seed'] in range(3900, 4800)], 'on_rs', 'raw_nogate')
    if paired:
        md += ['', '## Kalman ON vs NO bbox filtering at all (e02x arm paired with e02 runs on the same seeds; descriptive, post-hoc arm)', '',
               '| Condition | n | No bbox filter RMSE (mean) | Kalman ON RMSE (mean) | Geometric change | Seeds Kalman better | Broken % |', '|---|---:|---:|---:|---:|---:|---:|']
        for p in paired:
            md.append(f'| {p["case"]} | {p["n"]} | {p["baseline_rmse_m"]:.1f} | {p["treatment_rmse_m"]:.1f} | {-p["geometric_reduction_pct"]:+.1f} % | {p["wins"]}/{p["n"]} | '
                      f'{p["baseline_broken_pct"]:.1f} → {p["treatment_broken_pct"]:.1f} |')
    (OUT/'matrix/EXPERIMENT_MATRIX.md').write_text('\n'.join(md)+'\n')
    # heatmap
    M = np.full((len(cases), len(ARMS)), np.nan)
    B = np.full_like(M, np.nan)
    for i, c in enumerate(cases):
        for j, a in enumerate(ARMS):
            r = next((q for q in rows if q['case'] == c and q['arm'] == a), None)
            if r:
                M[i, j], B[i, j] = r['median_rmse_m'], r['formation_broken_pct']
    fig, ax = plt.subplots(figsize=(13, 0.62*len(cases)+2))
    im = ax.imshow(np.log10(M), cmap='RdYlGn_r', vmin=np.log10(2), vmax=np.log10(300), aspect='auto')
    for i in range(len(cases)):
        for j in range(len(ARMS)):
            if not np.isnan(M[i, j]):
                ax.text(j, i, f'{M[i, j]:.1f} m\n{B[i, j]:.0f}% broken', ha='center', va='center', fontsize=8)
    ax.set_xticks(range(len(ARMS)), [SHORT[a] for a in ARMS])
    ax.set_yticks(range(len(cases)), cases)
    cb = fig.colorbar(im, ax=ax, fraction=0.03)
    cb.set_ticks([np.log10(v) for v in [2, 5, 10, 30, 100, 300]], labels=['2', '5', '10', '30', '100', '300'])
    cb.set_label('median formation RMSE (m, log)')
    ax.set_title('Formation error by condition and filtering method (median over seeds; text = median RMSE, formation-broken time)')
    fig.tight_layout()
    fig.savefig(OUT/'matrix/experiment_matrix_heatmap.png', dpi=170)
    plt.close(fig)
    # per-run scatter
    fig, ax = plt.subplots(figsize=(13, 0.75*len(cases)+2))
    colors = dict(on_rs='#0b7a3e', off_short='#757575', off_rs='#c9a400', raw='#c62828', raw_nogate='#8e24aa')
    for i, c in enumerate(cases):
        for j, a in enumerate(ARMS):
            v = [r['rmse_m'] for r in recs if r['case'] == c and r['arm'] == a]
            if v:
                y = i+(j-2)*0.15
                ax.scatter(v, [y]*len(v), s=14, color=colors[a], alpha=.6)
                ax.scatter([np.median(v)], [y], s=70, marker='D', color=colors[a], edgecolor='black', label=SHORT[a] if i == 0 else None)
    ax.set_xscale('log')
    ax.set_yticks(range(len(cases)), cases)
    ax.invert_yaxis()
    ax.grid(axis='x', alpha=.25)
    ax.legend(loc='lower right', fontsize=9)
    ax.set_xlabel('Formation RMSE (m, log); dot = one seed, diamond = median; all runs shown')
    fig.tight_layout()
    fig.savefig(OUT/'matrix/all_runs_scatter.png', dpi=170)
    plt.close(fig)
    for name in ['inference.json', 'descriptive_block_tests.json']:
        shutil.copy2(EV/'e02'/name, OUT/'matrix'/('e02_'+name))
    for src in ['W1_rain015_rough_s_keyframes.jpg', 'C8_clear_speed_s_dropout_keyframes.jpg', 'C10_huge_waves_s_dropout_keyframes.jpg',
                'C10_huge_waves_s_dropout_timeseries.png', 'W1_rain015_rough_s_timeseries.png', 'C8_clear_speed_s_dropout_timeseries.png',
                'keyframe-selection.json']:
        if (DOC/'eval_e02'/src).exists():
            shutil.copy2(DOC/'eval_e02'/src, OUT/'keyframes'/src)
    if (DOC/'condition_videos/ALL_CONDITIONS_grid.mp4').exists():
        (OUT/'condition_videos').mkdir(exist_ok=True)
        shutil.copy2(DOC/'condition_videos/ALL_CONDITIONS_grid.mp4', OUT/'condition_videos/ALL_CONDITIONS_grid.mp4')
    print('package matrix written:', OUT)


if __name__ == '__main__':
    main()
