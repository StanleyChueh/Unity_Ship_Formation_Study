#!/usr/bin/env python3
"""Videos of the weather/wave conditions, from the exact JPEGs the detector received.

Fixed selection rule (no visual cherry-picking): original-matrix cases use their
preselected middle seed 1702, new held-out cases use the first held-out seed
2701, weather probes their only seed 1701; always the Kalman 'on' arm when it
exists ('off' for single-arm probes). Left-follower front camera, motion
t = -5..60 s at 2x speed. Overlay: thin white box = true leader position
(evaluation-only, so you can see where the leader is even when invisible),
magenta = YOLO box used by the tracker, header = condition + FRESH/COAST/LOST.
Also writes one 3x4 grid video with every condition on the same timeline.
"""
import json
import subprocess
from pathlib import Path
import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
K = ROOT/'Experiments/KalmanStudy'
OUT = ROOT/'Documentation/KalmanStudy/condition_videos'
CONDITIONS = [
    ('C0 calm (sea 0.55)', K/'v2/runs/C0_calm_circle_1702_on'),
    ('C8 rough sea 1.0 + 2 s dropouts', K/'robust_evaluation/e01/runs/C8_clear_speed_s_dropout_2701_on'),
    ('C1 HUGE waves (sea 3.0)', K/'v2/runs/C1_huge_waves_1702_on'),
    ('C10 HUGE waves + S-turn + dropouts', K/'robust_evaluation/e01/runs/C10_huge_waves_s_dropout_2701_on'),
    ('W1 light rain 0.15, sea 1.5', K/'robust_evaluation/e01/runs/W1_rain015_rough_s_2701_on'),
    ('W2 rain 0.25, sea 1.5', K/'robust_development/d03_weather/runs/W2_rain025_rough_s_1701_off'),
    ('C5 rain 0.4, sea 1.0', K/'v2/runs/C5_speed_s_dropout_1702_on'),
    ('C2 HEAVY rain 1.0 + fog', K/'v2/runs/C2_heavy_rain_1702_on'),
    ('W3 night, sea 1.5', K/'robust_development/d03_weather/runs/W3_night_rough_s_1701_off'),
    ('W4 night + rain 0.15', K/'robust_development/d03_weather/runs/W4_night_rain015_rough_s_1701_off'),
    ('C3 DARK storm (rain 1.0, sea 1.5)', K/'v2/runs/C3_dark_storm_1702_on'),
]


def frame(run, row, label, size):
    image = cv2.imread(str(run/'frames'/f'{row["step"]:05d}_LeftFront.jpg'))
    shift = row['height']-1-359   # frozen binary ID-box y encoding, see COORDINATE_CORRECTION.md
    for b in row['left_boxes']:
        if b['id'] == 1:
            cv2.rectangle(image, (b['x']-6, b['y']+shift-6), (b['x']+b['w']+6, b['y']+shift+b['h']+6), (255, 255, 255), 2)
    sel = row['selected'].get('LeftFront', {})
    if sel.get('bbox'):
        x0, y0, x1, y1 = map(int, sel['bbox'])
        cv2.rectangle(image, (x0, y0), (x1, y1), (221, 68, 238), 3)
    st = row['status']['Left']
    state = 'FRESH' if st['target_detected'] and not st['target_stale'] else ('COAST' if st['target_stale'] else 'LOST')
    color = {'FRESH': (80, 220, 80), 'COAST': (0, 179, 255), 'LOST': (60, 60, 255)}[state]
    cv2.rectangle(image, (0, 0), (image.shape[1], 56), (25, 20, 15), -1)
    cv2.putText(image, label, (14, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.15, (255, 255, 255), 2)
    cv2.putText(image, f't={row["t"]:5.1f}s  {state}', (image.shape[1]-360, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.15, color, 2)
    if row['t'] < 12:
        cv2.putText(image, 'weather/waves switch on at t=12 s', (14, 100), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (200, 200, 200), 2)
    if sel.get('forced_loss'):
        cv2.putText(image, 'scheduled bbox dropout', (14, 100), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 179, 255), 2)
    return cv2.resize(image, size, interpolation=cv2.INTER_AREA)


def writer(path, size):
    return subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{size[0]}x{size[1]}',
                             '-r', '20', '-i', '-', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '23', '-pix_fmt', 'yuv420p', str(path)],
                            stdin=subprocess.PIPE)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    data = []
    for label, run in CONDITIONS:
        rows = [json.loads(s) for s in (run/'steps.jsonl').read_text().splitlines()]
        data.append((label, run, rows))
        p = writer(OUT/(label.split()[0]+'.mp4'), (1280, 720))
        for row in rows:
            p.stdin.write(frame(run, row, label, (1280, 720)).tobytes())
        p.stdin.close()
        p.wait()
        print('wrote', label)
    tile, cols = (480, 270), 4
    rows_n = -(-len(data)//cols)
    p = writer(OUT/'ALL_CONDITIONS_grid.mp4', (tile[0]*cols, tile[1]*rows_n))
    for i in range(min(len(r) for _, _, r in data)):
        canvas = np.zeros((tile[1]*rows_n, tile[0]*cols, 3), np.uint8)
        for k, (label, run, rows) in enumerate(data):
            y, x = divmod(k, cols)
            canvas[y*tile[1]:(y+1)*tile[1], x*tile[0]:(x+1)*tile[0]] = frame(run, rows[i], label, tile)
        p.stdin.write(canvas.tobytes())
    p.stdin.close()
    p.wait()
    (OUT/'SOURCES.json').write_text(json.dumps([dict(label=l, run=str(r.relative_to(ROOT))) for l, r, _ in data], indent=2)+'\n')
    print('wrote grid ->', OUT)


if __name__ == '__main__':
    main()
