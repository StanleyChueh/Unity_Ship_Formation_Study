#!/usr/bin/env python3
"""Side-by-side rollout videos of all arms for every condition (report package).

Fixed seed rule (no visual cherry-picking): e02 primary cases use the preselected
middle seed 4409 (of 8), e02 secondary cases 4153 (middle of 4), e02x all-weather
cases their first seed 4903. One extra video shows the documented KF failure
(C10 seed 4513), labelled as such. Frames are the exact JPEGs the detector got
(left follower front camera); overlays: white = true leader box (evaluation
only), magenta = YOLO box used, orange line = estimate the controller used.
Each tile also has a leader-centred top-down map (rings = formation slots) and
the running formation error. 20 fps = 2x real time.
"""
import argparse
import json
import math
import os
from multiprocessing import Pool
import subprocess
from pathlib import Path
import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
EV = ROOT/'Experiments/KalmanStudy/robust_evaluation'
ARMS = [('on_rs', 'KALMAN ON: KF range/speed fusion', (62, 168, 46)),
        ('off_short', 'KALMAN OFF: production (finite-diff, 0.6 s hold)', (150, 150, 150)),
        ('off_rs', 'Non-Kalman filter: EMA + 3 s coast', (0, 190, 230)),
        ('raw', 'No tracker filter (bbox gate kept)', (60, 60, 230)),
        ('raw_nogate', 'NO bbox filtering at all', (200, 80, 200))]
SHORT = dict(on_rs='Kalman ON', off_short='Kalman OFF (production)', off_rs='EMA filter (non-Kalman)', raw='No tracker filter', raw_nogate='No bbox filtering at all')
CLEAN_LABEL = dict(on_rs='KALMAN ON', off_short='KALMAN OFF', off_rs='EMA FILTER', raw='NO tracker filter', raw_nogate='NO bbox filtering')
MOTION = dict(circle='FIXED circle R360 @18 m/s',
              variable='NON-FIXED: 14>20>10>18 m/s + S-turns',
              unexpected='NON-FIXED: unexpected turn')
# Fixed trajectory: one COMPLETE R360 circle lap (135 s) under every weather/wave level (e03_laps).
LAPS = [(f'L{k:02d}_'+n, 4903) for k, n in enumerate(['lap_calm', 'lap_rough_sea1.5', 'lap_huge_waves_sea3', 'lap_light_rain0.15',
        'lap_rain0.25', 'lap_rain0.4', 'lap_heavy_rain1.0', 'lap_night', 'lap_night_rain0.15', 'lap_dark_storm'], 1)]
# Non-fixed trajectories (speed changes + S-turns / unexpected turn), 60 s.
NONFIXED = [('C8_clear_speed_s_dropout', 4409), ('C10_huge_waves_s_dropout', 4409), ('W1_rain015_rough_s', 4409),
            ('W2_rain025_rough_s', 4903), ('C5_speed_s_dropout', 4903), ('W3_night_rough_s', 4903),
            ('W4_night_rain015_rough_s', 4903), ('C7_unseen_turn_8s', 4153), ('C10_huge_waves_s_dropout', 4513)]
# W1-W4 weather on a non-fixed path that completes a full circle (e04_wlaps).
WLAPS = [(n, 4903) for n in ['WL1_lap_rain0.15_nonfixed', 'WL2_lap_rain0.25_nonfixed', 'WL3_lap_night_nonfixed', 'WL4_lap_night_rain0.15_nonfixed']]
CASES = LAPS+WLAPS+NONFIXED


def run_dir(case, seed, arm):
    # KS_BATCHES (comma list) selects other batches, e.g. e05_weather_v2 (detector v2 re-run).
    for batch in os.environ.get('KS_BATCHES', 'e02,e02x,e03_laps,e04_wlaps').split(','):
        d = EV/batch/'runs'/f'{case}_{seed}_{arm}'
        if (d/'bridge.complete').exists() and (d/'unity.complete').exists():
            return d
    return None


def load(d):
    rows = [json.loads(s) for s in (d/'steps.jsonl').read_text().splitlines()]
    shift = rows[0]['height']-1-359   # frozen binary ID-box y encoding (COORDINATE_CORRECTION.md)
    for r in rows:
        for k in ['left_boxes', 'right_boxes']:
            for b in r[k]:
                b['y'] += shift
    return rows


def errors(r):
    leader = r['boats'][0]
    fx, fz = leader['fx'], leader['fz']
    n = math.hypot(fx, fz)
    fx, fz = fx/n, fz/n
    out = []
    for side, bi in [('left', 1), ('right', 2)]:
        back, lat = r[side+'_back'], r[side+'_side']
        tx, tz = leader['x']+fx*back+fz*lat, leader['z']+fz*back-fx*lat
        out.append(math.hypot(r['boats'][bi]['x']-tx, r['boats'][bi]['z']-tz))
    return out, (fx, fz)


def tile(d, r, label, color, rms, hist):
    T = np.zeros((515, 640, 3), np.uint8)
    img = cv2.imread(str(d/'frames'/f'{r["step"]:05d}_LeftFront.jpg'))
    for b in r['left_boxes']:
        if b['id'] == 1:
            cv2.rectangle(img, (b['x']-5, b['y']-5), (b['x']+b['w']+5, b['y']+b['h']+5), (255, 255, 255), 2)
    sel = r['selected'].get('LeftFront', {})
    if sel.get('bbox'):
        x0, y0, x1, y1 = map(int, sel['bbox'])
        cv2.rectangle(img, (x0, y0), (x1, y1), (221, 68, 238), 4)
    st = r['status']['Left']
    if st['target_detected'] and st['predicted_offset'] is not None:
        x = int((st['predicted_offset']+1)*0.5*img.shape[1])
        cv2.line(img, (x, 230), (x, 520), (0, 179, 255), 4)
    if sel.get('forced_loss'):
        cv2.putText(img, 'BBOX DROPOUT (scheduled)', (20, 90), cv2.FONT_HERSHEY_SIMPLEX, 1.6, (0, 179, 255), 4)
    T[34:394] = cv2.resize(img, (640, 360), interpolation=cv2.INTER_AREA)
    state = 'FRESH' if st['target_detected'] and not st['target_stale'] else ('COAST' if st['target_stale'] else 'LOST')
    scol = {'FRESH': (80, 220, 80), 'COAST': (0, 179, 255), 'LOST': (60, 60, 255)}[state]
    cv2.rectangle(T, (0, 0), (640, 34), color, -1)
    cv2.putText(T, label, (8, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.85 if len(label) < 20 else 0.62, (0, 0, 0), 2)
    (le, re_), (fx, fz) = errors(r)
    # bottom strip: top-down map + numbers
    m = np.full((121, 121, 3), 30, np.uint8)
    leader = r['boats'][0]
    def px(x, z):
        dx, dz = x-leader['x'], z-leader['z']
        a, l = dx*fx+dz*fz, dx*fz-dz*fx
        return int(60+l*1.6), int(40-a*1.6)
    for side, bi, c in [('left', 1, (255, 170, 60)), ('right', 2, (60, 200, 255))]:
        back, lat = r[side+'_back'], r[side+'_side']
        cv2.circle(m, px(leader['x']+fx*back+fz*lat, leader['z']+fz*back-fx*lat), 6, (140, 140, 140), 1)
        cv2.circle(m, px(r['boats'][bi]['x'], r['boats'][bi]['z']), 4, c, -1)
    cv2.circle(m, (60, 40), 5, (80, 80, 255), -1)
    T[394:515, 0:121] = m
    hist.append(rms)
    run_rmse = math.sqrt(np.mean(np.square(hist)))
    broken = 100*np.mean(np.array(hist) > 10)
    cv2.putText(T, f'{state}', (135, 425), cv2.FONT_HERSHEY_SIMPLEX, 0.9, scol, 2)
    cv2.putText(T, f'formation error now {rms:6.1f} m', (135, 458), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (235, 235, 235), 1)
    cv2.putText(T, f'L {le:5.1f} m   R {re_:5.1f} m', (135, 484), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1)
    cv2.putText(T, f'RMSE so far {run_rmse:6.1f} m   broken {broken:4.1f} %', (135, 508), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1)
    return T


def plot_tile(series, t_now, job, final, width=640):
    T = np.full((515, width, 3), 22, np.uint8)
    x0, x1, y0, y1, ymax = 60, width-15, 40, 380, 400.0
    def X(t): return int(x0+(t+5)/(job['duration']+5)*(x1-x0))
    def Y(e): return int(y1-math.log10(1+min(e, ymax))/math.log10(1+ymax)*(y1-y0))
    if job['gap']:
        for s in ([20] if job['case'].startswith('C7') else range(20, int(job['duration']), 18)):
            cv2.rectangle(T, (X(s), y0), (X(min(job['duration'], s+job['gap'])), y1), (60, 60, 60), -1)
    for tick in [2, 5, 10, 30, 100, 300]:
        cv2.line(T, (x0, Y(tick)), (x1, Y(tick)), (200, 200, 200) if tick == 10 else (70, 70, 70), 1)
        cv2.putText(T, f'{tick} m', (6, Y(tick)+4), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (170, 170, 170), 1)
    cv2.rectangle(T, (x0, y0), (x1, y1), (110, 110, 110), 1)
    for arm, label, color in ARMS:
        if arm not in series:
            continue
        t, e = series[arm]
        k = sum(1 for v in t if v <= t_now)
        if k > 1:
            cv2.polylines(T, [np.array([[X(a), Y(b)] for a, b in zip(t[:k], e[:k])], np.int32)], False, color, 2)
    cv2.line(T, (X(t_now), y0), (X(t_now), y1), (255, 255, 255), 1)
    cv2.putText(T, 'Formation error (m, log scale) vs time; gray = bbox dropouts', (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (235, 235, 235), 1)
    y = 405
    cv2.putText(T, f'Final RMSE t=15-{job["duration"]:.0f} s (this seed):', (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (235, 235, 235), 1)
    for arm, label, color in ARMS:
        if arm in final:
            y += 21
            cv2.putText(T, f'{SHORT[arm]:24s} {final[arm]:7.1f} m', (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
    return T


def render(item):
    case, seed, out_dir, keep, clean = item
    arms = [x for x in ARMS if keep is None or x[0] in keep]
    dirs = {a: run_dir(case, seed, a) for a, _, _ in arms}
    dirs = {a: d for a, d in dirs.items() if d is not None}
    if 'on_rs' not in dirs:
        return f'skip {case} {seed}: no KF run'
    data = {a: load(d) for a, d in dirs.items()}
    job = json.loads((next(iter(dirs.values()))/'job.json').read_text())
    series, final = {}, {}
    for a, rows in data.items():
        t = [r['t'] for r in rows]
        e = [math.sqrt(np.mean(np.square(errors(r)[0]))) for r in rows]
        series[a] = (t, e)
        sel = [v for tt, v in zip(t, e) if 15 <= tt <= job['duration']]
        final[a] = math.sqrt(np.mean(np.square(sel)))
    failure = case.startswith('C10') and seed == 4513
    name = f'{case}_seed{seed}' + ('_KF_FAILURE_EXAMPLE' if failure else '') + (f'_{len(arms)}way' if keep else '')
    W, H = 1920, (1030 if clean else 1080)
    top = 0 if clean else 50
    p = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{W}x{H}', '-r', '20', '-i', '-',
                          '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '24', '-pix_fmt', 'yuv420p', str(out_dir/f'{name}.mp4')], stdin=subprocess.PIPE)
    hist = {a: [] for a in data}
    n = min(len(r) for r in data.values())
    weather = f'sea {job["sea"]}  rain {job["rain"]}  fog {job["fog"]}  {"NIGHT" if job["dark"] else "day"}  bbox dropouts {job["gap"]} s'
    ref = data['on_rs']
    turned = [0.0]
    for a_, b_ in zip(ref, ref[1:]):
        h0 = math.atan2(a_['boats'][0]['fx'], a_['boats'][0]['fz'])
        h1 = math.atan2(b_['boats'][0]['fx'], b_['boats'][0]['fz'])
        turned.append(turned[-1]+abs((h1-h0+math.pi) % (2*math.pi)-math.pi))
    for i in range(n):
        canvas = np.zeros((H, W, 3), np.uint8)
        lap = f'  |  lap {min(100.0, math.degrees(turned[i])/3.6):5.1f} %' if job['motion'] == 'circle' else ''
        title = f'{case}  |  {weather}  |  {MOTION[job["motion"]]}{lap}  |  seed {seed}  |  2x'
        if failure:
            title = 'DOCUMENTED KF FAILURE CASE  |  '+title
        if not clean:
            cv2.putText(canvas, title, (10, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.70, (0, 120, 255) if failure else (255, 255, 255), 2)
        slots = [(0, top), (640, top), (1280, top), (0, top+515), (640, top+515), (1280, top+515)]
        for k, (a, label, color) in enumerate(arms):
            x, y = slots[k]
            if a in data:
                row = data[a][i]
                canvas[y:y+515, x:x+640] = tile(dirs[a], row, CLEAN_LABEL[a] if clean else label, color, math.sqrt(np.mean(np.square(errors(row)[0]))), hist[a])
            else:
                cv2.putText(canvas, f'{label}: not run for this case', (x+20, y+250), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (150, 150, 150), 1)
        if len(arms) <= 3:
            canvas[top+515:top+1030, 0:1920] = plot_tile(series, data['on_rs'][i]['t'], job, final, width=1920)
        else:
            canvas[top+515:top+1030, 1280:1920] = plot_tile(series, data['on_rs'][i]['t'], job, final)
        p.stdin.write(canvas.tobytes())
    p.stdin.close()
    p.wait()
    return f'wrote {name}.mp4 ({len(dirs)} arms)'


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', type=Path, default=ROOT/'Documentation/KalmanStudy/REPORT_PACKAGE/rollout_videos')
    ap.add_argument('--only', default=None, help='comma list of case prefixes')
    ap.add_argument('--workers', type=int, default=4)
    ap.add_argument('--arms', default=None, help='subset, e.g. on_rs,off_short,raw_nogate')
    ap.add_argument('--clean', action='store_true', help='no top title bar; short method labels')
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    keep = set(a.arms.split(',')) if a.arms else None
    items = [(c, s, a.out, keep, a.clean) for c, s in CASES if not a.only or c.split('_')[0] in a.only.split(',')]
    with Pool(a.workers) as pool:
        for msg in pool.imap_unordered(render, items):
            print(msg, flush=True)


if __name__ == '__main__':
    main()
