"""Course-method detector (classic_detector.py) on the drone videos, compared with YOLOv8 inside the same trackers.
Folds as in analyze.py / new_video_eval.py: train testv4 -> test img7888, train img7888 -> test testv4,
train both -> test the held-out Tello video img7923. The detector works on half-resolution frames (960x540).
For the learned-Q tracker, Q is chosen by innovation log-likelihood on the TRAINING video(s), scored with the
course detector's out-of-fold detections there (as for YOLO, whose weights were trained elsewhere).
Usage: python classic_drone.py OUT_DIR [--trackers-only]"""
import json, os, sys, time, zlib
from multiprocessing import Pool
import cv2
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "drone"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import classic_detector as cd
import replay as rp
import analyze as an

cv2.setNumThreads(1)
E = "/home/stanley/Github/Unity_Ship_Formation_Study/Experiments/PR_Course/drone"
OUT = sys.argv[1]
S = 0.5                                                   # detector image scale
cd.configure(40, 11, [50 * 1.25 ** k for k in range(11)])   # drone boxes: aspect ~0.27, 100..930 px wide at 1080p
VIDS = ["testv4", "img7888", "img7923"]
FOLDS = [(["img7888"], "testv4"), (["testv4"], "img7888"), (["testv4", "img7888"], "img7923")]
Q_GRID = [0.3, 1, 3, 10, 30, 100, 300, 1000]


def extract(v):
    d = f"{OUT}/frames/{v}"; os.makedirs(d, exist_ok=True); n = 0
    for i, fr in enumerate(rp._frames(f"{E}/videos/{v}.mp4")):
        p = f"{d}/{i:05d}.jpg"
        if not os.path.exists(p):
            cv2.imwrite(p, cv2.resize(fr, None, fx=S, fy=S, interpolation=cv2.INTER_AREA), [cv2.IMWRITE_JPEG_QUALITY, 95])
        n += 1
    return n


def items(v, step=1, off=0):
    gt, _ = an.fuse_gt(f"{E}/gt_dino_{v}.json")
    return [(f"{OUT}/frames/{v}/{i:05d}.jpg", [c * S for c in gt[i]] if gt[i] else None) for i in range(off, len(gt), step)]


def pos_neg(a):
    path, gt = a
    chs = cd.channels(cv2.imread(path)); H, W = chs[0].shape; pyr = cd.pyramid(chs)
    rng = np.random.default_rng(zlib.crc32(path.encode())); P, N = [], []
    if gt is not None:
        b = cd.norm_box(gt); P.append(cd.patch(pyr, b))
        P.append(cd.patch(cd.pyramid([cv2.flip(c, 1) for c in chs]), (W - b[2], b[1], W - b[0], b[3])))
    for _ in range(12):
        bw = rng.uniform(cd.WIDTHS[0], min(cd.WIDTHS[-1], W - 1)); bh = bw * cd.TH / cd.TW
        x, y = rng.uniform(0, W - bw), rng.uniform(0, H - bh); b = (x, y, x + bw, y + bh)
        if gt is None or cd.iou(b, gt) < 0.3:
            N.append(cd.patch(pyr, b))
    return P, N


def mine(a):
    (path, gt), w, k = a
    pyr = cd.pyramid(cd.channels(cv2.imread(path)))
    c = cd.peaks(cd.score_maps(pyr, w), k)
    X = [cd.window(pyr, *b[5:8]) for b in c]
    lab = [1 if gt is not None and cd.iou(b[1:5], gt) >= 0.5 else (0 if gt is None or cd.iou(b[1:5], gt) < 0.3 else -1) for b in c]
    return X, lab


MODEL = None


def init(m):
    global MODEL
    MODEL = m


def det_frame(path):
    t0 = time.perf_counter(); d, _ = cd.detect(cv2.imread(path), MODEL)
    return [[round(c / S, 1) for c in b[:4]] + [round(b[4], 4)] for b in d], time.perf_counter() - t0


def train(vids, pool):
    fr = [f for v in vids for f in items(v)]
    PN = pool.map(pos_neg, fr, chunksize=8)
    Xp = np.array([p for P, _ in PN for p in P]); Xn = np.array([n for _, N in PN for n in N])
    f1 = cd.fisher(Xp, Xn)
    hard = pool.map(mine, [(f, f1["w"], 20) for f in fr[::2]], chunksize=8)
    Xh = np.array([x for X, L in hard for x, l in zip(X, L) if l == 0])
    f2 = cd.fisher(Xp, np.vstack([Xn, Xh]))
    cand = pool.map(mine, [(f, f2["w"], 10) for f in fr], chunksize=8)
    X2 = [x for X, L in cand for x, l in zip(X, L) if l >= 0]; y2 = [l for X, L in cand for l in L if l >= 0]
    X2 = np.vstack([np.array(X2), Xp]); y2 = np.array(y2 + [1] * len(Xp))
    return dict(fisher=f2, bayes=cd.GaussBayes(X2, y2, d=min(30, len(Xp) // 10))), dict(pos=len(Xp), neg=len(Xn), hard=len(Xh))


def true_ll(res, gt):
    return [l for (i, r, c, s), l in zip(res["det"], res["ll"]) if gt[r] is not None and rp.iou(rp.xyxy(c), gt[r]) >= 0.3]


def run_arm(a):
    v, dets, arm, L, q = a
    return rp.run(f"{E}/videos/{v}.mp4", dict(W=1920, H=1080, frames=dets), L=L, arm=arm, q_scale=q)


def trackers(pool, dets, rep):
    """Q grid on the training video(s) and the three tracker arms on the test video, all jobs in one parallel batch."""
    oof = {"testv4": dets["testv4|from_img7888"], "img7888": dets["img7888|from_testv4"]}
    gts = {v: an.fuse_gt(f"{E}/gt_dino_{v}.json")[0] for v in VIDS}
    jobs, keys = [], []
    for tr, te in FOLDS:
        for L in (1, 3):
            for q in Q_GRID:
                for v in tr:
                    jobs.append((v, oof[v], "his", L, q)); keys.append((te, L, q, v))
    ll = {}
    for k, r in zip(keys, pool.map(run_arm, jobs, chunksize=1)):
        ll.setdefault(k[:3], []).extend(true_ll(r, gts[k[3]]))
    jobs, keys = [], []
    for tr, te in FOLDS:
        tdet = dets[f"{te}|from_{'+'.join(tr)}"]
        for L in (1, 3):
            sc = {q: float(np.mean(ll[(te, L, q)])) for q in Q_GRID}; qb = max(sc, key=sc.get)
            rep["results"][f"L{L}|{te}"] = dict(Q=qb, loglik=sc)
            for name, arm, q in (("classic_only", "yolo_only", 1), ("classic_hand", "his", 1), ("classic_learnedQ", "his", qb)):
                jobs.append((te, tdet, arm, L, q)); keys.append((f"L{L}|{te}", name))
    for (k, name), r in zip(keys, pool.map(run_arm, jobs, chunksize=1)):
        rep["results"][k][name] = an.metrics(r["outs"], gts[k.split("|")[1]])["success50"]
    for k, row in rep["results"].items():
        print(f"{k}: Q x{row['Q']}  course only {row['classic_only']:.1f}%  + hand-tuned {row['classic_hand']:.1f}%  "
              f"+ learned Q {row['classic_learnedQ']:.1f}%", flush=True)


if __name__ == "__main__" and len(sys.argv) > 2 and sys.argv[2] == "--trackers-only":
    rep = {"folds": {}, "results": {}}
    rep["folds_log"] = [l for l in open(f"{OUT}/../drone.log").read().splitlines() if l.startswith("train ")]
    with Pool(14) as pool:
        trackers(pool, json.load(open(f"{OUT}/drone_dets.json")), rep)
    json.dump(rep, open(f"{OUT}/drone_report.json", "w"), indent=1)
    sys.exit(0)

if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    with Pool(3) as p:
        print("frames:", dict(zip(VIDS, p.map(extract, VIDS))), flush=True)
    pool = Pool(14); dets = {}; rep = {"folds": {}, "results": {}}
    for tr, te in FOLDS:
        T = time.time(); model, info = train(tr, pool)
        with Pool(14, initializer=init, initargs=(model,)) as p2:
            res = p2.map(det_frame, [f for f, _ in items(te)], chunksize=4)
        dets[f"{te}|from_{'+'.join(tr)}"] = [d for d, _ in res]
        gt, _ = an.fuse_gt(f"{E}/gt_dino_{te}.json")
        top = [bool(d) and d[0][4] >= rp.DET_THR and cd.iou(d[0][:4], g) >= 0.5 for (d, _), g in zip(res, gt) if g is not None]
        yo = json.load(open(f"{E}/yolo_{te}.json"))["frames"]
        ytop = []
        for f, g in zip(yo, gt):
            if g is None: continue
            ds = rp.det_filter(f, 1920, 1080, rp.DET_THR)
            ytop.append(bool(ds) and cd.iou(max(ds, key=lambda d: d[4])[:4], g) >= 0.5)
        rep["folds"][te] = dict(train=tr, **info, ms_per_frame=1000 * float(np.mean([t for _, t in res])),
                               classic_top1=100 * float(np.mean(top)), yolo_top1=100 * float(np.mean(ytop)), train_s=time.time() - T)
        print(f"train {tr} -> test {te}: {info}; detector alone, same frame: course {rep['folds'][te]['classic_top1']:.1f}% "
              f"vs YOLO {rep['folds'][te]['yolo_top1']:.1f}%  ({rep['folds'][te]['ms_per_frame']:.0f} ms/frame)", flush=True)
    json.dump(dets, open(f"{OUT}/drone_dets.json", "w"))
    trackers(pool, dets, rep)
    json.dump(rep, open(f"{OUT}/drone_report.json", "w"), indent=1)
