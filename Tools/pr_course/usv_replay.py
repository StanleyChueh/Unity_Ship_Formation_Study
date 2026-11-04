"""Run the drone teammate's tracker (and its PR refinements) on saved USV runs, scored against simulator truth.
Each follower camera of each run is one sequence: frames/{step}_{Side}Front.jpg, YOLO leader-class boxes from
steps.jsonl raw_detections, ground truth = the leader's identity box (id 1). 10 Hz, 1280x720.
His hand-tuned constants are kept exactly (they were tuned for 30 fps 1080p drone video); the learned
versions are re-fitted from USV training runs, which is the point: learned parameters transfer, hand-tuned ones may not.
Folds: split by seed (train seeds never appear in test). Usage: python usv_replay.py OUT.json"""
import glob, json, os, sys, math
from multiprocessing import Pool
import cv2
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "drone"))
import replay as rp
import analyze as an

cv2.setNumThreads(1)
ROOT = "/home/stanley/Github/Unity_Ship_Formation_Study/Experiments/KalmanStudy/robust_evaluation/e07_vision_only_on_off/runs"
GROUP = {"C8": "clear", "C10": "huge_waves", "L03": "huge_waves", "L07": "rain", "L08": "night", "L09": "night_rain", "L10": "dark_storm"}
L = 1  # detection result used one control step (100 ms) late


def load(run, side):
    job = json.load(open(f"{run}/job.json")); gt, dets, paths = [], [], []
    for line in open(f"{run}/steps.jsonl"):
        r = json.loads(line)
        shift = r["height"] - 1 - job.get("id_box_encoded_y_origin", 359)
        lead = [b for b in r[side.lower() + "_boxes"] if b["id"] == 1]
        gt.append([lead[0]["x"], lead[0]["y"] + shift, lead[0]["x"] + lead[0]["w"], lead[0]["y"] + shift + lead[0]["h"]]
                  if lead and lead[0]["w"] >= 2 and lead[0]["h"] >= 2 else None)
        dets.append([d[:5] for d in r["raw_detections"].get(side + "Front", []) if d[5] == 0])
        paths.append(f"{run}/frames/{r['step']:05d}_{side}Front.jpg")
    return dict(gt=gt, yolo=dict(W=1280, H=720, frames=dets), paths=paths, seed=job["seed"],
                group=GROUP[os.path.basename(run).split("_")[0]], name=f"{os.path.basename(run)}/{side}")


def seqs():
    return [(r, s) for r in sorted(glob.glob(ROOT + "/*")) for s in ("Left", "Right")]


Q_GRID = [1, 3, 10, 30, 100, 300]
ARMS = ["yolo_only", "his", "his+learned_Q", "his+learned_RQ", "bayes_gate+learned_RQ"]


def make_noise(params):
    if not params:
        return None
    noise = dict(params); tab = noise.pop("table_scale")
    noise["det_scale"] = lambda s: next(v for lo, hi, v in tab if lo <= s < hi)
    return noise


def job(a):
    """a = (seq, arm, kwargs); noise passed as plain params (picklable)."""
    (run, side), arm, kw = a
    q = load(run, side); kw = dict(kw)
    kw["noise"] = make_noise(kw.pop("noise_params", None))
    res = rp.run(q["paths"], q["yolo"], L=L, arm=arm, gt=q["gt"], **kw)
    ll = [l for (i, r, c, s), l in zip(res["det"], res["ll"]) if q["gt"][r] is not None and rp.iou(rp.xyxy(c), q["gt"][r]) >= 0.3]
    return dict(name=q["name"], group=q["group"], gt=q["gt"], outs=res["outs"], samples=res["samples"],
                det=res["det"], flow=res["flow"], ll=ll)


def fit_noise(T):
    merged = dict(det=[], flow=[]); gt_all = []
    for t in T:
        off = len(gt_all)
        merged["det"] += [(i + off, r + off, c, s) for i, r, c, s in t["det"]]
        merged["flow"] += [(i + off, mx, my, n) for i, mx, my, n in t["flow"]]
        gt_all += t["gt"]
    nf = an.noise_fit(merged, gt_all)
    tab = [(lo, hi, ((vx + vy) / 2) / ((nf["det_x"] + nf["det_y"]) / 2) if vx is not None else 1.0)
           for lo, hi, n, vx, vy in nf["table"]]
    params = {k: nf[k] for k in ("det_x", "det_y", "wh", "flow_x", "flow_y")}; params["table_scale"] = tab
    return params, nf


if __name__ == "__main__":
    S = seqs(); seed_of = {r: json.load(open(f"{r}/job.json"))["seed"] for r, _ in S}
    seeds = sorted(set(seed_of.values())); report = {}; fits = {}
    pool = Pool(12)
    for fold in (0, 1):
        tr = [a for a in S if seeds.index(seed_of[a[0]]) % 2 == fold]; te = [a for a in S if a not in tr]
        # 1) R by MLE from the hand-tuned tracker's measurements vs truth
        params, nf = fit_noise(pool.map(job, [(a, "his", {}) for a in tr]))
        # 2) Q by maximising the innovation log-likelihood on the training runs (for hand R and for learned R)
        best = {}
        for tag, extra in (("hand_R", {}), ("learned_R", {"noise_params": params})):
            scores = {}
            for qs in Q_GRID:
                T = pool.map(job, [(a, "his", dict(extra, q_scale=qs)) for a in tr])
                scores[qs] = float(np.mean([l for t in T for l in t["ll"]]))
            best[tag] = max(scores, key=scores.get)
            print(f"fold {fold} {tag}: mean innovation log-lik per Q scale {scores} -> {best[tag]}", flush=True)
        # 3) Bayes gate trained on candidates seen by the learned-R/Q tracker
        T = pool.map(job, [(a, "his", {"noise_params": params, "q_scale": best["learned_R"], "collect": True}) for a in tr])
        X = np.array([x for t in T for x, _ in t["samples"]]); y = np.array([l for t in T for _, l in t["samples"]])
        gate = rp.BayesGate(X, y, lam_ratio=3.0)
        fits[fold] = dict(R={k: v for k, v in params.items()}, R_table=nf["table"], bias_y=nf["bias_y"], Q=best,
                          gate_samples=int(len(y)), gate_target_pct=float(100 * y.mean()))
        print(f"fold {fold}: learned R {dict((k, round(v, 5)) for k, v in params.items() if k != 'table_scale')}, Q {best}, "
              f"gate samples {len(y)} ({100 * y.mean():.1f}% target)", flush=True)
        cfg = {"yolo_only": ("yolo_only", {}), "his": ("his", {}),
               "his+learned_Q": ("his", {"q_scale": best["hand_R"]}),
               "his+learned_RQ": ("his", {"noise_params": params, "q_scale": best["learned_R"]}),
               "bayes_gate+learned_RQ": ("bayes_gate", {"noise_params": params, "q_scale": best["learned_R"], "gate": gate})}
        for name in ARMS:
            arm, kw = cfg[name]
            for t in pool.map(job, [(a, arm, kw) for a in te]):
                report.setdefault(t["group"], {}).setdefault(name, []).append((t["gt"], t["outs"]))
    summary = {"fits": fits}
    for group in sorted(report):
        print(f"\n=== {group}: {len(report[group]['his'])} test sequences")
        for name in ARMS:
            o2, g2 = [], []
            for gg, oo in report[group][name]:
                o2 += oo + [None]; g2 += gg + [None]
            vy = [None] + [abs((g2[i][1] + g2[i][3]) / 2 - (g2[i - 1][1] + g2[i - 1][3]) / 2) if g2[i] and g2[i - 1] else None
                           for i in range(1, len(g2))]
            thr = np.percentile([v for v in vy if v is not None], 80); fast = [v is not None and v >= thr for v in vy]
            m = an.metrics(o2, g2); fm = an.metrics(o2, g2, fast)
            summary[f"{group}|{name}"] = dict(all=m, fast=fm, fast_thr=float(thr))
            print(f"  {name:22s} IoU>=.5 {m['success50']:5.1f}%  mIoU {m['mean_iou']:.3f}  ctr-err {m['center_err']:.3f}  "
                  f"wrong {m['wrong_lock']:4.1f}%  jitter {m['jitter_px']:5.2f}px | fast(>={thr:.0f}px/step): "
                  f"IoU>=.5 {fm['success50']:5.1f}%  mIoU {fm['mean_iou']:.3f}", flush=True)
    json.dump(summary, open(sys.argv[1], "w"), indent=1, default=float)
