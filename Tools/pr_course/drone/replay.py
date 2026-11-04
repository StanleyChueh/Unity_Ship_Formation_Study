"""Deterministic offline replay of the teammate's tracker (drone_pkg_v4/code/track.py) plus PR refinements.

His real-time loop runs YOLO in a background thread. Here a detection submitted at frame i arrives at frame i+L,
and the next submission happens at that same frame (his detector is re-armed as soon as it is idle), so
L=1 reproduces his RTX-class setup (YOLO ~11 ms << 33 ms frame) and L=3 a ~100 ms embedded board.
His detect() ignores the roi argument, so a per-frame full-frame YOLO dump (yolo_dump.py) is exact.

Arms (config flags):
  yolo_only   : newest delayed YOLO result, top-confidence box >= DET_THR (left panel of his video)
  his         : faithful port (flow every frame, hand gate, R = 60*(0.5/s)^2 isotropic, FLOW_R*(1+10/n))
  bayes_gate  : his gate+score replaced by a Gaussian-MLE minimum-risk Bayes classifier (Ch.2 + Ch.3-1)
  learned_R   : measurement noise from MLE fits (per axis, scaled by box size)       (Ch.3-1)
"""
import json, math
import cv2
import numpy as np

INIT_THR, DET_THR = 0.35, 0.22
GATE, SIZE_RATIO = 1.5, (0.25, 5.0)
MISS_MAX = 180
R_BASE, FLOW_R = 60.0, 30.0
MAX_AREA = 0.30


def to_cxcywh(b):
    x1, y1, x2, y2 = b[:4]
    return np.array([(x1 + x2) / 2, (y1 + y2) / 2, x2 - x1, y2 - y1], np.float32)


def make_kf(c, q_scale=1.0):
    kf = cv2.KalmanFilter(8, 4)
    F = np.eye(8, dtype=np.float32)
    for i in range(4):
        F[i, i + 4] = 1
    F[2, 6] = F[3, 7] = 0
    kf.transitionMatrix = F
    H = np.zeros((4, 8), np.float32)
    for i in range(4):
        H[i, i] = 1
    kf.measurementMatrix = H
    kf.processNoiseCov = (np.diag([1, 1, 0.2, 0.2, 2, 2, 0.01, 0.01]) * q_scale).astype(np.float32)
    kf.measurementNoiseCov = (np.eye(4) * R_BASE).astype(np.float32)
    kf.errorCovPost = (np.eye(8) * 100).astype(np.float32)
    kf.statePost = np.array([c[0], c[1], c[2], c[3], 0, 0, 0, 0], np.float32).reshape(8, 1)
    return kf


def flow_shift(g0, g1, box):
    cx, cy, bw, bh = box
    bw, bh = bw * 0.7, bh * 0.7
    x0, y0 = int(max(cx - bw / 2, 0)), int(max(cy - bh / 2, 0))
    x1, y1 = int(min(cx + bw / 2, g0.shape[1])), int(min(cy + bh / 2, g0.shape[0]))
    if x1 - x0 < 8 or y1 - y0 < 8:
        return None
    p0 = cv2.goodFeaturesToTrack(g0[y0:y1, x0:x1], 40, 0.01, 4)
    if p0 is None or len(p0) < 6:
        return None
    p0 = p0 + np.array([[[x0, y0]]], np.float32)
    lk = dict(winSize=(31, 31), maxLevel=4)
    p1, st1, _ = cv2.calcOpticalFlowPyrLK(g0, g1, p0, None, **lk)
    p0r, st2, _ = cv2.calcOpticalFlowPyrLK(g1, g0, p1, None, **lk)
    fb = np.linalg.norm((p0 - p0r).reshape(-1, 2), axis=1)
    good = (st1.ravel() == 1) & (st2.ravel() == 1) & (fb < 1.5)
    if good.sum() < 6:
        return None
    d = (p1 - p0).reshape(-1, 2)[good]
    return float(np.median(d[:, 0])), float(np.median(d[:, 1])), int(good.sum())


def det_filter(dets, W, H, thr):
    return [d for d in dets if d[4] >= thr and (d[2] - d[0]) * (d[3] - d[1]) <= MAX_AREA * W * H]


def features(det, ref, P=None):
    """Pattern vector for one candidate box, relative to the tracker's reference box at the detection frame.
    Distance is a Mahalanobis distance under the filter's own position covariance P (+ a nominal detection
    variance), so the acceptance region widens automatically while the tracker coasts (no hand-tuned growth)."""
    c = to_cxcywh(det)
    size = max(ref[2], ref[3], 1.0)
    d = np.array([c[0] - ref[0], c[1] - ref[1]], np.float64)
    S = (P if P is not None else np.zeros((2, 2))) + np.eye(2) * (0.1 * size) ** 2
    return np.array([det[4],
                     math.log1p(math.sqrt(d @ np.linalg.solve(S, d))),
                     math.log(max(c[2] * c[3], 1.0) / max(ref[2] * ref[3], 1.0)),
                     math.log(max(c[2], 1.0) / max(c[3], 1.0))], np.float64)


class BayesGate:
    """Two-class Gaussian classifier: omega1 = the drone, omega2 = anything else. MLE mean/covariance per class,
    minimum-risk rule: accept iff ln p(x|w1) - ln p(x|w2) > ln[(lam_fa/lam_miss) * P(w2)/P(w1)]."""

    def __init__(self, X, y, lam_ratio=3.0):
        self.p = []
        for k in (1, 0):
            Z = X[y == k]
            mu = Z.mean(0)
            S = np.cov(Z.T, bias=True) + 1e-6 * np.eye(Z.shape[1])
            self.p.append((mu, np.linalg.inv(S), np.linalg.slogdet(S)[1]))
        p1 = y.mean()
        self.thr = math.log(lam_ratio * (1 - p1) / p1)

    def llr(self, x):
        g = []
        for mu, Si, ld in self.p:
            d = x - mu
            g.append(-0.5 * d @ Si @ d - 0.5 * ld)
        return g[0] - g[1]


def iou(a, b):
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0])); iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    i = ix * iy; u = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - i
    return i / u if u > 0 else 0.0


def xyxy(c):
    return [c[0] - c[2] / 2, c[1] - c[3] / 2, c[0] + c[2] / 2, c[1] + c[3] / 2]


def _frames(video):
    """A video path, or a list of image paths (USV runs save one JPEG per control step)."""
    if isinstance(video, (list, tuple)):
        for p in video:
            yield cv2.imread(p, cv2.IMREAD_GRAYSCALE)
        return
    cap = cv2.VideoCapture(video)
    while True:
        ok, frame = cap.read()
        if not ok:
            return
        yield frame


def run(video, yolo, L=1, arm="his", gate=None, noise=None, gt=None, collect=False, use_flow=True, q_scale=1.0):
    """Returns per-frame output boxes (cx,cy,w,h or None) and, if collect, labelled candidate features."""
    frames_det = yolo["frames"]; W, H = yolo["W"], yolo["H"]
    frames = _frames(video)
    kf, miss, idx = None, 0, -1
    hist = {}; gbuf = {}; last_box = prev_gray = None
    pending = None  # (submit_idx, arrive_idx)
    outs, samples, flow_log, det_log, ll_log = [], [], [], [], []
    for frame in frames:
        idx += 1
        gray = frame if frame.ndim == 2 else cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        if arm == "yolo_only":
            if pending and pending[1] == idx:
                ds = det_filter(frames_det[pending[0]], W, H, DET_THR)
                last_box = tuple(to_cxcywh(max(ds, key=lambda d: d[4]))) if ds else None
                pending = None
            if pending is None:
                pending = (idx, idx + L)
            outs.append(last_box)
            continue
        if kf is not None:
            kf.predict()
        # 1) optical flow every frame
        if use_flow and kf is not None and last_box is not None and prev_gray is not None:
            fl = flow_shift(prev_gray, gray, last_box)
            if fl is not None:
                if noise:
                    s2 = max(last_box[2], last_box[3]) ** 2
                    Rf = np.diag([noise["flow_x"] * s2, noise["flow_y"] * s2, noise["wh"] * s2 * 4, noise["wh"] * s2 * 4])
                    kf.measurementNoiseCov = Rf.astype(np.float32)
                else:
                    kf.measurementNoiseCov = np.eye(4, dtype=np.float32) * FLOW_R * (1 + 10.0 / fl[2])
                meas = np.array([[last_box[0] + fl[0]], [last_box[1] + fl[1]], [last_box[2]], [last_box[3]]], np.float32)
                flow_log.append((idx, float(meas[0, 0]), float(meas[1, 0]), fl[2]))
                kf.correct(meas)
        # 2) delayed detection result
        if pending and pending[1] == idx:
            ridx = pending[0]; pending = None
            if kf is None:
                ds = det_filter(frames_det[ridx], W, H, DET_THR)
                if ds:
                    b = max(ds, key=lambda d: d[4])
                    if b[4] >= INIT_THR:
                        box = tuple(float(v) for v in to_cxcywh(b))
                        for j in range(ridx, idx):  # carry the delayed box forward with flow, as he does
                            if j in gbuf:
                                f2 = flow_shift(gbuf[j], gbuf[j + 1] if j + 1 < idx else gray, box)
                                if f2 is not None:
                                    box = (box[0] + f2[0], box[1] + f2[1], box[2], box[3])
                        kf, miss = make_kf(box, q_scale), 0
            else:
                ref = np.array(hist[ridx], np.float32) if ridx in hist else kf.statePost[:4, 0].copy()
                lat = L + 2  # his lat = det_ms/1000*fps + 2
                pad = lat * float(np.hypot(kf.statePost[4, 0], kf.statePost[5, 0]))
                chosen = None
                if arm in ("bayes_gate", "bayes_gate+learned_R") or collect:
                    cand = det_filter(frames_det[ridx], W, H, 0.05)
                    P = kf.errorCovPost[:2, :2].astype(np.float64)
                    feats = [features(d, ref, P) for d in cand]
                    if collect and gt is not None and gt[ridx] is not None:
                        for d, x in zip(cand, feats):
                            samples.append((x, int(iou(d[:4], gt[ridx]) >= 0.3)))
                if arm in ("bayes_gate", "bayes_gate+learned_R"):
                    scored = [(gate.llr(x), d) for d, x in zip(cand, feats)]
                    scored = [t for t in scored if t[0] > gate.thr]
                    if scored:
                        chosen = max(scored, key=lambda t: t[0])[1]
                else:
                    gate_r = (GATE * max(ref[2], ref[3]) + 20) * (1 + 0.15 * min(miss, 10)) + pad
                    pa = max(ref[2] * ref[3], 1.0); cands = []
                    for b in det_filter(frames_det[ridx], W, H, DET_THR):
                        c = to_cxcywh(b); d = float(np.hypot(c[0] - ref[0], c[1] - ref[1])); r = float(c[2] * c[3]) / pa
                        if d < gate_r and SIZE_RATIO[0] <= r <= SIZE_RATIO[1]:
                            cands.append((b, d))
                    if cands:
                        chosen = max(cands, key=lambda x: x[0][4] * np.exp(-x[1] / gate_r))[0]
                if chosen is not None:
                    c = to_cxcywh(chosen); s = chosen[4]
                    cur = kf.statePost[:4, 0]
                    meas = np.array([cur[0] + (c[0] - ref[0]), cur[1] + (c[1] - ref[1]), c[2], c[3]], np.float32)
                    if noise:
                        s2 = max(c[2], c[3]) ** 2
                        k = noise["det_scale"](s)
                        R = np.diag([noise["det_x"] * k * s2, noise["det_y"] * k * s2, noise["wh"] * s2, noise["wh"] * s2])
                        kf.measurementNoiseCov = R.astype(np.float32)
                    else:
                        kf.measurementNoiseCov = np.eye(4, dtype=np.float32) * R_BASE * float(np.clip((0.5 / max(s, 1e-3)) ** 2, 0.5, 4.0))
                    det_log.append((idx, ridx, c.tolist(), s))
                    # innovation log-likelihood ln N(meas; H x, H P H' + R): the quantity maximised to learn Q (Ch.3-1 MLE)
                    inn = meas.astype(np.float64) - kf.statePost[:4, 0].astype(np.float64)
                    Sm = kf.errorCovPost[:4, :4].astype(np.float64) + kf.measurementNoiseCov.astype(np.float64)
                    ll_log.append(-0.5 * (inn @ np.linalg.solve(Sm, inn) + np.linalg.slogdet(Sm)[1] + 4 * math.log(2 * math.pi)))
                    kf.correct(meas.reshape(4, 1)); miss = 0
                else:
                    miss += 1
                    if miss > MISS_MAX:
                        kf = None
        # 3) re-arm detector
        if pending is None:
            pending = (idx, idx + L)
        if kf is not None:
            cx, cy, bw, bh = [float(v) for v in kf.statePost[:4, 0]]
            last_box = (cx, cy, max(bw, 1), max(bh, 1)); hist[idx] = last_box
        else:
            last_box = None
        outs.append(last_box)
        prev_gray = gray; gbuf[idx] = gray
        gbuf.pop(idx - 40, None)
    return dict(outs=outs, samples=samples, flow=flow_log, det=det_log, ll=ll_log)
