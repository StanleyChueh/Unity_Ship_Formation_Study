"""YOLOv8 vs the course-method detector (classic_run.py), each alone and inside the same trackers, on the 64 USV sequences.
Both detectors are scored on the same test folds (split by seed). For each detector, Q is chosen by the innovation
log-likelihood on that detector's training-fold sequences (Ch.3-1), exactly as usv_replay.py does for YOLO.
Usage: python classic_eval.py CLASSIC_DIR"""
import json, os, sys
from multiprocessing import Pool
import cv2
import numpy as np
from scipy import stats
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "drone"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import replay as rp
import analyze as an
import usv_replay as u

cv2.setNumThreads(1)
CD = sys.argv[1]
GROUPS = ["clear", "rain", "night", "night_rain", "dark_storm", "huge_waves"]
ARMS = [("yolo", "only"), ("yolo", "hand"), ("yolo", "learnedQ"), ("classic", "only"), ("classic", "hand"), ("classic", "learnedQ")]


def load(seq, src):
    q = u.load(*seq)
    if src == "classic":
        q["yolo"]["frames"] = json.load(open(f"{CD}/dets/{os.path.basename(seq[0])}__{seq[1]}.json"))
    return q


def job(a):
    seq, src, arm, qs = a
    q = load(seq, src)
    res = rp.run(q["paths"], q["yolo"], L=1, arm="yolo_only" if arm == "only" else "his", gt=q["gt"], q_scale=qs)
    ll = [l for (i, r, c, s), l in zip(res["det"], res["ll"]) if q["gt"][r] is not None and rp.iou(rp.xyxy(c), q["gt"][r]) >= 0.3]
    # detector quality without tracking or delay: best-confidence box in the same frame
    top = []
    for f, g in zip(q["yolo"]["frames"], q["gt"]):
        if g is None:
            continue
        ds = rp.det_filter(f, 1280, 720, rp.DET_THR)
        top.append(rp.iou(max(ds, key=lambda d: d[4])[:4], g) >= 0.5 if ds else False)
    return dict(name=q["name"], group=q["group"], gt=q["gt"], outs=res["outs"], ll=ll, top1=float(np.mean(top)))


def succ(outs, gt):
    i = [rp.iou(rp.xyxy(o), g) >= 0.5 if o is not None else False for o, g in zip(outs, gt) if g is not None]
    return float(np.mean(i)), len(i)


if __name__ == "__main__":
    S = u.seqs(); seed_of = {r: json.load(open(f"{r}/job.json"))["seed"] for r, _ in S}
    seeds = sorted(set(seed_of.values()))
    pool = Pool(14); per = {}; fits = {}
    for fold in (0, 1):
        tr = [a for a in S if seeds.index(seed_of[a[0]]) % 2 == fold]; te = [a for a in S if a not in tr]
        for src in ("yolo", "classic"):
            sc = {}
            for qs in u.Q_GRID:
                T = pool.map(job, [(a, src, "hand", qs) for a in tr])
                sc[qs] = float(np.mean([l for t in T for l in t["ll"]]))
            best = max(sc, key=sc.get); fits[f"fold{fold}|{src}"] = dict(loglik=sc, Q=best)
            print(f"fold {fold} {src}: innovation log-lik {sc} -> Q x{best}", flush=True)
            for arm, qs in (("only", 1), ("hand", 1), ("learnedQ", best)):
                for t in pool.map(job, [(a, src, arm, qs) for a in te]):
                    s, n = succ(t["outs"], t["gt"])
                    per.setdefault(t["name"], dict(group=t["group"]))[f"{src}|{arm}"] = dict(s=s, n=n)
                    per[t["name"]][f"{src}|top1_nodelay"] = t["top1"]
    out = dict(fits=fits, per_seq=per, groups={})
    keys = [f"{s}|{a}" for s, a in ARMS]
    print("\nIoU>=0.5 share of frames (pooled), one-step detection delay:")
    print(f"{'condition':12s}" + "".join(f"{k:>18s}" for k in keys))
    for g in GROUPS + ["all"]:
        seqs = [v for v in per.values() if g in ("all", v["group"])]
        row = {k: 100 * sum(v[k]["s"] * v[k]["n"] for v in seqs) / sum(v[k]["n"] for v in seqs) for k in keys}
        for src in ("yolo", "classic"):
            row[f"{src}|top1_nodelay"] = 100 * float(np.mean([v[f"{src}|top1_nodelay"] for v in seqs]))
        a = np.array([v["classic|learnedQ"]["s"] for v in seqs])
        for ref in ("yolo|only", "yolo|learnedQ"):
            b = np.array([v[ref]["s"] for v in seqs])
            p = stats.wilcoxon(a, b).pvalue if np.any(a != b) else 1.0
            row[f"classic_learnedQ_vs_{ref}"] = dict(wins=int((a > b).sum()), n=len(a), p=float(p))
        out["groups"][g] = row
        print(f"{g:12s}" + "".join(f"{row[k]:17.1f}%" for k in keys) +
              f"   | classic+Q beats YOLO-only {row['classic_learnedQ_vs_yolo|only']['wins']}/{len(a)}"
              f" (p={row['classic_learnedQ_vs_yolo|only']['p']:.2g})")
    json.dump(out, open(f"{CD}/eval.json", "w"), indent=1)
