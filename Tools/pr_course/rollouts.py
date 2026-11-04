"""Evidence package: per-frame replays saved, statistics, and side-by-side detection videos.
Arms: YOLO only | drone tracker hand-tuned | drone tracker + MLE-learned Q.
Learned Q values are the ones the innovation-likelihood search chose on the TRAINING data (see analyze.py / usv_replay.py logs):
  drone, trained on the other video: test testv4 -> Q x100, test img7888 -> Q x10 (same at L=1 and L=3); USV: Q x10 in both folds.
Usage: python rollouts.py OUTDIR"""
import glob, json, math, os, subprocess, sys
from multiprocessing import Pool
import cv2
import numpy as np
from scipy import stats
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "drone"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import replay as rp
import analyze as an
import usv_replay as uv

cv2.setNumThreads(1)
ROOT = "/home/stanley/Github/Unity_Ship_Formation_Study"
E = f"{ROOT}/Experiments/PR_Course/drone"
OUT = sys.argv[1]; os.makedirs(OUT, exist_ok=True)
ARMS = [("yolo_only", "YOLO only", (214, 120, 42)), ("his", "Drone tracker (hand-tuned)", (52, 104, 235)),
        ("learned_Q", "Drone tracker + MLE-learned Q", (122, 175, 27))]   # BGR of the report palette
DRONE_Q = {"testv4": 100, "img7888": 10}


def ious(outs, gt):
    return np.array([rp.iou(rp.xyxy(o), g) if (g is not None and o is not None) else (0.0 if g is not None else np.nan)
                     for o, g in zip(outs, gt)])


def block_bootstrap(a, b, block, n=4000, seed=0):
    """CI of mean(a) - mean(b) over scored frames, resampling contiguous blocks (frames are not independent)."""
    m = ~np.isnan(a); a, b = a[m], b[m]; k = len(a) // block
    da = a[:k * block].reshape(k, block).mean(1); db = b[:k * block].reshape(k, block).mean(1)
    rng = np.random.default_rng(seed); idx = rng.integers(0, k, (n, k))
    diffs = (da[idx] - db[idx]).mean(1)
    return float(np.mean(a - b)), float(np.percentile(diffs, 2.5)), float(np.percentile(diffs, 97.5)), int((da > db).sum()), int((da < db).sum()), k


def drone_run(args):
    v, L = args
    gt, _ = an.fuse_gt(f"{E}/gt_dino_{v}.json"); y = json.load(open(f"{E}/yolo_{v}.json")); vid = f"{E}/videos/{v}.mp4"
    outs = {"yolo_only": rp.run(vid, y, L=L, arm="yolo_only")["outs"], "his": rp.run(vid, y, L=L, arm="his")["outs"],
            "learned_Q": rp.run(vid, y, L=L, arm="his", q_scale=DRONE_Q[v])["outs"]}
    return v, L, gt, outs


def usv_run(seq):
    q = uv.load(*seq)
    outs = {"yolo_only": rp.run(q["paths"], q["yolo"], L=1, arm="yolo_only")["outs"],
            "his": rp.run(q["paths"], q["yolo"], L=1, arm="his")["outs"],
            "learned_Q": rp.run(q["paths"], q["yolo"], L=1, arm="his", q_scale=10)["outs"]}
    return q["name"], q["group"], q["gt"], q["paths"], outs


def put(img, text, org, scale=0.6, color=(255, 255, 255), th=1):
    cv2.putText(img, text, org, cv2.FONT_HERSHEY_SIMPLEX, scale, (0, 0, 0), th + 3, cv2.LINE_AA)
    cv2.putText(img, text, org, cv2.FONT_HERSHEY_SIMPLEX, scale, color, th, cv2.LINE_AA)


def render(frames, gt, outs, path, fps, title, crop=None, panel_w=640):
    """frames: iterable of BGR images. crop: (w, h) window centred on the ground truth (USV: tiny boat)."""
    I = {a: ious(outs[a], gt) for a, _, _ in ARMS}
    hits = {a: 0 for a, _, _ in ARMS}; scored = 0
    tmp = path + ".tmp.mp4"; wr = None; cc = None
    for i, fr in enumerate(frames):
        g = gt[i]
        if g is not None:
            scored += 1
            for a, _, _ in ARMS:
                hits[a] += I[a][i] >= 0.5
        if crop:
            if g is not None:
                cc = ((g[0] + g[2]) / 2, (g[1] + g[3]) / 2) if cc is None else (0.8 * cc[0] + 0.2 * (g[0] + g[2]) / 2, 0.8 * cc[1] + 0.2 * (g[1] + g[3]) / 2)
            c = cc or (fr.shape[1] / 2, fr.shape[0] / 2)
            x0 = int(min(max(c[0] - crop[0] / 2, 0), fr.shape[1] - crop[0])); y0 = int(min(max(c[1] - crop[1] / 2, 0), fr.shape[0] - crop[1]))
        else:
            x0, y0 = 0, 0
        panels = []
        for a, name, col in ARMS:
            im = fr.copy()
            if g is not None:
                cv2.rectangle(im, (int(g[0]), int(g[1])), (int(g[2]), int(g[3])), (60, 220, 60), 1, cv2.LINE_AA)
            o = outs[a][i]
            if o is not None:
                b = rp.xyxy(o); cv2.rectangle(im, (int(b[0]), int(b[1])), (int(b[2]), int(b[3])), col, 2, cv2.LINE_AA)
            if crop:
                im = im[y0:y0 + crop[1], x0:x0 + crop[0]]
            s = panel_w / im.shape[1]; im = cv2.resize(im, (panel_w, int(im.shape[0] * s)), interpolation=cv2.INTER_LINEAR)
            cv2.rectangle(im, (0, 0), (panel_w, 58), (0, 0, 0), -1)
            put(im, name, (8, 22), 0.58, (255, 255, 255), 1)
            cur = I[a][i]
            state = "no ground truth" if np.isnan(cur) else (f"IoU {cur:.2f}" + ("  LOST" if cur < 0.1 else ""))
            put(im, f"{state}   tracked so far: {100 * hits[a] / max(scored, 1):.1f}%", (8, 46), 0.5,
                (90, 90, 255) if (not np.isnan(cur) and cur < 0.1) else (220, 220, 220), 1)
            cv2.rectangle(im, (0, 0), (panel_w - 1, im.shape[0] - 1), col, 3)
            panels.append(im)
        canvas = np.hstack(panels)
        bar = np.zeros((34, canvas.shape[1], 3), np.uint8)
        put(bar, f"{title}   |   frame {i}   |   green = ground truth, colour = tracker output   |   'tracked' = IoU >= 0.5", (8, 23), 0.55)
        canvas = np.vstack([bar, canvas])
        if wr is None:
            wr = cv2.VideoWriter(tmp, cv2.VideoWriter_fourcc(*"mp4v"), fps, (canvas.shape[1], canvas.shape[0]))
        wr.write(canvas)
    wr.release()
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", tmp, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "23", path], check=True)
    os.remove(tmp)
    return {a: 100 * hits[a] / scored for a, _, _ in ARMS}


def drone_frames(v):
    cap = cv2.VideoCapture(f"{E}/videos/{v}.mp4")
    while True:
        ok, f = cap.read()
        if not ok:
            return
        yield f


if __name__ == "__main__":
    pool = Pool(8); report = {"drone": {}, "usv": {}}
    # ---------------- drone ----------------
    D = pool.map(drone_run, [(v, L) for L in (1, 3) for v in ("testv4", "img7888")])
    print("DRONE (block bootstrap over 1 s blocks, 95% CI of the difference in % frames tracked)")
    for v, L, gt, outs in D:
        I = {a: ious(outs[a], gt) for a, _, _ in ARMS}; ok = {a: (I[a] >= 0.5).astype(float) for a in I}
        for a in ok: ok[a][np.isnan(I[a])] = np.nan
        r = {a: float(np.nanmean(ok[a]) * 100) for a in ok}
        for base in ("his", "yolo_only"):
            d, lo, hi, w, l, k = block_bootstrap(ok["learned_Q"], ok[base], 30)
            r[f"learnedQ_minus_{base}"] = dict(diff=100 * d, ci=[100 * lo, 100 * hi], blocks_better=w, blocks_worse=l, blocks=k)
        report["drone"][f"L{L}|{v}"] = r
        print(f"  {v:8s} L={L}: YOLO {r['yolo_only']:.1f}  hand {r['his']:.1f}  learnedQ {r['learned_Q']:.1f} | "
              f"learnedQ-hand {r['learnedQ_minus_his']['diff']:+.1f} [{r['learnedQ_minus_his']['ci'][0]:+.1f}, {r['learnedQ_minus_his']['ci'][1]:+.1f}] "
              f"better/worse blocks {r['learnedQ_minus_his']['blocks_better']}/{r['learnedQ_minus_his']['blocks_worse']} | "
              f"learnedQ-YOLO {r['learnedQ_minus_yolo_only']['diff']:+.1f} [{r['learnedQ_minus_yolo_only']['ci'][0]:+.1f}, {r['learnedQ_minus_yolo_only']['ci'][1]:+.1f}]", flush=True)
        name = f"drone_{v}_delay{L}.mp4"
        render(drone_frames(v), gt, outs, f"{OUT}/{name}", 30,
               f"Drone {v} - offline replay, YOLO result {L} frame(s) late")
        print("   video:", name, flush=True)
    # ---------------- USV ----------------
    R = pool.map(usv_run, uv.seqs())
    print("\nUSV (per-sequence % frames tracked; Wilcoxon signed-rank, paired over sequences)")
    rows = []
    for name, group, gt, paths, outs in R:
        I = {a: ious(outs[a], gt) for a in outs}
        rows.append((name, group, {a: float(np.mean(I[a][~np.isnan(I[a])] >= 0.5) * 100) if np.any(~np.isnan(I[a])) else np.nan for a in I}, gt, paths, outs))
    for grp in ["all", "clear", "rain", "night", "night_rain", "dark_storm", "huge_waves"]:
        sel = [r for r in rows if grp == "all" or r[1] == grp]
        q = np.array([r[2]["learned_Q"] for r in sel]); h = np.array([r[2]["his"] for r in sel]); yo = np.array([r[2]["yolo_only"] for r in sel])
        m = ~np.isnan(q) & ~np.isnan(h) & ~np.isnan(yo)
        ph = stats.wilcoxon(q[m], h[m]).pvalue if m.sum() > 5 else float("nan")
        py = stats.wilcoxon(q[m], yo[m]).pvalue if m.sum() > 5 else float("nan")
        res = dict(n=int(m.sum()), better_than_hand=int((q[m] > h[m]).sum()), better_than_yolo=int((q[m] > yo[m]).sum()),
                   median_gain_vs_hand=float(np.median(q[m] - h[m])), median_gain_vs_yolo=float(np.median(q[m] - yo[m])), p_vs_hand=float(ph), p_vs_yolo=float(py))
        report["usv"][grp] = res
        print(f"  {grp:11s} n={res['n']:2d}  learnedQ > hand in {res['better_than_hand']}/{res['n']} (median {res['median_gain_vs_hand']:+.1f} pts, p={ph:.2g})"
              f"   learnedQ > YOLO in {res['better_than_yolo']}/{res['n']} (median {res['median_gain_vs_yolo']:+.1f} pts, p={py:.2g})", flush=True)
    # videos: the huge-wave and clear sequences with the largest gain over the hand-tuned tracker, plus a dark-storm one (honest case)
    picks = []
    for grp in ("huge_waves", "clear", "dark_storm"):
        cand = [r for r in rows if r[1] == grp and not np.isnan(r[2]["learned_Q"])]
        picks.append(max(cand, key=lambda r: r[2]["learned_Q"] - r[2]["his"]) if grp != "dark_storm"
                     else sorted(cand, key=lambda r: r[2]["learned_Q"] - r[2]["his"])[len(cand) // 2])
    for name, group, sc, gt, paths, outs in picks:
        fn = f"usv_{group}_{name.replace('/', '_')}.mp4"
        render((cv2.imread(p) for p in paths), gt, outs, f"{OUT}/{fn}", 10,
               f"USV {group} {name.split('_')[-1]} camera - offline replay, YOLO result 1 step (0.1 s) late", crop=(480, 270))
        report["usv"].setdefault("videos", []).append(dict(file=fn, sequence=name, **sc))
        print("   video:", fn, {k: round(v, 1) for k, v in sc.items()}, flush=True)
    json.dump(report, open(f"{OUT}/evidence.json", "w"), indent=1, default=float)
