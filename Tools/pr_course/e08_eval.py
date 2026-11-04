"""Analysis of e08_extreme_waves (protocol: Documentation/PR_Course/eval_e08_extreme_waves_protocol.json).
Arms replayed offline, 1 control step latency: YOLO only | drone tracker hand-tuned | + learned Q (x10, from e07 only).
Video rule, fixed before any e08 result was seen: for every case, seed 6007, left follower camera.
Usage: python e08_eval.py OUTDIR"""
import glob, json, os, sys
from multiprocessing import Pool
import numpy as np
from scipy import stats
OUT = sys.argv[1]
sys.argv = [sys.argv[0], OUT]
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rollouts as ro
import usv_replay as uv
from rollouts import rp, an, cv2

RUNS = "/home/stanley/Github/Unity_Ship_Formation_Study/Experiments/KalmanStudy/robust_evaluation/e08_extreme_waves/runs"
NAMES = {"X1": "Sea 4, clear", "X2": "Sea 5, clear", "X3": "Sea 4 + dark storm", "X4": "Sea 4 + heavy rain", "X5": "Sea 3 + dark storm"}
for k in NAMES:
    uv.GROUP[k] = k


def run_seq(seq):
    q = uv.load(*seq)
    outs = {"yolo_only": rp.run(q["paths"], q["yolo"], L=1, arm="yolo_only")["outs"],
            "his": rp.run(q["paths"], q["yolo"], L=1, arm="his")["outs"],
            "learned_Q": rp.run(q["paths"], q["yolo"], L=1, arm="his", q_scale=10)["outs"]}
    sc = {}
    for a, o in outs.items():
        I = ro.ious(o, q["gt"]); m = ~np.isnan(I)
        sc[a] = float(np.mean(I[m] >= 0.5) * 100) if m.any() else float("nan")
    return q["name"], q["group"], q["gt"], q["paths"], outs, sc


if __name__ == "__main__":
    seqs = [(r, s) for r in sorted(glob.glob(RUNS + "/*")) for s in ("Left", "Right")]
    R = Pool(10).map(run_seq, seqs)
    report = {"per_sequence": {n: dict(group=g, **sc) for n, g, _, _, _, sc in R}, "cases": {}}
    print(f"{len(R)} sequences\n")
    print(f"{'Case':22s} {'n':>3s} {'YOLO':>7s} {'hand':>7s} {'learnedQ':>9s}   learnedQ>hand      learnedQ vs YOLO")
    for key in list(NAMES) + ["all"]:
        sel = [r for r in R if key == "all" or r[1] == key]
        y = np.array([r[5]["yolo_only"] for r in sel]); h = np.array([r[5]["his"] for r in sel]); q = np.array([r[5]["learned_Q"] for r in sel])
        m = ~(np.isnan(y) | np.isnan(h) | np.isnan(q)); y, h, q = y[m], h[m], q[m]
        ph = stats.wilcoxon(q, h).pvalue if len(q) >= 5 and np.any(q != h) else float("nan")
        py = stats.wilcoxon(q, y).pvalue if len(q) >= 5 and np.any(q != y) else float("nan")
        # pooled frame-level means (same definition as the earlier tables)
        def pooled(a):
            I = np.concatenate([ro.ious(r[4][a], r[2]) for r in sel]); return float(np.mean(I[~np.isnan(I)] >= 0.5) * 100)
        res = dict(name=NAMES.get(key, "All extreme cases"), n=int(len(q)), yolo=pooled("yolo_only"), hand=pooled("his"), learned_Q=pooled("learned_Q"),
                   better_than_hand=int((q > h).sum()), p_vs_hand=float(ph), better_than_yolo=int((q > y).sum()), p_vs_yolo=float(py),
                   median_gain_vs_hand=float(np.median(q - h)), median_gain_vs_yolo=float(np.median(q - y)))
        report["cases"][key] = res
        print(f"{res['name']:22s} {res['n']:3d} {res['yolo']:6.1f}% {res['hand']:6.1f}% {res['learned_Q']:8.1f}%   "
              f"{res['better_than_hand']:2d}/{res['n']} p={ph:.2g}     {res['better_than_yolo']:2d}/{res['n']} better, median {res['median_gain_vs_yolo']:+.1f} pts, p={py:.2g}", flush=True)
    for n, g, gt, paths, outs, sc in R:
        if "_6007_" in n and n.endswith("/Left"):
            fn = f"usv_e08_{g}_{NAMES[g].replace(' ', '').replace('+', '_').replace(',', '_')}_seed6007_left.mp4"
            ro.render((cv2.imread(p) for p in paths), gt, outs, f"{OUT}/{fn}", 10,
                      f"USV {NAMES[g]} (e08, seed 6007, left camera) - offline replay, YOLO 1 step late", crop=(480, 270))
            print("video:", fn, {k: round(v, 1) for k, v in sc.items()}, flush=True)
    json.dump(report, open(f"{OUT}/evidence_e08.json", "w"), indent=1, default=float)
