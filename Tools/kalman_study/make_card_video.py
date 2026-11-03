#!/usr/bin/env python3
"""Homepage card loop for the website: the follower's own camera, tracking the leader in three conditions.

Unmodified logged camera frames from batch e07_vision_only_on_off (strict vision-only, Kalman ON, seed 4903), left follower.
The brackets are the logged YOLO box of that exact frame. Pixels are not brightened or denoised; the crop only follows
the boat (median-smoothed, offline) so it stays in shot. The window lies between scheduled dropouts, so every frame has a
real detection, and the script stops if one does not. Plays at 2x.
"""
import argparse
import json
from pathlib import Path
import subprocess
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.ndimage import median_filter, uniform_filter1d

ROOT = Path(__file__).resolve().parents[2]
RUNS = ROOT/'Experiments/KalmanStudy/robust_evaluation/e07_vision_only_on_off/runs'
BOLD = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
CASES = [('L07_lap_heavy_rain1.0', 'HEAVY RAIN'), ('L08_lap_night', 'NIGHT'), ('L10_lap_dark_storm', 'DARK STORM')]
W, H, GOOD = 960, 540, (72, 230, 150)
ZOOM, FADE = 1.9, 8


def track(case, seed, arm, side, t0, t1):
    run = RUNS/f'{case}_{seed}_{arm}'
    rows = [json.loads(l) for l in (run/'steps.jsonl').open()]
    rows = [r for r in rows if t0 <= r['t'] < t1 and r.get('step') is not None]
    boxes = [(r.get('selected', {}).get(side+'Front') or {}).get('bbox') for r in rows]
    missing = [r['t'] for r, b in zip(rows, boxes) if not b]
    if missing:
        raise SystemExit(f'{case}: no detection at t={missing[:5]}')
    c = np.array([[(b[0]+b[2])/2, (b[1]+b[3])/2] for b in boxes], float)
    c = uniform_filter1d(median_filter(c, size=(9, 1), mode='nearest'), size=9, axis=0, mode='nearest')
    return run, rows, boxes, c


def bracket(d, x0, y0, x1, y1, n=11, w=3):
    for sx, ex, sy, ey in [(x0, x0+n, y0, y0+n), (x1, x1-n, y0, y0+n), (x0, x0+n, y1, y1-n), (x1, x1-n, y1, y1-n)]:
        d.line((sx, sy, ex, sy), fill=GOOD, width=w)
        d.line((sx, sy, sx, ey), fill=GOOD, width=w)


def strip(data, k, sw, side, label, font):
    run, rows, boxes, c = data
    cw, ch = int(sw/ZOOM), int(H/ZOOM)
    img = cv2.imread(str(run/'frames'/f'{rows[k]["step"]:05d}_{side}Front.jpg'))
    x0 = int(np.clip(c[k, 0]-cw*0.42, 0, img.shape[1]-cw))   # boat left of centre, wake trails across the strip
    y0 = int(np.clip(c[k, 1]-ch*0.48, 0, img.shape[0]-ch))
    crop = cv2.resize(img[y0:y0+ch, x0:x0+cw], (sw, H), interpolation=cv2.INTER_CUBIC)
    P = Image.fromarray(crop[:, :, ::-1]).convert('RGBA')
    scrim = Image.new('RGBA', (sw, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(scrim)
    for i in range(110):
        sd.line((0, H-i, sw, H-i), fill=(0, 0, 0, int(190*(1-i/110))))
    P = Image.alpha_composite(P, scrim).convert('RGB')
    d = ImageDraw.Draw(P)
    b = boxes[k]
    pad = 7
    bracket(d, (b[0]-x0)*ZOOM-pad, (b[1]-y0)*ZOOM-pad, (b[2]-x0)*ZOOM+pad, (b[3]-y0)*ZOOM+pad)
    d.text((18, H-46), label, font=font, fill=(255, 255, 255))
    return np.asarray(P)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--seed', type=int, default=4903)
    ap.add_argument('--arm', default='on_pv')
    ap.add_argument('--side', default='Left')
    ap.add_argument('--start', type=float, default=41.0)
    ap.add_argument('--end', type=float, default=55.0)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    font = ImageFont.truetype(BOLD, 24)
    data = [track(c, a.seed, a.arm, a.side, a.start, a.end) for c, _ in CASES]
    n = min(len(d[1]) for d in data)
    sw = W//len(CASES)
    frames = []
    for k in range(n):
        tiles = [strip(d, k, sw if i < len(CASES)-1 else W-sw*(len(CASES)-1), a.side, CASES[i][1], font) for i, d in enumerate(data)]
        f = np.hstack(tiles)
        for i in range(1, len(CASES)):
            f[:, sw*i-1:sw*i+1] = 0
        frames.append(f)
    for i in range(FADE):   # blend the tail into the head so the loop has no hard cut
        w = (i+1)/(FADE+1)
        frames[n-FADE+i] = (frames[n-FADE+i]*(1-w)+frames[i]*w).astype(np.uint8)
    frames = frames[:n-1]
    Image.fromarray(frames[0]).save(a.out.with_suffix('.jpg'), quality=88)
    p = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', '20', '-i', '-', '-an',
                          '-c:v', 'libx264', '-crf', '27', '-preset', 'slow', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(a.out)], stdin=subprocess.PIPE)
    for f in frames:
        p.stdin.write(f.tobytes())
    p.stdin.close()
    p.wait()
    print('wrote', a.out, a.out.stat().st_size//1024, 'KB', len(frames), 'frames')


if __name__ == '__main__':
    main()
