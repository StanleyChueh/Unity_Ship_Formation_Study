"""Train the course-method detector per fold (split by seed, as in usv_replay.py) and run it on every test frame.
Writes OUT/dets/<run>__<side>.json (per-frame [[x1,y1,x2,y2,conf], ...]) and OUT/train_report.json.
Usage: python classic_run.py OUT_DIR"""
import json, os, pickle, sys, time, zlib
from multiprocessing import Pool
import cv2
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import classic_detector as cd
import usv_replay as u

cv2.setNumThreads(1)
OUT = sys.argv[1]
RNG = np.random.default_rng(0)


def frames_of(seq, step, offset=0):
    q = u.load(*seq)
    return [(q["paths"][i], q["gt"][i]) for i in range(offset, len(q["paths"]), step)]


def pos_neg(args):
    path, gt = args
    img = cv2.imread(path); chs = cd.channels(img); H, W = chs[0].shape; pyr = cd.pyramid(chs)
    rng = np.random.default_rng(zlib.crc32(path.encode()))
    P, N = [], []
    if gt is not None:
        b = cd.norm_box(gt); P.append(cd.patch(pyr, b))
        P.append(cd.patch(cd.pyramid([cv2.flip(c, 1) for c in chs]), (W - b[2], b[1], W - b[0], b[3])))
    for _ in range(12):
        bw = rng.uniform(cd.WIDTHS[0], cd.WIDTHS[-1]); bh = bw * cd.TH / cd.TW
        x, y = rng.uniform(0, W - bw), rng.uniform(0, H - bh); b = (x, y, x + bw, y + bh)
        if gt is None or cd.iou(b, gt) < 0.3:
            N.append(cd.patch(pyr, b))
    return P, N


def mine(args):
    """Stage-1 peaks on a training frame: hard negatives (IoU<0.3) and labelled candidates for stage 2."""
    (path, gt), w, k = args
    pyr = cd.pyramid(cd.channels(cv2.imread(path)))
    c = cd.peaks(cd.score_maps(pyr, w), k)
    X = [cd.window(pyr, *b[5:8]) for b in c]
    lab = [1 if gt is not None and cd.iou(b[1:5], gt) >= 0.5 else (0 if gt is None or cd.iou(b[1:5], gt) < 0.3 else -1) for b in c]
    return X, lab


MODEL = None


def init(m):
    global MODEL
    MODEL = m


def run_seq(seq):
    q = u.load(*seq); out, cand_lab, t = [], [], 0.0
    for p, g in zip(q["paths"], q["gt"]):
        img = cv2.imread(p); t0 = time.perf_counter()
        d, _ = cd.detect(img, MODEL); t += time.perf_counter() - t0
        out.append([[round(v, 2) for v in b[:4]] + [round(b[4], 4)] for b in d])
        cand_lab += [(b[4], 1 if g is not None and cd.iou(b[:4], g) >= 0.5 else 0) for b in d]
    name = os.path.basename(seq[0]) + "__" + seq[1]
    json.dump(out, open(f"{OUT}/dets/{name}.json", "w"))
    return name, t / len(q["paths"]), cand_lab


def auc(scores, labels):
    s, l = np.asarray(scores), np.asarray(labels)
    order = np.argsort(s); r = np.empty(len(s)); r[order] = np.arange(1, len(s) + 1)
    n1 = l.sum(); n0 = len(l) - n1
    return float((r[l == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


if __name__ == "__main__":
    os.makedirs(f"{OUT}/dets", exist_ok=True)
    S = u.seqs(); seed_of = {r: json.load(open(f"{r}/job.json"))["seed"] for r, _ in S}
    seeds = sorted(set(seed_of.values())); rep = {}
    pool = Pool(14)
    for fold in (0, 1):
        tr = [a for a in S if seeds.index(seed_of[a[0]]) % 2 == fold]; te = [a for a in S if a not in tr]
        T = time.time()
        fr = [f for s in tr for f in frames_of(s, 6)]
        PN = pool.map(pos_neg, fr, chunksize=20)
        Xp = np.array([p for P, _ in PN for p in P]); Xn = np.array([n for _, N in PN for n in N])
        f1 = cd.fisher(Xp, Xn)
        hard = pool.map(mine, [(f, f1["w"], 20) for s in tr for f in frames_of(s, 12, 3)], chunksize=10)
        Xh = np.array([x for X, L in hard for x, l in zip(X, L) if l == 0])
        f2 = cd.fisher(Xp, np.vstack([Xn, Xh]))
        cand = pool.map(mine, [(f, f2["w"], 10) for s in tr for f in frames_of(s, 6, 1)], chunksize=10)
        X2 = [x for X, L in cand for x, l in zip(X, L) if l >= 0]; y2 = [l for X, L in cand for l in L if l >= 0]
        X2 = np.vstack([np.array(X2), Xp[::2]]); y2 = np.array(y2 + [1] * len(Xp[::2]))
        bayes = cd.GaussBayes(X2, y2)
        model = dict(fisher=f2, bayes=bayes)
        pickle.dump(model, open(f"{OUT}/model_fold{fold}.pkl", "wb"))
        print(f"fold {fold}: {len(Xp)} pos, {len(Xn)} random neg, {len(Xh)} hard neg; stage-2 {len(y2)} samples "
              f"({100 * y2.mean():.1f}% leader); train {time.time() - T:.0f}s", flush=True)
        with Pool(14, initializer=init, initargs=(model,)) as p2:
            res = p2.map(run_seq, te)
        sc = [s for _, _, cl in res for s, _ in cl]; lb = [l for _, _, cl in res for _, l in cl]
        rep[fold] = dict(train=[os.path.basename(r) + "/" + s for r, s in tr], n_pos=len(Xp), n_neg=len(Xn), n_hard=len(Xh),
                         stage2_n=int(len(y2)), stage2_leader_pct=float(100 * y2.mean()),
                         test_candidate_auc=auc(sc, lb), ms_per_frame=float(1000 * np.mean([t for _, t, _ in res])))
        print(f"fold {fold}: test candidate AUC {rep[fold]['test_candidate_auc']:.3f}, "
              f"{rep[fold]['ms_per_frame']:.0f} ms/frame (1 CPU core)", flush=True)
    json.dump(rep, open(f"{OUT}/train_report.json", "w"), indent=1)
