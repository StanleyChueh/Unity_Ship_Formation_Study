#!/usr/bin/env python3
"""4-metric experiment matrices for the views videos: formation RMSE, triangle IoU,
steer variation, throttle variation (seed 4903 = the run each video shows; t = 15 s -> end).

Writes per-video PNG/CSV/MD into rollout_videos_views/matrices, a combined table
(ALL_VIEWS_MATRICES.md/.csv) and a small-multiples comparison figure across all conditions.
"""
import csv
import os
from pathlib import Path
os.environ.setdefault('MPLCONFIGDIR', '/tmp/robust-study-plots')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import make_video_matrices as mvm
from make_report_package import leader_turn

ROOT = Path(__file__).resolve().parents[2]
VIEWS = Path(os.environ.get('KS_VIEWS_DIR', ROOT/'Documentation/KalmanStudy/REPORT_PACKAGE/rollout_videos_views'))
OUT = VIEWS/'matrices'
METRICS = [('rmse_m', 'Formation RMSE (m)', '.2f', False),
           ('mean_iou', 'Formation IoU (0-1)', '.3f', True),
           ('steer_variation_per_s', 'Steer variation (|Δsteer| per s)', '.3f', False),
           ('throttle_variation_per_s', 'Throttle variation (|Δthrottle| per s)', '.3f', False)]
ARMS = mvm.ARMS
# Validated categorical palette (dataviz validator, light surface): aqua, blue, magenta.
COLOR = dict(on_rs='#1baf7a', off_short='#2a78d6', raw_nogate='#e87ba4')
MARKER = dict(on_rs='o', off_short='s', raw_nogate='D')
INK, MUTED, GRID = '#262624', '#6b6a63', '#e4e3dc'


def main():
    for old in OUT.glob('*'):
        old.unlink()
    OUT.mkdir(parents=True, exist_ok=True)
    recs = mvm.results()
    videos = sorted(p.name[:-len('_views.mp4')] for p in VIEWS.glob('*_views.mp4'))
    combined, md_all = [], ['# Views videos — formation RMSE, IoU, steer and throttle variation', '',
                            'Each table = the three runs shown in that video (seed 4903), metrics over t = 15 s → end of run. '
                            'Bold = best of the three (lower is better except IoU).', '',
                            '**How to read steer/throttle variation:** lower = smoother control, but only where the formation is '
                            'actually held (L01–L03). Where a method has lost the leader (heavy rain, night, dark storm) the follower '
                            'cruises blind with near-constant commands, so its variation is near zero although it is failing; and in '
                            'rain KALMAN ON can show higher steer variation because it is still actively tracking. Read variation '
                            'together with RMSE and IoU.', '']
    for name in videos:
        case = name.rsplit('_seed', 1)[0]
        run = {a: next((r for r in recs if r['case'] == case and r['seed'] == mvm.VIDEO_SEED and r['arm'] == a), None) for a, _ in ARMS}
        if any(v is None for v in run.values()):
            print('missing runs for', name)
            continue
        turn = leader_turn(Path(run['on_rs']['raw_output']))
        rows = []
        for key, label, fmt, higher in METRICS:
            vals = [run[a][key] for a, _ in ARMS]
            best = int(np.argmax(vals) if higher else np.argmin(vals))
            rows.append(dict(label=label, values=[format(v, fmt) for v in vals], best=best, key=key, raw=vals))
            combined.append(dict(case=case, key=key, label=label, **{a: run[a][key] for a, _ in ARMS}))
        mvm.render_png(case, rows, turn, OUT/f'{name}_views_matrix.png')
        md = [f'## {case} (video `{name}_views.mp4`, leader turned {turn:.0f}°)', '',
              '| Metric | ' + ' | '.join(l for _, l in ARMS) + ' |', '|---|---:|---:|---:|']
        for r in rows:
            md.append(f'| {r["label"]} | ' + ' | '.join(f'**{v}**' if i == r['best'] else v for i, v in enumerate(r['values'])) + ' |')
        (OUT/f'{name}_views_matrix.md').write_text('\n'.join(md)+'\n')
        with (OUT/f'{name}_views_matrix.csv').open('w') as f:
            w = csv.writer(f)
            w.writerow(['metric']+[l for _, l in ARMS])
            w.writerows([r['label']]+r['raw'] for r in rows)
        md_all += md+['']
        print('matrix', name)
    (OUT/'ALL_VIEWS_MATRICES.md').write_text('\n'.join(md_all)+'\n')
    with (OUT/'ALL_VIEWS_MATRICES.csv').open('w') as f:
        w = csv.writer(f)
        w.writerow(['case', 'metric']+[l for _, l in ARMS])
        w.writerows([c['case'], c['label']]+[c[a] for a, _ in ARMS] for c in combined)
    # Small-multiples comparison figure (one panel per metric, one row per condition).
    cases = list(dict.fromkeys(c['case'] for c in combined))
    fig, axes = plt.subplots(1, 4, figsize=(17, 0.46*len(cases)+2.2), sharey=True)
    y = np.arange(len(cases))
    for ax, (key, label, fmt, higher) in zip(axes, METRICS):
        for i, case in enumerate(cases):
            c = next(c for c in combined if c['case'] == case and c['key'] == key)
            vals = [c[a] for a, _ in ARMS]
            ax.plot([min(vals), max(vals)], [i, i], color=GRID, lw=2, zorder=1, solid_capstyle='round')
            for a, lab in ARMS:
                ax.scatter(c[a], i, s=58, marker=MARKER[a], color=COLOR[a], edgecolor='white', linewidth=1.5, zorder=3,
                           label=lab if i == 0 else None)
        if key == 'rmse_m':
            ax.set_xscale('log')
        ax.set_title(label + ('  (higher = better)' if higher else '  (lower = better)'), fontsize=10.5, loc='left', color=INK)
        ax.grid(axis='x', color=GRID, lw=0.8)
        ax.set_axisbelow(True)
        for s in ['top', 'right']:
            ax.spines[s].set_visible(False)
        ax.spines['left'].set_color(MUTED)
        ax.spines['bottom'].set_color(MUTED)
        ax.tick_params(colors=MUTED, labelsize=9)
    axes[0].set_yticks(y, [c.replace('_lap_', ' ').replace('_nonfixed', ' (non-fixed)').replace('_', ' ') for c in cases], color=INK)
    axes[0].invert_yaxis()
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc='upper left', ncol=3, frameon=False, bbox_to_anchor=(0.12, 1.0), fontsize=10)
    fig.suptitle('Rollout videos (seed 4903): formation RMSE, IoU, steer and throttle variation by condition',
                 x=0.12, ha='left', y=1.045, fontsize=13, fontweight='bold', color=INK)
    fig.tight_layout()
    fig.savefig(OUT/'ALL_VIEWS_comparison.png', dpi=180, bbox_inches='tight', facecolor='white')
    plt.close(fig)


if __name__ == '__main__':
    main()
