#!/usr/bin/env python3
"""One video per condition: rows = KALMAN ON / KALMAN OFF / NO bbox filtering,
each row = top view (plotted from logged true positions) + left follower front camera +
right follower front camera; right panel = formation error of the three methods over time.

Fixed seed 4903 (same runs as the 3-way videos and their matrices). Camera frames are the
exact JPEGs the detector received; white box = true leader (evaluation only), magenta =
YOLO box used, orange line = position the method steers to. 1920x1080, 20 fps = 2x speed.
"""
import argparse
import json
import math
import os
from multiprocessing import Pool
from pathlib import Path
import subprocess
import cv2
import numpy as np
from make_rollout_videos import load, errors, run_dir

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT/'Documentation/KalmanStudy/REPORT_PACKAGE/rollout_videos_views'
ARMS = [('on_rs', 'KALMAN ON', (62, 168, 46)), ('off_short', 'KALMAN OFF', (155, 155, 155)), ('raw_nogate', 'NO bbox filtering', (200, 80, 200))]
CASES = [(f'L{k:02d}_'+n, 4903) for k, n in enumerate(['lap_calm', 'lap_rough_sea1.5', 'lap_huge_waves_sea3', 'lap_light_rain0.15',
         'lap_rain0.25', 'lap_rain0.4', 'lap_heavy_rain1.0', 'lap_night', 'lap_night_rain0.15', 'lap_dark_storm'], 1)]
CASES += [(n, 4903) for n in ['WL1_lap_rain0.15_nonfixed', 'WL2_lap_rain0.25_nonfixed', 'WL3_lap_night_nonfixed', 'WL4_lap_night_rain0.15_nonfixed']]
ROW_H, HEAD_H, TOP_W, CAM_W, CAM_H, PANEL_X = 360, 30, 326, 537, 302, 1400
LEFT_C, RIGHT_C = (214, 120, 42), (52, 104, 235)   # BGR of #2a78d6 / #eb6834


def state_of(st):
    return 'FRESH' if st['target_detected'] and not st['target_stale'] else ('COAST' if st['target_stale'] else 'LOST')


def camera(run, row, side):
    img = cv2.imread(str(run/'frames'/f'{row["step"]:05d}_{side}Front.jpg'))
    for b in row['left_boxes' if side == 'Left' else 'right_boxes']:
        if b['id'] == 1:
            cv2.rectangle(img, (b['x']-6, b['y']-6), (b['x']+b['w']+6, b['y']+b['h']+6), (255, 255, 255), 3)
    sel = row['selected'].get(side+'Front', {})
    if sel.get('bbox'):
        x0, y0, x1, y1 = map(int, sel['bbox'])
        cv2.rectangle(img, (x0, y0), (x1, y1), (221, 68, 238), 5)
    st = row['status'][side]
    if st['target_detected'] and st['predicted_offset'] is not None:
        x = int((st['predicted_offset']+1)*0.5*img.shape[1])
        cv2.line(img, (x, 220), (x, 520), (0, 179, 255), 6)
    img = cv2.resize(img, (CAM_W, CAM_H), interpolation=cv2.INTER_AREA)
    s = state_of(st)
    col = {'FRESH': (80, 220, 80), 'COAST': (0, 179, 255), 'LOST': (60, 60, 255)}[s]
    cv2.rectangle(img, (0, 0), (CAM_W, 26), (20, 20, 20), -1)
    cv2.putText(img, f'{side} follower camera', (8, 19), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (235, 235, 235), 1)
    cv2.putText(img, s, (CAM_W-90, 19), cv2.FONT_HERSHEY_SIMPLEX, 0.6, col, 2)
    if sel.get('forced_loss'):
        cv2.putText(img, 'BBOX DROPOUT', (8, 52), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 179, 255), 2)
    return img


def top_view(rows, i, trail):
    """World frame (north up), centred on the leader; zooms out (min +-32 m) to keep all boats in view."""
    T = np.full((TOP_W, TOP_W, 3), (52, 38, 24), np.uint8)
    r = rows[i]
    L = r['boats'][0]
    far = max(math.hypot(b['x']-L['x'], b['z']-L['z']) for b in r['boats'][1:])
    half = max(32.0, far*1.15+6)
    scale = TOP_W/(2*half)
    def px(x, z):
        return int(TOP_W/2+(x-L['x'])*scale), int(TOP_W/2-(z-L['z'])*scale)
    step = 10 if half < 60 else (50 if half < 300 else 200)
    for g in range(-int(half)//step*step, int(half)+1, step):
        cv2.line(T, (int(TOP_W/2+g*scale), 0), (int(TOP_W/2+g*scale), TOP_W), (70, 56, 42), 1)
        cv2.line(T, (0, int(TOP_W/2+g*scale)), (TOP_W, int(TOP_W/2+g*scale)), (70, 56, 42), 1)
    for bi, color in [(0, (90, 90, 255)), (1, LEFT_C), (2, RIGHT_C)]:
        pts = np.array([px(rows[j]['boats'][bi]['x'], rows[j]['boats'][bi]['z']) for j in range(max(0, i-trail), i+1)], np.int32)
        if len(pts) > 1:
            cv2.polylines(T, [pts], False, tuple(int(c*0.6) for c in color), 1, cv2.LINE_AA)
    (eL, eR), (fx, fz) = errors(r)
    for side, bi, color, e in [('left', 1, LEFT_C, eL), ('right', 2, RIGHT_C, eR)]:
        back, lat = r[side+'_back'], r[side+'_side']
        slot = (L['x']+fx*back+fz*lat, L['z']+fz*back-fx*lat)
        b = r['boats'][bi]
        cv2.circle(T, px(*slot), 6, (200, 200, 200), 1, cv2.LINE_AA)
        cv2.line(T, px(*slot), px(b['x'], b['z']), color, 2, cv2.LINE_AA)
        cv2.circle(T, px(b['x'], b['z']), 6, color, -1, cv2.LINE_AA)
    c = np.array(px(L['x'], L['z']))
    f = np.array([fx, -fz])
    n = np.array([fz, fx])
    tri = np.array([c+f*11, c-f*7+n*6, c-f*7-n*6], np.int32)
    cv2.fillPoly(T, [tri], (90, 90, 255), cv2.LINE_AA)
    cv2.line(T, (10, TOP_W-14), (int(10+step*scale), TOP_W-14), (230, 230, 230), 2)
    cv2.putText(T, f'{step} m', (12, TOP_W-20), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (230, 230, 230), 1)
    cv2.putText(T, 'top view (N up)', (8, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (235, 235, 235), 1)
    return T


def panel(case, job, series, t_now, hist, final, turned):
    P = np.full((1080, 1920-PANEL_X, 3), 22, np.uint8)
    W = P.shape[1]
    cv2.putText(P, case.split('_')[0], (14, 34), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
    if os.environ.get('KS_DETECTOR_LABEL'):
        cv2.putText(P, os.environ['KS_DETECTOR_LABEL'], (110, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 179, 255), 2)
    desc = f'sea {job["sea"]}  rain {job["rain"]}{"  NIGHT" if job["dark"] else ""}'
    motion = 'fixed circle R360' if job['motion'] == 'circle' else 'non-fixed: straight, then full turn'
    cv2.putText(P, desc, (14, 64), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (220, 220, 220), 1)
    cv2.putText(P, motion, (14, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (220, 220, 220), 1)
    cv2.putText(P, f'lap {min(100.0, turned/3.6):5.1f} %   t = {t_now:5.1f} s', (14, 118), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (220, 220, 220), 1)
    x0, x1, y0, y1, ymax = 52, W-14, 150, 600, 400.0
    def X(t): return int(x0+(t+5)/(job['duration']+5)*(x1-x0))
    def Y(e): return int(y1-math.log10(1+min(e, ymax))/math.log10(1+ymax)*(y1-y0))
    if job['gap']:
        for s in range(20, int(job['duration']), 18):
            cv2.rectangle(P, (X(s), y0), (X(min(job['duration'], s+job['gap'])), y1), (58, 58, 58), -1)
    for tick in [2, 5, 10, 30, 100, 300]:
        cv2.line(P, (x0, Y(tick)), (x1, Y(tick)), (205, 205, 205) if tick == 10 else (62, 62, 62), 1)
        cv2.putText(P, f'{tick}', (10, Y(tick)+4), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (170, 170, 170), 1)
    cv2.rectangle(P, (x0, y0), (x1, y1), (110, 110, 110), 1)
    cv2.putText(P, 'formation error (m, log)', (x0, y0-10), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (235, 235, 235), 1)
    for arm, label, color in ARMS:
        if arm in series:
            t, e = series[arm]
            k = sum(1 for v in t if v <= t_now)
            if k > 1:
                cv2.polylines(P, [np.array([[X(a), Y(b)] for a, b in zip(t[:k], e[:k])], np.int32)], False, color, 2, cv2.LINE_AA)
    cv2.line(P, (X(t_now), y0), (X(t_now), y1), (255, 255, 255), 1)
    cv2.putText(P, 'time (s); grey = scheduled bbox dropouts' if job['gap'] else 'time (s); natural detection losses only',
                (x0, y1+22), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (170, 170, 170), 1)
    y = 668
    cv2.putText(P, 'now      RMSE so far   broken', (150, y-28), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (190, 190, 190), 1)
    for arm, label, color in ARMS:
        if arm not in hist:
            continue
        h = hist[arm]
        cv2.rectangle(P, (14, y-16), (30, y), color, -1)
        cv2.putText(P, label.replace(' bbox filtering', ' bbox'), (36, y-2), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (235, 235, 235), 1)
        cv2.putText(P, f'{h[-1]:6.1f} m  {math.sqrt(np.mean(np.square(h))):7.1f} m  {100*np.mean(np.array(h) > 10):5.1f} %',
                    (150, y+20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (235, 235, 235), 1)
        y += 62
    y += 10
    cv2.putText(P, f'Final RMSE (t=15-{job["duration"]:.0f} s):', (14, y), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (235, 235, 235), 1)
    for arm, label, color in ARMS:
        if arm in final:
            y += 28
            cv2.putText(P, f'{label:18s} {final[arm]:7.1f} m', (14, y), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)
    y += 44
    for txt, col in [('white box = true leader (eval only)', (230, 230, 230)), ('magenta = YOLO box used', (221, 68, 238)),
                     ('orange line = where it steers', (0, 179, 255)), ('top view: ring = slot, line = error', (200, 200, 200))]:
        cv2.putText(P, txt, (14, y), cv2.FONT_HERSHEY_SIMPLEX, 0.45, col, 1)
        y += 22
    return P


def render(item):
    case, seed, out = item
    dirs = {a: run_dir(case, seed, a) for a, _, _ in ARMS}
    if any(d is None for d in dirs.values()):
        return f'skip {case}: missing runs'
    data = {a: load(d) for a, d in dirs.items()}
    job = json.loads((dirs['on_rs']/'job.json').read_text())
    series, final = {}, {}
    for a, rows in data.items():
        t = [r['t'] for r in rows]
        e = [math.sqrt(np.mean(np.square(errors(r)[0]))) for r in rows]
        series[a] = (t, e)
        final[a] = math.sqrt(np.mean(np.square([v for tt, v in zip(t, e) if 15 <= tt <= job['duration']])))
    ref = data['on_rs']
    turned = [0.0]
    for a_, b_ in zip(ref, ref[1:]):
        h0 = math.atan2(a_['boats'][0]['fx'], a_['boats'][0]['fz'])
        h1 = math.atan2(b_['boats'][0]['fx'], b_['boats'][0]['fz'])
        turned.append(turned[-1]+math.degrees(abs((h1-h0+math.pi) % (2*math.pi)-math.pi)))
    name = f'{case}_seed{seed}_views'
    p = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', '1920x1080', '-r', '20', '-i', '-',
                          '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '24', '-pix_fmt', 'yuv420p', str(out/f'{name}.mp4')], stdin=subprocess.PIPE)
    hist = {a: [] for a in data}
    n = min(len(r) for r in data.values())
    for i in range(n):
        canvas = np.zeros((1080, 1920, 3), np.uint8)
        for k, (a, label, color) in enumerate(ARMS):
            rows = data[a]
            row = rows[i]
            y = k*ROW_H
            e_now = math.sqrt(np.mean(np.square(errors(row)[0])))
            hist[a].append(e_now)
            cv2.rectangle(canvas, (0, y), (PANEL_X, y+HEAD_H), color, -1)
            cv2.putText(canvas, label, (10, y+22), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 0, 0), 2)
            cv2.putText(canvas, f'formation error {e_now:6.1f} m', (PANEL_X-300, y+22), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 0), 2)
            canvas[y+HEAD_H:y+HEAD_H+TOP_W, 0:TOP_W] = top_view(rows, i, 150)
            cy = y+HEAD_H+(ROW_H-HEAD_H-CAM_H)//2
            canvas[cy:cy+CAM_H, TOP_W:TOP_W+CAM_W] = camera(dirs[a], row, 'Left')
            canvas[cy:cy+CAM_H, TOP_W+CAM_W:TOP_W+2*CAM_W] = camera(dirs[a], row, 'Right')
        canvas[:, PANEL_X:] = panel(case, job, series, data['on_rs'][i]['t'], hist, final, turned[i])
        p.stdin.write(canvas.tobytes())
    p.stdin.close()
    p.wait()
    return f'wrote {name}.mp4 (leader turned {turned[-1]:.0f} deg)'


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', type=Path, default=OUT)
    ap.add_argument('--only', default=None)
    ap.add_argument('--workers', type=int, default=4)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    items = [(c, s, a.out) for c, s in CASES if not a.only or c.split('_')[0] in a.only.split(',')]
    with Pool(a.workers) as pool:
        for msg in pool.imap_unordered(render, items):
            print(msg, flush=True)


if __name__ == '__main__':
    main()
