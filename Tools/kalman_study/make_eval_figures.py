#!/usr/bin/env python3
"""Multi-arm figures and exact-source camera keyframes for d03+/evaluation batches.

Keyframes: (1) a preselected middle seed per case at predefined loss start /
middle / end / +2 s recovery times (or fixed times for natural-loss cases), and
(2) across ALL seeds, the single instants of largest and smallest
(most negative) treatment-minus-baseline error, explicitly labeled as extrema.
Images are the exact JPEGs the detector received; overlays: white = GT leader
box (evaluation-only), magenta = selected YOLO box, orange = x position of the
estimate the controller used (not an invented 2D box).
"""
import argparse
import json
import os
from pathlib import Path
os.environ.setdefault('MPLCONFIGDIR', '/tmp/robust-study-plots')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image, ImageDraw
from analyze import load, traces
from make_figures import annotated, font, shade
from analyze_arms import LABEL

COLOR = dict(on_ego='#1565c0', on='#7b1fa2', off='#d35b22', off_short='#757575', on_rs='#0b7a3e', off_rs='#c9a400', raw='#c62828')


def loaded(job):
    rows = load(job)
    for r in rows:
        r['_directory'] = job['output']
    return rows, traces(rows, job)


def matrix_plot(records, out, title):
    cases = sorted({r['case'] for r in records})
    arms = [a for a in LABEL if any(r['arm'] == a for r in records)]
    fig, ax = plt.subplots(figsize=(12, 0.9*len(cases)+2))
    for i, case in enumerate(cases):
        for j, arm in enumerate(arms):
            shift = (j-(len(arms)-1)/2)*0.17
            vals = [r['rmse_m'] for r in records if r['case'] == case and r['arm'] == arm]
            if not vals:
                continue
            ax.scatter(vals, np.full(len(vals), i+shift), s=14, color=COLOR[arm], alpha=.55)
            ax.scatter([np.exp(np.mean(np.log(vals)))], [i+shift], s=80, marker='D', color=COLOR[arm],
                       edgecolor='black', label=LABEL[arm] if i == 0 else None)
    ax.set_xscale('log')
    ax.set_yticks(range(len(cases)), cases)
    ax.invert_yaxis()
    ax.grid(axis='x', alpha=.25)
    ax.legend(loc='lower right', fontsize=9)
    ax.set_xlabel('Follower formation RMSE (m, log scale), motion t=15–60 s; dot = seed, diamond = geometric mean')
    ax.set_title(title)
    fig.tight_layout()
    fig.savefig(out/'matrix.png', dpi=170)
    plt.close(fig)


def sheet(case, entries, out_path, header):
    """entries: list of rows; each row = list of (row, arm, side, rms) frames."""
    columns = max(len(e) for e in entries)
    image = Image.new('RGB', (columns*640, 60+len(entries)*375), '#161b22')
    draw = ImageDraw.Draw(image)
    draw.text((10, 12), header, font=font(20), fill='white')
    for ri, frames in enumerate(entries):
        for ci, (row, arm, side, rms) in enumerate(frames):
            im = annotated(row, LABEL[arm], side, rms)
            im.thumbnail((640, 360))
            image.paste(im, (ci*640, 60+ri*375))
    image.save(out_path, quality=92)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--treatment', default='on_ego')
    parser.add_argument('--baselines', default='off_short,off')
    args = parser.parse_args()
    data = args.directory.resolve()
    out = (args.output or data/'figures').resolve()
    out.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((data/'manifest.json').read_text())
    results = json.loads((data/'results.json').read_text())
    records = results['run_results']
    stage = manifest['stage']
    matrix_plot(records, out, f'{data.name} ({stage}): all completed runs, no seeds removed')
    jobs = {(j['case'], j['seed'], j['arm']): j for j in manifest['jobs']
            if (Path(j['output'])/'bridge.complete').exists() and (Path(j['output'])/'unity.complete').exists()}
    selections = []
    for case in sorted({k[0] for k in jobs}):
        seeds = sorted({k[1] for k in jobs if k[0] == case})
        arms = [a for a in LABEL if any((case, s, a) in jobs for s in seeds)]
        seed = seeds[len(seeds)//2]
        series = {a: loaded(jobs[(case, seed, a)]) for a in arms if (case, seed, a) in jobs}
        job = next(iter(jobs[(case, seed, a)] for a in series))
        fig, axes = plt.subplots(3, 1, figsize=(12, 8.5), sharex=True)
        for arm, (rows, trace) in series.items():
            t = [r['t'] for r in rows]
            axes[0].plot(t, [r['rms'] for r in trace], color=COLOR[arm], label=LABEL[arm], lw=1.3)
            axes[1].plot(t, [r['iou'] for r in trace], color=COLOR[arm], lw=1.1)
            axes[2].plot(t, [r['status']['Left']['target_area'] or np.nan for r in rows], color=COLOR[arm], lw=1.0)
        for ax in axes:
            shade(ax, job)
            ax.set_xlim(0, 60)
        axes[0].axhline(10, color='black', ls='--', lw=.8)
        axes[0].set_ylabel('Follower RMS error (m)')
        axes[0].legend(fontsize=9)
        axes[1].set_ylabel('Triangle IoU')
        axes[2].set_ylabel('Left box area used (px)')
        axes[2].set_xlabel('Seconds since leader motion starts (gray = scheduled measurement suppression)')
        axes[0].set_title(f'{case} / preselected middle seed {seed}')
        fig.tight_layout()
        fig.savefig(out/f'{case}_timeseries.png', dpi=150)
        plt.close(fig)
        # (1) predefined times on the middle seed
        times = [19.9, 21.0, 21.9, 24.0] if job['gap'] else [16.0, 25.0, 35.0, 45.0]
        if job['gap'] and job['gap'] > 2.5:
            times = [19.9, 20+job['gap']/2, 20+job['gap']-0.1, 20+job['gap']+2]
        shown = [a for a in [args.treatment]+args.baselines.split(',') if a in series]
        rows_out = []
        for arm in shown:
            rows, trace = series[arm]
            frames = []
            for t in times:
                i = min(range(len(rows)), key=lambda k: abs(rows[k]['t']-t))
                side = 'Left' if trace[i]['left_error'] >= trace[i]['right_error'] else 'Right'
                frames.append((rows[i], arm, side, trace[i]['rms']))
                selections.append(dict(kind='predefined', case=case, seed=seed, arm=arm, t=rows[i]['t'], step=rows[i]['step'], side=side,
                                       jpeg_sha256=rows[i]['image_sha256'][side+'Front'], source=jobs[(case, seed, arm)]['output']))
            rows_out.append(frames)
        sheet(case, rows_out, out/f'{case}_keyframes.jpg',
              f'{case} seed {seed} (preselected middle seed). Rows: {", ".join(LABEL[a] for a in shown)}. Times {times} s.')
        # (2) extrema across all seeds vs each baseline
        for baseline in args.baselines.split(','):
            best, worst = None, None
            for s in seeds:
                if (case, s, args.treatment) not in jobs or (case, s, baseline) not in jobs:
                    continue
                a_rows, a_tr = loaded(jobs[(case, s, args.treatment)])
                b_rows, b_tr = loaded(jobs[(case, s, baseline)])
                for i in range(150, min(len(a_tr), len(b_tr))):
                    d = a_tr[i]['rms']-b_tr[i]['rms']
                    item = (d, s, i, a_rows, a_tr, b_rows, b_tr)
                    if best is None or d < best[0]:
                        best = item
                    if worst is None or d > worst[0]:
                        worst = item
            for tag, item in [('largest_benefit', best), ('largest_disadvantage', worst)]:
                if item is None:
                    continue
                d, s, i, a_rows, a_tr, b_rows, b_tr = item
                frames = []
                for rows, trace, arm in [(a_rows, a_tr, args.treatment), (b_rows, b_tr, baseline)]:
                    side = 'Left' if trace[i]['left_error'] >= trace[i]['right_error'] else 'Right'
                    frames.append((rows[i], arm, side, trace[i]['rms']))
                    selections.append(dict(kind='extremum_'+tag, baseline=baseline, case=case, seed=s, arm=arm, t=rows[i]['t'], step=rows[i]['step'],
                                           side=side, error_difference_m=d, jpeg_sha256=rows[i]['image_sha256'][side+'Front'],
                                           source=jobs[(case, s, arm)]['output']))
                sheet(case, [frames], out/f'{case}_vs_{baseline}_EXTREMUM_{tag}.jpg',
                      f'EXTREMUM, not representative: {case} seed {s} t={a_rows[i]["t"]:.1f}s, '
                      f'{LABEL[args.treatment]} minus {LABEL[baseline]} = {d:+.1f} m')
    (out/'keyframe-selection.json').write_text(json.dumps(selections, indent=2)+'\n')
    print('Saved figures:', out)


if __name__ == '__main__':
    main()
