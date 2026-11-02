#!/usr/bin/env python3
"""Offline check: which way of measuring the leader's box gives the best range signal?

Runs the detector on saved frames, scored against true boat separation (scoring only). Compares the
current full-frame detection with ROI zoom (crop around the previous box, as in the drone tracker's
roi_from idea) and full-frame high resolution, plus range taken from box height or width alone.
"""
import argparse
import json
import math
import time
from pathlib import Path
import cv2
import numpy as np
from ultralytics import YOLO
from make_rollout_videos import load

ROOT = Path(__file__).resolve().parents[2]
EV = ROOT/'Experiments/KalmanStudy/robust_evaluation'
RUNS = [('Clear, speed changes', 'e06_vision_only', 'C8_clear_speed_s_dropout_4903_on_pv', 1),
        ('Huge waves, speed changes', 'e06_vision_only', 'C10_huge_waves_s_dropout_5021_on_pv', 1),
        ('Night, speed changes', 'e06_vision_only', 'W3_night_rough_s_4903_on_pv', 1),
        ('Dark storm lap', 'e05_weather_v2', 'L10_lap_dark_storm_4903_on_rs', 3)]
MODES = {'full 640 (current)': (640, None), 'full 1280': (1280, None), 'ROI 640 px crop': (640, 640), 'ROI 320 px crop': (640, 320)}
DT = 0.1


def detect(model, im, imgsz, crop, center):
    H, W = im.shape[:2]
    x0 = y0 = 0
    if crop is not None:
        x0 = int(np.clip(center[0]-crop/2, 0, max(W-crop, 0)))
        y0 = int(np.clip(center[1]-crop/2, 0, max(H-crop, 0)))
        im = im[y0:y0+crop, x0:x0+crop]
    r = model.predict(im, imgsz=imgsz, conf=0.25, device=0, half=True, verbose=False)[0]
    best = None
    for b in r.boxes:
        if int(b.cls[0]) != 0:
            continue
        s = float(b.conf[0])
        if best is None or s > best[0]:
            best = (s, *[float(v) for v in b.xyxy[0]])
    if best is None:
        return None
    return best[1]+x0, best[2]+y0, best[3]+x0, best[4]+y0


def score(boxes, rt, key, window):
    N = int(round(window/DT))
    tr, ms = [], []
    for k in range(N, len(boxes)):
        a, b = boxes[k], boxes[k-N]
        if a is None or b is None:
            continue
        tr.append(math.log(rt[k]/rt[k-N])/window)
        ms.append(-math.log(key(a)/key(b))/window)
    if len(tr) < 20:
        return None
    tr, ms = np.array(tr), np.array(ms)
    return float(np.sqrt(np.mean((ms-tr)**2))*np.median(rt)), float(np.corrcoef(ms, tr)[0, 1])


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', type=Path)
    a = ap.parse_args()
    model = YOLO(str(ROOT/'best_realistic_v2.pt'))
    report = {}
    for label, batch, name, step in RUNS:
        run = EV/batch/'runs'/name
        rows = [r for r in load(run) if r['t'] >= 15][::step]
        rt = [math.hypot(r['boats'][0]['x']-r['boats'][1]['x'], r['boats'][0]['z']-r['boats'][1]['z']) for r in rows]
        report[label] = {}
        print('\n'+label, len(rows), 'frames', flush=True)
        for mode, (imgsz, crop) in MODES.items():
            boxes, center, spent = [], None, 0.0
            for r in rows:
                im = cv2.imread(str(run/'frames'/f'{r["step"]:05d}_LeftFront.jpg'))
                if center is None:
                    sel = (r['selected'].get('LeftFront') or {}).get('bbox')
                    if sel:
                        center = ((sel[0]+sel[2])/2, (sel[1]+sel[3])/2)
                t = time.perf_counter()
                b = detect(model, im, imgsz, crop, center or (640, 360)) if crop is None or center is not None else None
                spent += time.perf_counter()-t
                boxes.append(b)
                if b is not None:
                    center = ((b[0]+b[2])/2, (b[1]+b[3])/2)
            dt = step*DT
            entry = dict(found_pct=100*np.mean([b is not None for b in boxes]), ms=1000*spent/len(rows))
            keys = {'area': lambda b: math.sqrt(max((b[2]-b[0])*(b[3]-b[1]), 1.0)), 'width': lambda b: max(b[2]-b[0], 1.0), 'height': lambda b: max(b[3]-b[1], 1.0)}
            for kname, key in keys.items():
                for w in [1.0, 2.0]:
                    N = max(1, int(round(w/dt)))
                    s = score(boxes, rt, key, N*DT) if step == 1 else None
                    if step != 1:
                        tr, ms = [], []
                        for k in range(N, len(boxes)):
                            if boxes[k] is not None and boxes[k-N] is not None:
                                tr.append(math.log(rt[k]/rt[k-N])/w)
                                ms.append(-math.log(key(boxes[k])/key(boxes[k-N]))/w)
                        s = (float(np.sqrt(np.mean((np.array(ms)-np.array(tr))**2))*np.median(rt)), float(np.corrcoef(ms, tr)[0, 1])) if len(tr) >= 20 else None
                    entry[f'{kname}_{w:.0f}s'] = s
            report[label][mode] = entry
            f = lambda k: f"{entry[k][0]:.2f}" if entry[k] else '-'
            print(f"  {mode:20s} found {entry['found_pct']:5.1f}% {entry['ms']:5.1f} ms | range-rate RMS m/s, 1 s / 2 s: size {f('area_1s')}/{f('area_2s')}  width {f('width_1s')}/{f('width_2s')}  height {f('height_1s')}/{f('height_2s')}", flush=True)
    if a.out:
        a.out.write_text(json.dumps(report, indent=1)+'\n')


if __name__ == '__main__':
    main()
