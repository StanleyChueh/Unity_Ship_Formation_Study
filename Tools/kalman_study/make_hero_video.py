#!/usr/bin/env python3
"""Clean 15 s Kalman ON vs OFF video for the project page and README still.

Both runs are strictly vision-only (batch e07_vision_only_on_off, fixed seed 4903, dark storm lap). Shows 30 s of the
run at 2x speed, from just before a scheduled dropout through the next one. Left: what the left follower's camera sees.
Below: the formation from above, in the leader's frame, using logged true positions (scoring only).
"""
import argparse
import json
import math
from pathlib import Path
import subprocess
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from make_rollout_videos import load, errors

ROOT = Path(__file__).resolve().parents[2]
RUNS = ROOT/'Experiments/KalmanStudy/robust_evaluation/e07_vision_only_on_off/runs'
OUT = ROOT/'Documentation/KalmanStudy/REPORT_PACKAGE/vision_only'
BOLD = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
REG = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
F = {(p, s): ImageFont.truetype(p, s) for p in [BOLD, REG] for s in [15, 18, 22, 28, 48]}
METHODS = [('on_pv', 'Kalman ON', (27, 175, 122)), ('off_short_pv', 'Kalman OFF', (42, 120, 214))]
W, H, HEAD, CAM_H = 1280, 720, 56, 360
COL = W//2
SCALE = 5.0   # px per metre in the formation map
ALERT, WARN, GOOD = (233, 84, 84), (240, 170, 40), (80, 215, 130)


def in_dropout(t, gap):
    return gap > 0 and t >= 20 and (t-20) % 18 < gap


def state_text(st, dropped):
    if st['target_detected'] and not st['target_stale'] and not dropped:
        return 'Leader detected', GOOD
    if st['target_detected']:
        return 'Predicting position', WARN
    return 'Leader lost', ALERT


def crop_box(rows):
    cx, cy = [], []
    for r in rows:
        bb = (r['selected'].get('LeftFront') or {}).get('bbox')
        if bb:
            cx.append((bb[0]+bb[2])/2)
            cy.append((bb[1]+bb[3])/2)
    return float(np.median(cx)), float(np.median(cy))


def panel(run, r, name, color, gap, centre):
    P = Image.new('RGB', (COL, H), (18, 20, 24))
    d = ImageDraw.Draw(P)
    d.rectangle((0, 0, COL, HEAD), fill=color)
    d.text((16, 11), name, font=F[BOLD, 28], fill=(255, 255, 255))
    # Camera view, zoomed so the boat is visible.
    img = cv2.imread(str(run/'frames'/f'{r["step"]:05d}_LeftFront.jpg'))
    cw, ch = 800, 450
    x0 = int(np.clip(centre[0]-cw/2, 0, img.shape[1]-cw))
    y0 = int(np.clip(centre[1]-ch/2, 0, img.shape[0]-ch))
    k = COL/cw
    cam = cv2.resize(img[y0:y0+ch, x0:x0+cw], (COL, CAM_H), interpolation=cv2.INTER_AREA)
    P.paste(Image.fromarray(cam[:, :, ::-1]), (0, HEAD))
    st = r['status']['Left']
    bb = (r['selected'].get('LeftFront') or {}).get('bbox')
    if bb:
        d.rectangle(((bb[0]-x0)*k-3, (bb[1]-y0)*k+HEAD-3, (bb[2]-x0)*k+3, (bb[3]-y0)*k+HEAD+3), outline=GOOD, width=3)
    dropped = in_dropout(r['t'], gap)
    text, tcol = state_text(st, dropped)
    if not bb and st['target_detected'] and st['predicted_offset'] is not None:
        px = ((st['predicted_offset']+1)*0.5*img.shape[1]-x0)*k
        py = (centre[1]-y0)*k+HEAD
        d.line((px, py-34, px, py+34), fill=WARN, width=4)
    d.rectangle((0, HEAD, COL, HEAD+38), fill=(10, 12, 16))
    d.ellipse((14, HEAD+11, 30, HEAD+27), fill=tcol)
    d.text((38, HEAD+7), text, font=F[BOLD, 18], fill=(240, 240, 240))
    if dropped:
        label = 'Detector blocked for 2 s'
        tw = d.textlength(label, font=F[BOLD, 22])
        d.rectangle((COL-tw-34, HEAD+CAM_H-46, COL-10, HEAD+CAM_H-10), fill=WARN)
        d.text((COL-tw-22, HEAD+CAM_H-42), label, font=F[BOLD, 22], fill=(20, 20, 20))
    # Formation from above, leader at the top.
    top = HEAD+CAM_H
    mw, mh = 340, H-top
    d.rectangle((0, top, mw, H), fill=(21, 38, 56))
    (eL, eR), (fx, fz) = errors(r)
    L = r['boats'][0]
    cx, cy = mw/2, top+34

    def to_px(x, z):
        dx, dz = x-L['x'], z-L['z']
        return (float(np.clip(cx+(dx*fz-dz*fx)*SCALE, 6, mw-6)), float(np.clip(cy-(dx*fx+dz*fz)*SCALE, top+6, H-6)))
    d.polygon([(cx, cy-13), (cx-10, cy+10), (cx+10, cy+10)], fill=(235, 104, 52))
    for side, bi in [('left', 1), ('right', 2)]:
        back, lat = r[side+'_back'], r[side+'_side']
        slot = to_px(L['x']+fx*back+fz*lat, L['z']+fz*back-fx*lat)
        boat = to_px(r['boats'][bi]['x'], r['boats'][bi]['z'])
        d.line((slot, boat), fill=(255, 255, 255), width=2)
        d.ellipse((slot[0]-11, slot[1]-11, slot[0]+11, slot[1]+11), outline=(205, 215, 225), width=2)
        d.ellipse((boat[0]-8, boat[1]-8, boat[0]+8, boat[1]+8), fill=(250, 250, 250))
    d.text((10, top+8), 'Top view', font=F[REG, 15], fill=(190, 200, 210))
    d.text((cx+16, cy-10), 'Leader', font=F[REG, 15], fill=(235, 235, 235))
    e = math.sqrt((eL**2+eR**2)/2)
    d.text((mw+22, top+56), 'Off formation', font=F[REG, 22], fill=(190, 195, 205))
    d.text((mw+22, top+86), f'{e:.1f} m', font=F[BOLD, 48], fill=(255, 255, 255))
    d.text((mw+22, top+166), 'Ring = assigned slot', font=F[REG, 15], fill=(160, 165, 175))
    d.text((mw+22, top+188), 'Line = distance from it', font=F[REG, 15], fill=(160, 165, 175))
    return P


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--case', default='L10_lap_dark_storm')
    ap.add_argument('--seed', type=int, default=4903)
    ap.add_argument('--start', type=float, default=36.0)
    ap.add_argument('--seconds', type=float, default=30.0)
    ap.add_argument('--still-t', type=float, default=57.5)
    ap.add_argument('--out', type=Path, default=OUT/'hero_on_vs_off.mp4')
    a = ap.parse_args()
    data = {}
    for arm, _, _ in METHODS:
        run = RUNS/f'{a.case}_{a.seed}_{arm}'
        data[arm] = (run, load(run), json.loads((run/'job.json').read_text()))
    centre = crop_box(data['on_pv'][1])
    p = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', '20', '-i', '-', '-an',
                          '-c:v', 'libx264', '-crf', '30', '-preset', 'medium', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(a.out)], stdin=subprocess.PIPE)
    still = None
    idx = {arm: {round(r['t'], 1): r for r in rows} for arm, (_, rows, _) in data.items()}
    n = int(a.seconds*10)
    for k in range(n):
        t = round(a.start+k*0.1, 1)
        frame = Image.new('RGB', (W, H), (0, 0, 0))
        for c, (arm, name, color) in enumerate(METHODS):
            run, _, job = data[arm]
            frame.paste(panel(run, idx[arm][t], name, color, job['gap'], centre), (c*(COL+2)-c*2, 0))
        ImageDraw.Draw(frame).rectangle((COL-1, 0, COL+1, H), fill=(0, 0, 0))
        p.stdin.write(frame.tobytes())
        if abs(t-a.still_t) < 0.01:
            still = frame
    p.stdin.close()
    p.wait()
    if still:
        still.save(a.out.with_suffix('.jpg'), quality=86)
    print('wrote', a.out, a.out.stat().st_size//1024, 'KB')


if __name__ == '__main__':
    main()
