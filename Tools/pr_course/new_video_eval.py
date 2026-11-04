"""Held-out test on a NEW drone video. Every learned quantity is fitted only on the training videos (testv4 + img7888);
the new video is used once, for scoring.
Usage: python new_video_eval.py NEW_NAME OUTDIR      (needs EXP/videos/NEW.mp4, yolo_NEW.json, gt_dino_NEW.json)"""
import json, os, sys
import numpy as np
NEW, OUTDIR = sys.argv[1], sys.argv[2]
sys.argv = [sys.argv[0], OUTDIR]  # rollouts.py reads its output folder from argv
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rollouts as ro
from rollouts import rp, an, E

TRAIN = ["testv4", "img7888"]
Q_GRID = [1, 3, 10, 30, 100, 300, 1000]


def load(v):
    gt, _ = an.fuse_gt(f"{E}/gt_dino_{v}.json")
    return dict(gt=gt, yolo=json.load(open(f"{E}/yolo_{v}.json")), video=f"{E}/videos/{v}.mp4")


def true_ll(res, gt):
    return [l for (i, r, c, s), l in zip(res["det"], res["ll"]) if gt[r] is not None and rp.iou(rp.xyxy(c), gt[r]) >= 0.3]


if __name__ == "__main__":
    tr = {v: load(v) for v in TRAIN}; te = load(NEW); report = {"new_video": NEW, "train_videos": TRAIN}
    print(f"{NEW}: {len(te['gt'])} frames, ground truth on {sum(g is not None for g in te['gt'])}, "
          f"YOLO box (>=0.22) on {sum(any(d[4] >= 0.22 for d in f) for f in te['yolo']['frames'])}")
    for L in (1, 3):
        # 1) Q by maximum innovation likelihood, pooled over BOTH training videos (hand-tuned R, as in the drone code)
        sc = {}
        for q in Q_GRID:
            lls = []
            for v, d in tr.items():
                lls += true_ll(rp.run(d["video"], d["yolo"], L=L, arm="his", q_scale=q), d["gt"])
            sc[q] = float(np.mean(lls))
        q_best = max(sc, key=sc.get)
        print(f"\nL={L}: training innovation log-likelihood per Q", {k: round(v, 2) for k, v in sc.items()}, "-> Q x", q_best, flush=True)
        # 2) learned R and Bayes gate, also from training videos only (for the extra rows)
        X = []; Y = []; merged = dict(det=[], flow=[]); gt_all = []
        for v, d in tr.items():  # pool both training videos into one MLE fit
            r0 = rp.run(d["video"], d["yolo"], L=L, arm="his", gt=d["gt"]); off = len(gt_all)
            merged["det"] += [(i + off, r + off, c, s) for i, r, c, s in r0["det"]]
            merged["flow"] += [(i + off, mx, my, n) for i, mx, my, n in r0["flow"]]
            gt_all += d["gt"]
        noise = an.noise_fit(merged, gt_all)
        for v, d in tr.items():
            r1 = rp.run(d["video"], d["yolo"], L=L, arm="his", gt=d["gt"], collect=True, noise=noise, q_scale=q_best)
            X += [x for x, _ in r1["samples"]]; Y += [l for _, l in r1["samples"]]
        gate = rp.BayesGate(np.array(X), np.array(Y), lam_ratio=3.0)
        # 3) test once on the new video
        outs = {"yolo_only": rp.run(te["video"], te["yolo"], L=L, arm="yolo_only")["outs"],
                "his": rp.run(te["video"], te["yolo"], L=L, arm="his")["outs"],
                "learned_Q": rp.run(te["video"], te["yolo"], L=L, arm="his", q_scale=q_best)["outs"],
                "learned_RQ": rp.run(te["video"], te["yolo"], L=L, arm="his", noise=noise, q_scale=q_best)["outs"],
                "bayes_gate_RQ": rp.run(te["video"], te["yolo"], L=L, arm="bayes_gate", noise=noise, q_scale=q_best, gate=gate)["outs"]}
        gt = te["gt"]
        vy = [None] + [abs((gt[i][1] + gt[i][3]) / 2 - (gt[i - 1][1] + gt[i - 1][3]) / 2) if gt[i] and gt[i - 1] else None for i in range(1, len(gt))]
        thr = np.percentile([v for v in vy if v is not None], 80); fast = [v is not None and v >= thr for v in vy]
        rows = {}
        for a, o in outs.items():
            m = an.metrics(o, gt); f = an.metrics(o, gt, fast)
            rows[a] = dict(all=m, fast=f)
            print(f"  {a:14s} IoU>=.5 {m['success50']:5.1f}%  mIoU {m['mean_iou']:.3f}  wrong {m['wrong_lock']:4.1f}%  jitter {m['jitter_px']:5.1f}px | "
                  f"fast (>= {thr:.0f}px/frame): IoU>=.5 {f['success50']:5.1f}%", flush=True)
        I = {a: ro.ious(outs[a], gt) for a in outs}; ok = {}
        for a in I:
            ok[a] = (I[a] >= 0.5).astype(float); ok[a][np.isnan(I[a])] = np.nan
        boot = {}
        for base in ("his", "yolo_only"):
            d, lo, hi, w, l, k = ro.block_bootstrap(ok["learned_Q"], ok[base], 30)
            boot[base] = dict(diff=100 * d, ci=[100 * lo, 100 * hi], better=w, worse=l, blocks=k)
            print(f"  learned Q - {base:9s}: {100 * d:+.1f} points, 95% CI [{100 * lo:+.1f}, {100 * hi:+.1f}], 1-s blocks better/worse {w}/{l} of {k}")
        report[f"L{L}"] = dict(q_scores=sc, q_best=q_best, results=rows, bootstrap=boot)
        name = f"drone_{NEW}_delay{L}.mp4"
        ro.render(ro.drone_frames(NEW), gt, {a: outs[a] for a in ("yolo_only", "his", "learned_Q")}, f"{OUTDIR}/{name}", 30,
                  f"NEW drone video {NEW} (held out) - offline replay, YOLO result {L} frame(s) late")
        print("  video:", name, flush=True)
    json.dump(report, open(f"{OUTDIR}/evidence_{NEW}.json", "w"), indent=1, default=float)
