#!/usr/bin/env python3
"""ON vs OFF chart for the README, and the same data as JSON for the website chart, from e07 results only."""
import json
import os
from pathlib import Path
os.environ.setdefault('MPLCONFIGDIR', '/tmp/robust-study-plots')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
BATCH = ROOT/'Experiments/KalmanStudy/robust_evaluation/e07_vision_only_on_off'
OUT = ROOT/'Documentation/KalmanStudy/REPORT_PACKAGE/vision_only'
CASES = [('L07_lap_heavy_rain1.0', 'Heavy rain'), ('L08_lap_night', 'Night'), ('L09_lap_night_rain0.15', 'Night + rain'), ('L10_lap_dark_storm', 'Dark storm'),
         ('C8_clear_speed_s_dropout', 'Clear, speed changes'), ('L03_lap_huge_waves_sea3', 'Huge waves'), ('C10_huge_waves_s_dropout', 'Huge waves, speed changes')]
ARMS = [('on_pv', 'Kalman ON', '#1baf7a', 'o'), ('off_short_pv', 'Kalman OFF', '#2a78d6', 'D')]
INK, MUTED, GRID = '#262624', '#6b6a63', '#e4e3dc'


def main():
    recs = json.loads((BATCH/'results.json').read_text())['run_results']
    rows = []
    for case, label in CASES:
        row = dict(label=label)
        for arm, *_ in ARMS:
            row[arm] = [round(r['rmse_m'], 2) for r in sorted(recs, key=lambda r: r['seed']) if r['case'] == case and r['arm'] == arm]
        rows.append(row)
    (OUT/'on_vs_off_chart_data.json').write_text(json.dumps(rows, indent=1)+'\n')
    fig, ax = plt.subplots(figsize=(10, 4.6))
    ax.axvline(10, color=MUTED, lw=1, ls=(0, (4, 3)), zorder=1)
    ax.text(10.5, -0.75, '10 m', color=MUTED, fontsize=9, va='center')
    for i, row in enumerate(rows):
        ax.axhline(i, color=GRID, lw=1, zorder=0)
        for j, (arm, label, color, marker) in enumerate(ARMS):
            ax.scatter(row[arm], [i+(0.13 if j else -0.13)]*len(row[arm]), s=70, marker=marker, color=color, edgecolor='white', linewidth=1.3, zorder=3, label=label if i == 0 else None)
    ax.set_xscale('log')
    ax.set_xticks([2, 5, 10, 20, 50, 100, 200, 500, 1000], ['2', '5', '10', '20', '50', '100', '200', '500', '1000'])
    ax.minorticks_off()
    ax.set_yticks(range(len(rows)), [r['label'] for r in rows], color=INK)
    ax.set_ylim(len(rows)-0.5, -1.1)
    ax.set_xlabel('Formation RMSE per run (m, log scale; lower is better)', color=MUTED)
    ax.tick_params(colors=MUTED)
    ax.tick_params(axis='y', colors=INK, length=0)
    for s in ['top', 'right', 'left']:
        ax.spines[s].set_visible(False)
    ax.spines['bottom'].set_color(MUTED)
    ax.legend(frameon=False, loc='upper right', fontsize=10, ncol=2)
    fig.suptitle('Vision-only: Kalman about halves the error in rain and darkness; huge waves are unsolved', x=0.01, ha='left', fontsize=12.5, fontweight='bold', color=INK)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(OUT/'on_vs_off_chart.png', dpi=170, facecolor='white')
    print(json.dumps(rows))


if __name__ == '__main__':
    main()
