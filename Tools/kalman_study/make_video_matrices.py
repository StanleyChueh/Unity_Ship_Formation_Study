#!/usr/bin/env python3
"""One experiment matrix per 3-way rollout video (KALMAN ON / KALMAN OFF / NO bbox filtering).

For each condition video (fixed seed 4903, the seed the video shows) the matrix lists the
metrics of exactly those three runs, plus the mean over both seeds (4903, 5021) for context.
Metrics use the analysis window t = 15 s -> end of run. Outputs per video: PNG table, CSV,
Markdown; plus ALL_3WAY_MATRICES.md/.csv. Also reports the measured leader turn (>= 360 deg
means the video's run completed a full circle).
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
from make_report_package import leader_turn

ROOT = Path(__file__).resolve().parents[2]
EV = ROOT/'Experiments/KalmanStudy/robust_evaluation'
OUT = Path(os.environ.get('KS_3WAY_DIR', ROOT/'Documentation/KalmanStudy/REPORT_PACKAGE/rollout_videos_3way'))/'matrices'
ARMS = [('on_rs', 'KALMAN ON'), ('off_short', 'KALMAN OFF'), ('raw_nogate', 'NO bbox filtering')]
VIDEO_SEED = 4903
# (key, label, format, higher_is_better)
METRICS = [('rmse_m', 'Formation RMSE (m)', '.2f', False),
           ('broken_pct', 'Formation broken, error > 10 m (% of time)', '.1f', False),
           ('mean_iou', 'Triangle IoU (0-1)', '.3f', True),
           ('p95_error_m', 'Follower error, 95th percentile (m)', '.1f', False),
           ('peak_follower_error_m', 'Follower error, peak (m)', '.1f', False),
           ('min_separation_m', 'Minimum boat separation (m)', '.1f', True),
           ('fresh_pct', 'Fresh YOLO leader detection (% frames)', '.1f', True),
           ('correct_measurement_pct', 'Correct leader detection (% frames)', '.1f', True),
           ('scheduled_gap_rmse_m', 'Formation RMSE during bbox dropouts (m)', '.2f', False),
           ('steer_variation_per_s', 'Steer variation (|d steer| per s)', '.3f', False),
           ('throttle_variation_per_s', 'Throttle variation (|d throttle| per s)', '.3f', False)]


def results():
    out = []
    for batch in os.environ.get('KS_BATCHES', 'e03_laps,e04_wlaps').split(','):
        p = EV/batch/'results.json'
        if p.exists():
            out += json.loads(p.read_text())['run_results']
    return out


def render_png(case, rows, turn, path):
    cols = [label for _, label in ARMS]
    fig, ax = plt.subplots(figsize=(11.5, 0.36*(len(rows)+1)+0.5))
    ax.axis('off')
    cell = [[r['label']]+r['values'] for r in rows]
    table = ax.table(cellText=cell, colLabels=['Metric (t = 15 s → end, seed 4903 = this video)']+cols, loc='center',
                     cellLoc='center', colLoc='center', colWidths=[0.46, 0.18, 0.18, 0.18], bbox=[0, 0, 1, 1])
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    head = {0: '#ececea', 1: '#2fa84f', 2: '#9b9b9b', 3: '#c65bc6'}
    for (i, j), c in table.get_celld().items():
        c.set_edgecolor('#d9d8d2')
        if i == 0:
            c.set_facecolor(head[j])
            c.set_text_props(weight='bold', color='white' if j else '#262624')
        elif j == 0:
            c.set_text_props(ha='left')
            c._loc = 'left'
        if i > 0 and j > 0 and rows[i-1]['best'] == j-1:
            c.set_text_props(weight='bold')
            c.set_facecolor('#eef6ee')
    ax.set_title(f'{case} — experiment matrix for this video (seed 4903); leader turned {turn:.0f}° '
                 f'({"complete circle" if turn >= 360 else "NOT a full circle"}). Bold = best of the three.',
                 fontsize=10.5, loc='left', pad=6)
    fig.tight_layout()
    fig.savefig(path, dpi=180, bbox_inches='tight', facecolor='white')
    plt.close(fig)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    recs = results()
    cases = sorted({r['case'] for r in recs}, key=lambda c: (c[0] != 'L', c))
    all_md = ['# Experiment matrices for the 3-way rollout videos', '',
              'One table per video: the three runs shown in that video (seed 4903), metrics over t = 15 s → end. '
              'Last rows: mean over both seeds (4903, 5021) for context. Bold = best of the three.', '']
    all_csv = []
    for case in cases:
        run = {a: next((r for r in recs if r['case'] == case and r['seed'] == VIDEO_SEED and r['arm'] == a), None) for a, _ in ARMS}
        if any(v is None for v in run.values()):
            print('incomplete', case)
            continue
        turn = leader_turn(Path(run['on_rs']['raw_output']))
        rows = []
        for key, label, fmt, higher in METRICS:
            vals = [run[a][key] for a, _ in ARMS]
            if any(v is None for v in vals):
                continue
            best = int(np.argmax(vals) if higher else np.argmin(vals))
            rows.append(dict(label=label, values=[format(v, fmt) for v in vals], best=best, key=key, raw=vals))
        both = {a: [r for r in recs if r['case'] == case and r['arm'] == a] for a, _ in ARMS}
        for key, label in [('rmse_m', 'Mean formation RMSE over both seeds (m)'), ('broken_pct', 'Mean broken time over both seeds (%)')]:
            vals = [float(np.mean([r[key] for r in both[a]])) for a, _ in ARMS]
            rows.append(dict(label=label+f' [n={min(len(both[a]) for a, _ in ARMS)}]', values=[format(v, '.1f') for v in vals],
                             best=int(np.argmin(vals)), key=key+'_both_seeds', raw=vals))
        name = f'{case}_seed{VIDEO_SEED}_3way'
        render_png(case, rows, turn, OUT/f'{name}_matrix.png')
        md = [f'## {case} (video `{name}.mp4`)', '', f'Leader turned {turn:.0f}° in this run '
              f'({"complete circle" if turn >= 360 else "not a full circle"}).', '',
              '| Metric | ' + ' | '.join(l for _, l in ARMS) + ' |', '|---|---:|---:|---:|']
        for r in rows:
            md.append(f'| {r["label"]} | ' + ' | '.join(f'**{v}**' if i == r['best'] else v for i, v in enumerate(r['values'])) + ' |')
        (OUT/f'{name}_matrix.md').write_text('\n'.join(md)+'\n')
        with (OUT/f'{name}_matrix.csv').open('w') as f:
            w = csv.writer(f)
            w.writerow(['metric']+[l for _, l in ARMS])
            for r in rows:
                w.writerow([r['label']]+r['raw'])
        all_md += md+['']
        for r in rows:
            all_csv.append([case, r['key'], r['label']]+r['raw'])
        print('matrix', name)
    (OUT/'ALL_3WAY_MATRICES.md').write_text('\n'.join(all_md)+'\n')
    with (OUT/'ALL_3WAY_MATRICES.csv').open('w') as f:
        w = csv.writer(f)
        w.writerow(['case', 'metric_key', 'metric']+[l for _, l in ARMS])
        w.writerows(all_csv)


if __name__ == '__main__':
    main()
