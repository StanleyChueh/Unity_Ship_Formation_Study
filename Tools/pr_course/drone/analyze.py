"""Drone analysis for the PR course project. Usage: python analyze.py EXPDIR
EXPDIR has videos/{testv4,img7888}.mp4, yolo_*.json (yolo_dump.py), gt_dino_*.json (gt_dino.py).
Train/test is cross-video: models fitted on one video are tested on the other (2 folds)."""
import json, math, sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import replay as rp

E = sys.argv[1] if len(sys.argv) > 1 else "."
VIDS = ["testv4", "img7888"]


def fuse_gt(path):
    """Teammate's autolabel_v2 fusion: seed = best box, weighted mean of opinions with IoU>=0.5,
    accept if >=2 of 4 opinions and fused conf >= 0.30; rescue weak frames consistent with accepted neighbours."""
    d = json.load(open(path)); items = []
    for ops in d["frames"]:
        cands = [b for r in ops for b in r]
        if not cands:
            items.append(None); continue
        seed = max(cands, key=lambda b: b[4])
        picks = []
        for r in ops:
            m = [b for b in r if rp.iou(b, seed) >= 0.5]
            if m: picks.append(max(m, key=lambda b: b[4]))
        w = np.array([b[4] for b in picks]); B = np.array([b[:4] for b in picks])
        items.append(((B * w[:, None]).sum(0) / w.sum()).tolist() + [float(w.sum() / len(ops)), len(picks)])
    st = ["ok" if f and f[5] >= 2 and f[4] >= 0.30 else ("weak" if f else "none") for f in items]
    for n, f in enumerate(items):
        if st[n] == "weak":
            for j in range(max(0, n - 3), min(len(items), n + 4)):
                if j != n and st[j] == "ok":
                    b2 = items[j]; w, h = f[2] - f[0], f[3] - f[1]; w2, h2 = b2[2] - b2[0], b2[3] - b2[1]
                    dd = math.hypot((f[0] + f[2] - b2[0] - b2[2]) / 2, (f[1] + f[3] - b2[1] - b2[3]) / 2)
                    if dd < 1.5 * max(w, h, w2, h2) and 0.5 <= (w * h) / max(w2 * h2, 1) <= 2:
                        st[n] = "rescued"; break
    return [f[:4] if s in ("ok", "rescued") else None for f, s in zip(items, st)], st


def metrics(outs, gt, mask=None):
    idx = [i for i, g in enumerate(gt) if g is not None and (mask is None or mask[i])]
    cov = [outs[i] is not None for i in idx]
    ious = [rp.iou(rp.xyxy(outs[i]), gt[i]) if outs[i] is not None else 0.0 for i in idx]
    cerr = [math.hypot(outs[i][0] - (gt[i][0] + gt[i][2]) / 2, outs[i][1] - (gt[i][1] + gt[i][3]) / 2) /
            math.hypot(gt[i][2] - gt[i][0], gt[i][3] - gt[i][1]) for i in idx if outs[i] is not None]
    wrong = [e > 1.0 for e in cerr]
    jit = [math.hypot(outs[i + 1][0] - 2 * outs[i][0] + outs[i - 1][0], outs[i + 1][1] - 2 * outs[i][1] + outs[i - 1][1])
           for i in idx if 0 < i < len(outs) - 1 and None not in (outs[i - 1], outs[i], outs[i + 1])]
    return dict(n=len(idx), coverage=100 * np.mean(cov), success50=100 * np.mean(np.array(ious) >= 0.5),
                mean_iou=float(np.mean(ious)), center_err=float(np.median(cerr)) if cerr else float("nan"),
                wrong_lock=100 * float(np.mean(wrong)) if wrong else 0.0, jitter_px=float(np.mean(jit)) if jit else float("nan"))


def noise_fit(res, gt):
    """MLE (zero-mean Gaussian -> mean of squares) of normalised measurement errors, per axis."""
    ex, ey, ew, conf = [], [], [], []
    for idx, ridx, c, s in res["det"]:
        g = gt[ridx]
        if g is None: continue
        size = max(g[2] - g[0], g[3] - g[1])
        ex.append((c[0] - (g[0] + g[2]) / 2) / size); ey.append((c[1] - (g[1] + g[3]) / 2) / size)
        ew.append((c[2] - (g[2] - g[0])) / size); conf.append(s)
    fx, fy = [], []
    for idx, mx, my, n in res["flow"]:
        g = gt[idx]
        if g is None: continue
        size = max(g[2] - g[0], g[3] - g[1])
        fx.append((mx - (g[0] + g[2]) / 2) / size); fy.append((my - (g[1] + g[3]) / 2) / size)
    ex, ey, conf = map(np.array, (ex, ey, conf))
    ok = (np.abs(ex) < 1) & (np.abs(ey) < 1)  # drop wrong-target associations from the noise fit
    bins = [0.0, 0.4, 0.6, 0.8, 1.01]; base = float(np.mean(ex[ok] ** 2 + ey[ok] ** 2) / 2); table = []
    for lo, hi in zip(bins, bins[1:]):
        m = ok & (conf >= lo) & (conf < hi)
        table.append((lo, hi, int(m.sum()), float(np.mean(ex[m] ** 2)) if m.sum() > 10 else None,
                      float(np.mean(ey[m] ** 2)) if m.sum() > 10 else None))
    scale = {(lo, hi): ((vx + vy) / 2 / base if vx is not None else 1.0) for lo, hi, n, vx, vy in table}
    fx, fy = np.array(fx), np.array(fy); okf = (np.abs(fx) < 1) & (np.abs(fy) < 1)
    return dict(det_x=float(np.mean(ex[ok] ** 2)), det_y=float(np.mean(ey[ok] ** 2)), wh=float(np.mean(np.array(ew)[ok] ** 2)),
                flow_x=float(np.mean(fx[okf] ** 2)), flow_y=float(np.mean(fy[okf] ** 2)),
                det_scale=lambda s: next(v for (lo, hi), v in scale.items() if lo <= s < hi), table=table,
                bias_y=float(np.mean(ey[ok])), n_det=int(ok.sum()), n_flow=int(okf.sum()))


def motion_table(yolo, gt):
    """YOLO (top box >= 0.22) miss / wrong rate vs the drone's vertical image speed (GT, px per frame at 1080p)."""
    rows = []
    for i in range(1, len(gt)):
        if gt[i] is None or gt[i - 1] is None: continue
        vy = abs((gt[i][1] + gt[i][3]) / 2 - (gt[i - 1][1] + gt[i - 1][3]) / 2)
        ds = rp.det_filter(yolo["frames"][i], yolo["W"], yolo["H"], rp.DET_THR)
        top = max(ds, key=lambda d: d[4]) if ds else None
        rows.append((vy, top is None, top is not None and rp.iou(top[:4], gt[i]) < 0.3))
    return np.array(rows, float)


if __name__ == "__main__":
    data = {}
    for v in VIDS:
        gt, st = fuse_gt(f"{E}/gt_dino_{v}.json")
        y = json.load(open(f"{E}/yolo_{v}.json"))
        data[v] = dict(gt=gt, st=st, yolo=y, video=f"{E}/videos/{v}.mp4")
        print(f"{v}: frames {len(gt)}  GT accepted {sum(g is not None for g in gt)}  "
              f"(ok {st.count('ok')}, rescued {st.count('rescued')})")
    report = {"motion": {}, "noise": {}, "results": {}}
    # 1) detection errors vs vertical speed (both videos pooled)
    M = np.vstack([motion_table(data[v]["yolo"], data[v]["gt"]) for v in VIDS])
    print("\nYOLO alone vs vertical speed of the drone in the image (px/frame, 1080p)")
    for lo, hi in [(0, 2), (2, 5), (5, 10), (10, 20), (20, 1e9)]:
        m = (M[:, 0] >= lo) & (M[:, 0] < hi)
        if m.sum():
            r = dict(n=int(m.sum()), miss=100 * M[m, 1].mean(), wrong=100 * M[m, 2].mean())
            report["motion"][f"{lo}-{hi}"] = r
            print(f"  {lo:>4}-{hi:<6}: missed {r['miss']:5.1f}%  wrong box {r['wrong']:5.1f}%  n={r['n']}")
    # 2) cross-video training of the PR components (R by MLE, Q by innovation likelihood, Bayes gate), then all arms
    ARMS = ["yolo_only", "his", "his+learned_Q", "his+learned_RQ", "bayes_gate+learned_RQ"]
    for L in (1, 3):
        for test in VIDS:
            train = [v for v in VIDS if v != test][0]; D = data[train]; gtr = D["gt"]
            def true_ll(res):
                return [l for (i, r, c, s), l in zip(res["det"], res["ll"]) if gtr[r] is not None and rp.iou(rp.xyxy(c), gtr[r]) >= 0.3]
            tr = rp.run(D["video"], D["yolo"], L=L, arm="his", gt=gtr)
            noise = noise_fit(tr, gtr); best = {}
            for tag, extra in (("hand_R", {}), ("learned_R", {"noise": noise})):
                sc = {q: float(np.mean(true_ll(rp.run(D["video"], D["yolo"], L=L, arm="his", q_scale=q, **extra))))
                      for q in [0.3, 1, 3, 10, 30, 100]}
                best[tag] = max(sc, key=sc.get)
                print(f"  L={L} train {train} {tag}: innovation log-lik per Q scale", {k: round(v, 2) for k, v in sc.items()}, "->", best[tag])
            tr2 = rp.run(D["video"], D["yolo"], L=L, arm="his", gt=gtr, collect=True, noise=noise, q_scale=best["learned_R"])
            X = np.array([x for x, _ in tr2["samples"]]); yv = np.array([l for _, l in tr2["samples"]])
            gate = rp.BayesGate(X, yv, lam_ratio=3.0)
            report["noise"][f"L{L}_train_{train}"] = dict({k: v for k, v in noise.items() if k != "det_scale"}, Q=best)
            gt = data[test]["gt"]
            vy = [None] + [abs((gt[i][1] + gt[i][3]) / 2 - (gt[i - 1][1] + gt[i - 1][3]) / 2)
                           if gt[i] is not None and gt[i - 1] is not None else None for i in range(1, len(gt))]
            fast_thr = np.percentile([v for v in vy if v is not None], 80)
            fast = [v is not None and v >= fast_thr for v in vy]
            print(f"\n=== L={L} frame(s) latency, train {train} -> test {test}  (learned R det_x {noise['det_x']:.4f} det_y {noise['det_y']:.4f} "
                  f"flow_x {noise['flow_x']:.4f} flow_y {noise['flow_y']:.4f}; Q {best}; gate samples {len(yv)}, target {yv.mean() * 100:.1f}%; "
                  f"fast = top 20% vertical speed >= {fast_thr:.1f} px/frame)")
            cfg = {"yolo_only": ("yolo_only", {}), "his": ("his", {}), "his+learned_Q": ("his", dict(q_scale=best["hand_R"])),
                   "his+learned_RQ": ("his", dict(noise=noise, q_scale=best["learned_R"])),
                   "bayes_gate+learned_RQ": ("bayes_gate", dict(noise=noise, q_scale=best["learned_R"], gate=gate))}
            for arm in ARMS:
                a, kw = cfg[arm]
                res = rp.run(data[test]["video"], data[test]["yolo"], L=L, arm=a, **kw)
                allm = metrics(res["outs"], gt); fm = metrics(res["outs"], gt, fast)
                report["results"][f"L{L}|{test}|{arm}"] = dict(all=allm, fast=fm)
                print(f"  {arm:22s} cover {allm['coverage']:5.1f}%  IoU>=.5 {allm['success50']:5.1f}%  "
                      f"mIoU {allm['mean_iou']:.3f}  ctr-err {allm['center_err']:.3f}  wrong {allm['wrong_lock']:4.1f}%  "
                      f"jitter {allm['jitter_px']:5.2f}px | fast: IoU>=.5 {fm['success50']:5.1f}%  mIoU {fm['mean_iou']:.3f}", flush=True)
    json.dump(report, open(f"{E}/drone_report.json", "w"), indent=1, default=float)
