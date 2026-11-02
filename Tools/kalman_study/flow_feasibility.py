#!/usr/bin/env python3
"""Offline check: can optical flow measure what the vision-only tracker is weak at?

Uses saved runs (the exact JPEGs the detector received) and needs no simulator. True positions and
identity boxes are for scoring only. Two questions:

1. Range rate. Compare d(ln r)/dt from box size against scale change between tracked features
   (MedianFlow-style: ratio of pairwise feature distances), both over the same time window, scored
   against the true boat separation.
2. Dropouts. From the last box before a scheduled dropout, carry the box with flow through the gap
   (the images still exist, only the detector output is withheld) and score offset and size against
   the true leader box, next to the tracker's own coasted estimate.

Feature finding and the forward-backward check follow flow_shift in the drone tracker
(tracking_optical_flow.py); the window is smaller because the boat is only tens of pixels wide.
"""
import argparse
import json
import math
from pathlib import Path
import cv2
import numpy as np
from make_rollout_videos import load

EV = Path(__file__).resolve().parents[2]/'Experiments/KalmanStudy/robust_evaluation'
LK = dict(winSize=(15, 15), maxLevel=3, criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01))
DT = 0.1


def gray(run, row, side):
    im = cv2.imread(str(run/'frames'/f'{row["step"]:05d}_{side}Front.jpg'), cv2.IMREAD_GRAYSCALE)
    return im


def track(g0, g1, box, min_points=6):
    """box = (x0, y0, x1, y1). Returns (median dx, median dy, scale, n good points) or None."""
    x0, y0, x1, y1 = [int(round(v)) for v in box]
    x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, g0.shape[1]), min(y1, g0.shape[0])
    if x1-x0 < 6 or y1-y0 < 4:
        return None
    p0 = cv2.goodFeaturesToTrack(g0[y0:y1, x0:x1], 40, 0.01, 2)
    if p0 is None or len(p0) < min_points:
        return None
    p0 = p0+np.array([[[x0, y0]]], np.float32)
    p1, st1, _ = cv2.calcOpticalFlowPyrLK(g0, g1, p0, None, **LK)
    back, st2, _ = cv2.calcOpticalFlowPyrLK(g1, g0, p1, None, **LK)
    fb = np.linalg.norm((p0-back).reshape(-1, 2), axis=1)
    good = (st1.ravel() == 1) & (st2.ravel() == 1) & (fb < 1.0)
    if good.sum() < min_points:
        return None
    a, b = p0.reshape(-1, 2)[good], p1.reshape(-1, 2)[good]
    d = b-a
    i, j = np.triu_indices(len(a), 1)
    d0, d1 = np.linalg.norm(a[i]-a[j], axis=1), np.linalg.norm(b[i]-b[j], axis=1)
    keep = d0 > 3.0
    if keep.sum() < 3:
        return None
    return float(np.median(d[:, 0])), float(np.median(d[:, 1])), float(np.median(d1[keep]/d0[keep])), int(good.sum())


def truth_range(row, idx):
    L, F = row['boats'][0], row['boats'][idx]
    return math.hypot(L['x']-F['x'], L['z']-F['z'])


def true_box(row, side):
    for b in row['left_boxes' if side == 'Left' else 'right_boxes']:
        if b['id'] == 1:
            return b
    return None


def rate_test(run, side, idx, windows):
    rows = [r for r in load(run) if r['t'] >= 15]
    key = side+'Front'
    n = len(rows)
    rt = np.array([truth_range(r, idx) for r in rows])
    area = np.full(n, np.nan)
    width = []
    for k, r in enumerate(rows):
        bb = (r['selected'].get(key) or {}).get('bbox')
        if bb:
            area[k] = (bb[2]-bb[0])*(bb[3]-bb[1])
            width.append(bb[2]-bb[0])
    # Per-step ln(scale) from flow, tracked between consecutive frames from the current YOLO box.
    lns = np.full(n, np.nan)
    pts = []
    prev = gray(run, rows[0], side)
    for k in range(1, n):
        cur = gray(run, rows[k], side)
        bb = (rows[k-1]['selected'].get(key) or {}).get('bbox')
        if bb and prev is not None and cur is not None:
            out = track(prev, cur, bb)
            if out:
                lns[k] = math.log(out[2])
                pts.append(out[3])
        prev = cur
    res = dict(box_width_px=float(np.median(width)) if width else None, median_points=float(np.median(pts)) if pts else 0,
               flow_coverage_pct=float(100*np.mean(np.isfinite(lns[1:]))), windows={})
    for w in windows:
        N = int(round(w/DT))
        tr, bo, fl = [], [], []
        for k in range(N, n):
            seg = lns[k-N+1:k+1]
            if not (np.isfinite(area[k]) and np.isfinite(area[k-N])) or np.mean(np.isfinite(seg)) < 0.8:
                continue
            tr.append(math.log(rt[k]/rt[k-N])/w)
            bo.append(-0.5*math.log(area[k]/area[k-N])/w)
            fl.append(-np.nansum(seg)/(np.isfinite(seg).sum()*DT))
        if len(tr) < 20:
            res['windows'][str(w)] = dict(samples=len(tr))
            continue
        tr, bo, fl = np.array(tr), np.array(bo), np.array(fl)
        r_ref = float(np.median(rt))
        res['windows'][str(w)] = dict(samples=len(tr), true_std_mps=float(tr.std()*r_ref),
                                      box_rms_mps=float(np.sqrt(np.mean((bo-tr)**2))*r_ref), flow_rms_mps=float(np.sqrt(np.mean((fl-tr)**2))*r_ref),
                                      box_corr=float(np.corrcoef(bo, tr)[0, 1]), flow_corr=float(np.corrcoef(fl, tr)[0, 1]))
    return res


def dropout_test(run, side):
    rows = load(run)
    key = side+'Front'
    W = 1280.0
    out = []
    k = 1
    while k < len(rows):
        r = rows[k]
        if r['t'] >= 15 and not (r['selected'].get(key) or {}).get('bbox') and (rows[k-1]['selected'].get(key) or {}).get('bbox'):
            bb = list(rows[k-1]['selected'][key]['bbox'])
            start = k
            box = np.array(bb, float)
            prev = gray(run, rows[k-1], side)
            flow_e, kf_e, area_e, lost = [], [], [], 0
            ok = True
            while k < len(rows) and not (rows[k]['selected'].get(key) or {}).get('bbox'):
                cur = gray(run, rows[k], side)
                res = track(prev, cur, box) if ok else None
                if res:
                    cx, cy = (box[0]+box[2])/2+res[0], (box[1]+box[3])/2+res[1]
                    hw, hh = (box[2]-box[0])/2*res[2], (box[3]-box[1])/2*res[2]
                    box = np.array([cx-hw, cy-hh, cx+hw, cy+hh])
                else:
                    ok = False
                    lost += 1
                tb = true_box(rows[k], side)
                st = rows[k]['status'][side]
                if tb:
                    true_off = (tb['x']+tb['w']/2)/W*2-1
                    if ok:
                        flow_e.append(abs(((box[0]+box[2])/2)/W*2-1-true_off))
                        area_e.append(abs(0.5*math.log(max((box[2]-box[0])*(box[3]-box[1]), 1.0)/max(tb['w']*tb['h'], 1.0))))
                    if st.get('predicted_offset') is not None and st.get('target_detected'):
                        kf_e.append(abs(st['predicted_offset']-true_off))
                prev = cur
                k += 1
            out.append(dict(t=rows[start]['t'], frames=k-start, survived=ok, flow_offset_err=float(np.mean(flow_e)) if flow_e else None,
                            flow_end_offset_err=float(flow_e[-1]) if flow_e else None, flow_log_size_err=float(np.mean(area_e)) if area_e else None,
                            tracker_offset_err=float(np.mean(kf_e)) if kf_e else None))
        k += 1
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', type=Path)
    a = ap.parse_args()
    runs = [('Clear, speed changes', 'e06_vision_only', 'C8_clear_speed_s_dropout_4903_on_pv'),
            ('Huge waves, speed changes', 'e06_vision_only', 'C10_huge_waves_s_dropout_5021_on_pv'),
            ('Night, speed changes', 'e06_vision_only', 'W3_night_rough_s_4903_on_pv'),
            ('Heavy rain lap', 'e05_weather_v2', 'L07_lap_heavy_rain1.0_4903_on_rs'),
            ('Dark storm lap', 'e05_weather_v2', 'L10_lap_dark_storm_4903_on_rs')]
    report = {}
    for label, batch, name in runs:
        run = EV/batch/'runs'/name
        entry = {}
        for side, idx in [('Left', 1), ('Right', 2)]:
            entry[side] = dict(rate=rate_test(run, side, idx, [0.5, 1.0, 2.0]), dropouts=dropout_test(run, side))
        report[label] = entry
        print('\n'+label, name)
        for side in entry:
            r = entry[side]['rate']
            print(f"  {side}: box width {r['box_width_px']} px, {r['median_points']:.0f} flow points, flow available {r['flow_coverage_pct']:.0f}% of frames")
            for w, s in r['windows'].items():
                if 'box_rms_mps' in s:
                    print(f"    window {w} s (n={s['samples']}): true spread {s['true_std_mps']:.2f} m/s | range-rate RMS error box {s['box_rms_mps']:.2f}, flow {s['flow_rms_mps']:.2f} m/s | corr box {s['box_corr']:.2f}, flow {s['flow_corr']:.2f}")
                else:
                    print(f"    window {w} s: too few samples ({s['samples']})")
            d = entry[side]['dropouts']
            if d:
                f = [x['flow_offset_err'] for x in d if x['flow_offset_err'] is not None]
                e = [x['flow_end_offset_err'] for x in d if x['flow_end_offset_err'] is not None]
                k = [x['tracker_offset_err'] for x in d if x['tracker_offset_err'] is not None]
                z = [x['flow_log_size_err'] for x in d if x['flow_log_size_err'] is not None]
                print(f"    dropouts {len(d)}: flow survived whole gap {sum(x['survived'] for x in d)}/{len(d)}; offset error flow {np.mean(f) if f else float('nan'):.3f} (at end {np.mean(e) if e else float('nan'):.3f}), tracker coast {np.mean(k) if k else float('nan'):.3f}; flow log-size error {np.mean(z) if z else float('nan'):.3f}")
    if a.out:
        a.out.write_text(json.dumps(report, indent=1)+'\n')


if __name__ == '__main__':
    main()
