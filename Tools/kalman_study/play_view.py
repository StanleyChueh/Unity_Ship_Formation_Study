#!/usr/bin/env python3
"""Live / replay viewer for play_case.py (or any study) run folders.

The study simulator renders the boat cameras off-screen, so its own window does
not update. This viewer shows the exact frames the detector received for both
followers, plus a top-down formation map, as they are written.

  python Tools/kalman_study/play_view.py              # follow the newest user_play run live
  python Tools/kalman_study/play_view.py RUN_DIR      # replay a finished run
Keys: q quit, space pause, +/- replay speed.
Overlays: white = true leader box (evaluation only), magenta = YOLO box used,
orange line = tracker estimate the controller used. Status FRESH/COAST/LOST.
"""
import json
import math
import sys
import time
from pathlib import Path
import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]


def newest():
    runs = sorted((ROOT/'Experiments/KalmanStudy/user_play').glob('*/steps.jsonl'), key=lambda p: p.stat().st_mtime)
    if not runs:
        raise SystemExit('No user_play run yet; start play_case.py first.')
    return runs[-1].parent


def rows_of(path, start=0):
    with open(path/'steps.jsonl') as f:
        lines = f.read().splitlines()
    out = []
    for line in lines[start:]:
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            break   # line still being written
    return out


def panel(run, row, side):
    image = cv2.imread(str(run/'frames'/f'{row["step"]:05d}_{side}Front.jpg'))
    if image is None:
        return np.zeros((360, 640, 3), np.uint8)
    shift = row['height']-1-359   # frozen 720p StudyRig ID-box y encoding (COORDINATE_CORRECTION.md)
    for b in row['left_boxes' if side == 'Left' else 'right_boxes']:
        if b['id'] == 1:
            y = b['y']+shift
            cv2.rectangle(image, (b['x'], y), (b['x']+b['w'], y+b['h']), (255, 255, 255), 3)
    sel = row['selected'].get(side+'Front', {})
    if sel.get('bbox'):
        x0, y0, x1, y1 = map(int, sel['bbox'])
        cv2.rectangle(image, (x0, y0), (x1, y1), (221, 68, 238), 3)
    st = row['status'][side]
    if st['target_detected'] and st['predicted_offset'] is not None:
        x = int((st['predicted_offset']+1)*0.5*image.shape[1])
        cv2.line(image, (x, 220), (x, 540), (0, 179, 255), 3)
    label = 'FRESH' if st['target_detected'] and not st['target_stale'] else ('COAST' if st['target_stale'] else 'LOST')
    color = {'FRESH': (80, 220, 80), 'COAST': (0, 179, 255), 'LOST': (60, 60, 255)}[label]
    cv2.rectangle(image, (0, 0), (image.shape[1], 50), (38, 27, 21), -1)
    c = row['controls'][side]
    cv2.putText(image, f'{side} follower  {label}  thr {c["throttle"]:.2f}  steer {c["steer"]:+.2f}',
                (12, 36), cv2.FONT_HERSHEY_SIMPLEX, 1.0, color, 2)
    if sel.get('forced_loss'):
        cv2.putText(image, 'YOLO box suppressed (scheduled test)', (12, 90), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 179, 255), 2)
    return cv2.resize(image, (640, 360))


def minimap(row, trail):
    m = np.full((360, 360, 3), 28, np.uint8)
    leader, left, right = row['boats']
    fx, fz = leader['fx'], leader['fz']
    n = math.hypot(fx, fz)
    fx, fz = fx/n, fz/n
    def to_px(x, z):   # leader-centred, leader heading up, 1 px = 0.25 m
        dx, dz = x-leader['x'], z-leader['z']
        ahead, lateral = dx*fx+dz*fz, dx*fz-dz*fx
        return int(180+lateral*4), int(140-ahead*4)
    for side, boat in [('left', left), ('right', right)]:
        back, lat = row[side+'_back'], row[side+'_side']
        tx, tz = leader['x']+fx*back+fz*lat, leader['z']+fz*back-fx*lat
        cv2.circle(m, to_px(tx, tz), 7, (120, 120, 120), 1)
        err = math.hypot(boat['x']-tx, boat['z']-tz)
        cv2.circle(m, to_px(boat['x'], boat['z']), 6, (255, 170, 60) if side == 'left' else (60, 200, 255), -1)
        cv2.putText(m, f'{side} err {err:5.1f} m', (8, 300 if side == 'left' else 325), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (230, 230, 230), 1)
    cv2.circle(m, (180, 140), 7, (80, 80, 255), -1)
    cv2.putText(m, f't={row["t"]:5.1f}s  leader {leader["speed"]:4.1f} m/s', (8, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (230, 230, 230), 1)
    cv2.putText(m, 'red=leader  rings=formation slots', (8, 350), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (170, 170, 170), 1)
    return m


def main():
    run = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else newest()
    live = len(sys.argv) == 1
    job = json.loads((run/'job.json').read_text())
    title = f'{run.name}  sea={job["sea"]} rain={job["rain"]} dark={job["dark"]} motion={job["motion"]} gap={job["gap"]}'
    cv2.namedWindow('USV run viewer', cv2.WINDOW_NORMAL)
    index, speed, paused, rows = 0, 1.0, False, []
    while True:
        if live or not rows:
            rows += rows_of(run, len(rows))
        if index < len(rows):
            row = rows[index]
            canvas = np.hstack([panel(run, row, 'Left'), panel(run, row, 'Right'), minimap(row, None)])
            canvas = np.vstack([np.full((34, canvas.shape[1], 3), 15, np.uint8), canvas])
            cv2.putText(canvas, title, (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 1)
            cv2.imshow('USV run viewer', canvas)
            if not paused:
                index += 1 if not live else max(1, len(rows)-index)  # live: jump to newest
        elif live and (run/'bridge.complete').exists():
            live = False
        key = cv2.waitKey(int(100/speed) if not live else 50) & 0xFF
        if key == ord('q'):
            break
        if key == ord(' '):
            paused = not paused
        if key in (ord('+'), ord('=')):
            speed = min(8.0, speed*2)
        if key == ord('-'):
            speed = max(0.25, speed/2)
        if not live and index >= len(rows) and not paused:
            time.sleep(0.05)
    cv2.destroyAllWindows()


if __name__ == '__main__':
    main()
