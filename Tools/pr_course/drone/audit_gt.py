"""Contact sheet for checking pseudo ground truth by eye: GT (green), YOLO top box (red), crop around the target.
Picks frames where GT and YOLO disagree first, then evenly spaced frames. Usage: python audit_gt.py EXPDIR VIDEO_NAME OUT.jpg [N]"""
import json, sys, os, cv2, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import replay as rp, analyze as an
E, v, out = sys.argv[1:4]; N = int(sys.argv[4]) if len(sys.argv) > 4 else 30
gt, st = an.fuse_gt(f"{E}/gt_dino_{v}.json"); y = json.load(open(f"{E}/yolo_{v}.json"))
top = []
for i, f in enumerate(y["frames"]):
    ds = rp.det_filter(f, y["W"], y["H"], rp.DET_THR); top.append(max(ds, key=lambda d: d[4]) if ds else None)
dis = [i for i in range(len(gt)) if (gt[i] is None) != (top[i] is None) or (gt[i] and top[i] and rp.iou(gt[i], top[i]) < 0.3)]
even = list(range(0, len(gt), max(1, len(gt) // (N // 2))))
pick = sorted(set(dis[:: max(1, len(dis) // (N // 2))][: N // 2] + even[: N - min(len(dis), N // 2)]))[:N]
cap = cv2.VideoCapture(f"{E}/videos/{v}.mp4"); tiles = []; i = -1
while True:
    ok, fr = cap.read()
    if not ok: break
    i += 1
    if i not in pick: continue
    ref = gt[i] or (top[i][:4] if top[i] else None)
    cx, cy = ((ref[0] + ref[2]) / 2, (ref[1] + ref[3]) / 2) if ref else (fr.shape[1] / 2, fr.shape[0] / 2)
    for b, c in ((gt[i], (0, 255, 0)), (top[i], (0, 0, 255))):
        if b: cv2.rectangle(fr, (int(b[0]), int(b[1])), (int(b[2]), int(b[3])), c, 2)
    x0 = int(min(max(cx - 240, 0), fr.shape[1] - 480)); y0 = int(min(max(cy - 160, 0), fr.shape[0] - 320))
    t = fr[y0:y0 + 320, x0:x0 + 480].copy()
    cv2.putText(t, f"{i} {st[i]} {'DIS' if i in dis else ''}", (5, 22), 0, 0.7, (0, 255, 255), 2)
    tiles.append(t)
while len(tiles) % 6: tiles.append(np.zeros_like(tiles[0]))
cv2.imwrite(out, np.vstack([np.hstack(tiles[k:k + 6]) for k in range(0, len(tiles), 6)]))
print(v, "frames", len(gt), "GT", sum(g is not None for g in gt), "YOLO", sum(t is not None for t in top), "disagree", len(dis))
