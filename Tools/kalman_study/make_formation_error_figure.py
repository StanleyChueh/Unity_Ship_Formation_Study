#!/usr/bin/env python3
"""Explanatory figure: how formation error is computed in the rollout videos and matrix.

(a) schematic in the leader frame, (b) a real logged instant, (c) one run's error over time
with the 10 m "broken" threshold and the t >= 15 s RMSE window. The real example is fixed by
rule: L03 huge-wave full lap, seed 4903, Kalman OFF, first instant after t = 15 s with
formation error > 10 m.
"""
import json
import math
import os
from pathlib import Path
os.environ.setdefault('MPLCONFIGDIR', '/tmp/robust-study-plots')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT/'Experiments/KalmanStudy/robust_evaluation/e03_laps/runs/L03_lap_huge_waves_sea3_4903_off_short'
OUT = ROOT/'Documentation/KalmanStudy/REPORT_PACKAGE/figures'
INK, MUTED, GRID = '#262624', '#6b6a63', '#d9d8d2'
LEFT, RIGHT = '#2a78d6', '#eb6834'   # categorical slots 1-2 (validated: CVD dE 24.7)
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10, 'axes.edgecolor': MUTED, 'axes.labelcolor': INK,
                     'xtick.color': MUTED, 'ytick.color': MUTED, 'axes.titleweight': 'bold', 'axes.titlesize': 11})


def leader_frame(row):
    """Return leader-frame coordinates (lateral right +, ahead +) of followers and slots, and errors."""
    L = row['boats'][0]
    fx, fz = L['fx'], L['fz']
    n = math.hypot(fx, fz)
    fx, fz = fx/n, fz/n
    rx, rz = fz, -fx
    def to_frame(x, z):
        dx, dz = x-L['x'], z-L['z']
        return dx*rx+dz*rz, dx*fx+dz*fz
    out = {}
    for side, bi in [('left', 1), ('right', 2)]:
        back, lat = row[side+'_back'], row[side+'_side']
        slot = (lat, back)
        boat = to_frame(row['boats'][bi]['x'], row['boats'][bi]['z'])
        out[side] = dict(slot=slot, boat=boat, e=math.dist(slot, boat))
    out['formation'] = math.sqrt((out['left']['e']**2+out['right']['e']**2)/2)
    return out


def draw_frame(ax, geo, title, annotate_dims):
    ax.set_aspect('equal')
    ax.axhline(0, color=GRID, lw=0.8, zorder=0)
    ax.axvline(0, color=GRID, lw=0.8, zorder=0)
    ax.annotate('', xy=(0, 9), xytext=(0, 0), arrowprops=dict(arrowstyle='-|>', color=INK, lw=2))
    ax.text(1.2, 7.5, 'leader heading f', color=INK, fontsize=9)
    ax.annotate('', xy=(9, 0), xytext=(0, 0), arrowprops=dict(arrowstyle='-|>', color=MUTED, lw=1.5))
    ax.text(5.5, 1.2, 'right r', color=MUTED, fontsize=9)
    ax.plot([0], [0], marker='^', ms=13, color=INK, zorder=5)
    ax.text(-2, 2.5, 'Leader', color=INK, fontsize=10, fontweight='bold', ha='right')
    s_l, s_r = geo['left']['slot'], geo['right']['slot']
    ax.plot([0, s_l[0], s_r[0], 0], [0, s_l[1], s_r[1], 0], ls=':', color=MUTED, lw=1.2, zorder=1)
    for side, color, name in [('left', LEFT, 'Left follower'), ('right', RIGHT, 'Right follower')]:
        slot, boat, e = geo[side]['slot'], geo[side]['boat'], geo[side]['e']
        ax.add_patch(plt.Circle(slot, 1.6, fill=False, ec=MUTED, lw=1.5, ls='--', zorder=2))
        ax.plot(*boat, 'o', ms=10, color=color, mec='white', mew=2, zorder=6)
        ax.plot([slot[0], boat[0]], [slot[1], boat[1]], color=color, lw=2.2, zorder=4)
        mx, my = (slot[0]+boat[0])/2, (slot[1]+boat[1])/2
        ax.text(mx+(1.6 if side == 'right' else -1.6), my, f'e$_{{{side[0].upper()}}}$ = {e:.1f} m', color=INK, fontsize=10,
                ha='left' if side == 'right' else 'right', va='center', fontweight='bold',
                bbox=dict(boxstyle='round,pad=0.2', fc='white', ec='none', alpha=0.9))
        ax.text(boat[0], boat[1]-2.6, name, color=INK, fontsize=9, ha='center', va='top')
    if annotate_dims:
        ax.annotate('', xy=(s_l[0], -38), xytext=(0, -38), arrowprops=dict(arrowstyle='<->', color=MUTED))
        ax.plot([s_l[0], s_l[0]], [s_l[1]-2, -38], color=GRID, lw=0.8, ls='--')
        ax.text(s_l[0]/2, -39.2, '13 m', color=MUTED, ha='center', va='top', fontsize=9)
        ax.annotate('', xy=(27, 0), xytext=(27, s_r[1]), arrowprops=dict(arrowstyle='<->', color=MUTED))
        ax.plot([s_r[0]+2, 27], [s_r[1], s_r[1]], color=GRID, lw=0.8, ls='--')
        ax.text(28, s_r[1]/2, '22 m\nbehind', color=MUTED, va='center', fontsize=9)
        for s in (s_l, s_r):
            ax.text(s[0], s[1]+2.3, 'slot', color=MUTED, fontsize=9, ha='center', va='bottom')
    ax.set_title(title, loc='left')
    ax.set_xlabel('lateral position in leader frame (m, right +)')
    ax.set_ylabel('along-track position (m, ahead +)')
    ax.grid(color=GRID, lw=0.5, alpha=0.6)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rows = [json.loads(s) for s in (RUN/'steps.jsonl').read_text().splitlines()]
    job = json.loads((RUN/'job.json').read_text())
    geos = [leader_frame(r) for r in rows]
    t = np.array([r['t'] for r in rows])
    form = np.array([g['formation'] for g in geos])
    eL = np.array([g['left']['e'] for g in geos])
    eR = np.array([g['right']['e'] for g in geos])
    k = next(i for i in range(len(t)) if t[i] >= 15 and form[i] > 10)

    fig = plt.figure(figsize=(15, 12.5))
    gs = fig.add_gridspec(2, 2, height_ratios=[1.35, 1], hspace=0.22, wspace=0.18, top=0.93)
    # (a) schematic with illustrative positions
    schem = dict(left=dict(slot=(-13, -22), boat=(-17.5, -27.5)), right=dict(slot=(13, -22), boat=(17.0, -26.5)))
    for s in ['left', 'right']:
        schem[s]['e'] = math.dist(schem[s]['slot'], schem[s]['boat'])
    schem['formation'] = math.sqrt((schem['left']['e']**2+schem['right']['e']**2)/2)
    ax = fig.add_subplot(gs[0, 0])
    draw_frame(ax, schem, '(a) Definition (illustrative positions)', True)
    ax.set_xlim(-36, 36)
    ax.set_ylim(-60, 13)
    ax.text(-35, -59, 'Slot = start-of-run offset, rotated with the leader:\n'
            '  left slot  = P$_L$ − 22·f − 13·r\n  right slot = P$_L$ − 22·f + 13·r',
            fontsize=9.5, color=INK, va='bottom', family='DejaVu Sans Mono',
            bbox=dict(boxstyle='round,pad=0.4', fc='#f4f3ef', ec=GRID))
    ax.text(35, -46, f'formation error = √((e$_L$² + e$_R$²)/2)\n= √(({schem["left"]["e"]:.1f}² + {schem["right"]["e"]:.1f}²)/2) = {schem["formation"]:.1f} m',
            fontsize=10.5, color=INK, ha='right', va='bottom', bbox=dict(boxstyle='round,pad=0.4', fc='#f4f3ef', ec=GRID))
    # (b) real logged instant
    g = geos[k]
    ax = fig.add_subplot(gs[0, 1])
    draw_frame(ax, g, f'(b) Real example: {job["case"]}, seed {job["seed"]}, Kalman OFF, t = {t[k]:.1f} s', False)
    pts = [g['left']['boat'], g['right']['boat'], g['left']['slot'], g['right']['slot'], (0, 0)]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    pad = 9
    ax.set_xlim(min(xs)-pad-6, max(xs)+pad+6)
    ax.set_ylim(min(ys)-pad-8, max(ys)+pad+5)
    ax.text(0.98, 0.03, f'formation error = √(({g["left"]["e"]:.1f}² + {g["right"]["e"]:.1f}²)/2)\n= {g["formation"]:.1f} m  (> 10 m → this frame counts as "broken")',
            transform=ax.transAxes, fontsize=10, ha='right', va='bottom', color=INK,
            bbox=dict(boxstyle='round,pad=0.4', fc='#f4f3ef', ec=GRID))
    # (c) over time
    ax = fig.add_subplot(gs[1, :])
    win = t >= 15
    rmse = math.sqrt(np.mean(form[win]**2))
    broken = 100*np.mean(form[win] > 10)
    ax.axvspan(t[0], 15, color='#f0efea', zorder=0)
    ax.text(5, 0.97, 'not scored\n(accelerating from rest)', transform=ax.get_xaxis_transform(), ha='center', va='top', color=MUTED, fontsize=9)
    for s in range(20, int(job['duration']), 18):
        ax.axvspan(s, s+job['gap'], color='#e4e3dc', zorder=0, lw=0)
    ax.fill_between(t, 10, np.maximum(form, 10), where=win & (form > 10), color=INK, alpha=0.12, lw=0, label='broken frames (> 10 m)')
    ax.plot(t, eL, color=LEFT, lw=1.6, label='e$_L$ (left follower)')
    ax.plot(t, eR, color=RIGHT, lw=1.6, label='e$_R$ (right follower)')
    ax.plot(t, form, color=INK, lw=2.2, label='formation error √((e$_L$²+e$_R$²)/2)')
    ax.axhline(10, color=MUTED, lw=1.2, ls='--')
    ax.text(t[-1], 10.6, '10 m "broken" threshold', ha='right', va='bottom', color=MUTED, fontsize=9)
    ax.axvline(t[k], color=MUTED, lw=1, ls=':')
    ax.text(t[k]+0.8, 0.97, '(b)', transform=ax.get_xaxis_transform(), color=MUTED, va='top')
    ax.set_yscale('log')
    ax.set_ylim(0.5, max(200, form.max()*1.5))
    ax.set_xlim(t[0], t[-1])
    ax.set_xlabel('time since leader starts moving (s); grey bands = scheduled 2 s bbox dropouts')
    ax.set_ylabel('error (m, log scale)')
    ax.set_title('(c) Over a run: per-frame formation error → Final RMSE and broken %', loc='left')
    ax.legend(loc='upper left', bbox_to_anchor=(0.16, 1.0), frameon=False, fontsize=9)
    ax.text(0.99, 0.04, f'Final RMSE (t = 15 s → end) = √(mean of formation error²) = {rmse:.1f} m\n'
            f'broken = share of scored frames above 10 m = {broken:.1f} %', transform=ax.transAxes, ha='right', va='bottom',
            fontsize=10.5, color=INK, bbox=dict(boxstyle='round,pad=0.4', fc='#f4f3ef', ec=GRID))
    ax.grid(color=GRID, lw=0.5, alpha=0.6, which='major')
    fig.suptitle('How formation error is calculated (rollout videos and experiment matrix)', fontsize=14, fontweight='bold', x=0.06, ha='left', y=0.985)
    fig.text(0.06, 0.958, 'Positions come from simulator ground truth (evaluation only — never given to the boats). '
             'Errors are horizontal distances in metres.', color=MUTED, fontsize=10)
    for ext in ['png', 'pdf']:
        fig.savefig(OUT/f'formation_error_explained.{ext}', dpi=200, bbox_inches='tight', facecolor='white')
    print(f'example instant t={t[k]:.1f}s eL={eL[k]:.2f} eR={eR[k]:.2f} formation={form[k]:.2f}; run RMSE={rmse:.2f} broken={broken:.1f}%')


if __name__ == '__main__':
    main()
