"""Leader-boat detector built only from course methods (no neural network), for comparison with YOLOv8.

Stage 1  Fisher linear discriminant (Ch.3-2) on normalised 24x17 patches (grey + gradient magnitude, 816-D).
         Because the Fisher score w^T z is linear, it is evaluated at every position and scale of the image as a
         correlation (sliding window over a 7-level image pyramid). Shrinkage on S_w (Hughes effect, Ch.1/3-1).
         Trained twice: random negatives, then hard negatives mined from its own false peaks (design cycle, Ch.1).
Stage 2  PCA (Ch.3-2) of the top candidates -> Gaussian class-conditional densities with MLE mean/covariance
         (Ch.3-1) for leader vs non-leader, priors from candidate counts -> Bayes posterior (Ch.2). The posterior
         is the box confidence that the tracker thresholds, like YOLO's confidence.
All parameters are learned from training-fold frames only; the test seed is never seen.
"""
import cv2
import numpy as np

TW, TH = 24, 17                     # template size (aspect 0.71 = median leader box)
WIDTHS = [22 * 1.2 ** k for k in range(7)]   # leader box widths searched, 22..66 px at full resolution


def configure(tw, th, widths):
    """Change the window geometry (e.g. wide drone boxes). Call before any pool is forked."""
    global TW, TH, WIDTHS
    TW, TH, WIDTHS = tw, th, list(widths)


def channels(img):
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
    gx = cv2.Sobel(g, cv2.CV_32F, 1, 0, ksize=3); gy = cv2.Sobel(g, cv2.CV_32F, 0, 1, ksize=3)
    return [g, np.sqrt(gx * gx + gy * gy)]


def norm_box(b):
    """Area-preserving box with the template aspect, centred on b (x1,y1,x2,y2)."""
    cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
    w = np.sqrt(max(b[2] - b[0], 1) * max(b[3] - b[1], 1) * TW / TH); h = w * TH / TW
    return cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2


def pyramid(chs):
    """Each channel resized so that a leader box of width WIDTHS[k] becomes TW pixels wide."""
    return [(TW / bw, [cv2.resize(c, None, fx=TW / bw, fy=TW / bw, interpolation=cv2.INTER_AREA) for c in chs]) for bw in WIDTHS]


def window(pyr, k, x, y):
    out = []
    for c in pyr[k][1]:
        p = c[y:y + TH, x:x + TW].ravel(); out.append((p - p.mean()) / (p.std() + 1e-3))
    return np.concatenate(out)


def patch(pyr, b):
    """Feature vector of box b: the pyramid window nearest in scale and position (the same pixels the scan sees)."""
    nb = norm_box(b); bw = nb[2] - nb[0]
    k = int(np.argmin([abs(np.log(bw / w)) for w in WIDTHS])); f, cs = pyr[k]
    H, W = cs[0].shape
    x = int(np.clip(round((nb[0] + nb[2]) / 2 * f - TW / 2), 0, W - TW)); y = int(np.clip(round((nb[1] + nb[3]) / 2 * f - TH / 2), 0, H - TH))
    return window(pyr, k, x, y)


def fisher(Xp, Xn, shrink=0.05):
    m1, m0 = Xp.mean(0), Xn.mean(0)
    Sw = np.cov(Xp, rowvar=False) * (len(Xp) - 1) + np.cov(Xn, rowvar=False) * (len(Xn) - 1)
    Sw /= len(Xp) + len(Xn) - 2
    Sw = (1 - shrink) * Sw + shrink * np.trace(Sw) / len(Sw) * np.eye(len(Sw))
    w = np.linalg.solve(Sw, m1 - m0)
    w /= np.linalg.norm(w)
    s1, s0 = Xp @ w, Xn @ w
    return dict(w=w.astype(np.float32), mid=float((s1.mean() + s0.mean()) / 2))


def score_maps(pyr, w):
    """Fisher score w^T z of every window at every scale: correlation plus box-filter mean/std (z = per-window z-score)."""
    W = w.reshape(len(pyr[0][1]), TH, TW); out = []
    for f, cs in pyr:
        tot = None
        for im, wc in zip(cs, W):
            corr = cv2.matchTemplate(im, wc, cv2.TM_CCORR)
            mu = cv2.boxFilter(im, -1, (TW, TH), anchor=(0, 0), normalize=True, borderType=cv2.BORDER_CONSTANT)
            mu2 = cv2.boxFilter(im * im, -1, (TW, TH), anchor=(0, 0), normalize=True, borderType=cv2.BORDER_CONSTANT)
            hh, ww = corr.shape
            mu, mu2 = mu[:hh, :ww], mu2[:hh, :ww]
            sd = np.sqrt(np.maximum(mu2 - mu * mu, 0)) + 1e-3
            s = (corr - mu * float(wc.sum())) / sd
            tot = s if tot is None else tot + s
        out.append((tot, f))
    return out


def peaks(maps, k=10, nms_iou=0.3):
    cands = []
    for k, (s, f) in enumerate(maps):
        dil = cv2.dilate(s, np.ones((5, 5), np.uint8))
        ys, xs = np.where((s >= dil) & (s > np.partition(s.ravel(), -30)[-30] - 1e-6))
        for y, x in zip(ys, xs):
            cands.append((float(s[y, x]), x / f, y / f, (x + TW) / f, (y + TH) / f, k, int(x), int(y)))
    cands.sort(key=lambda c: -c[0]); keep = []
    for c in cands:
        if all(iou(c[1:5], d[1:5]) < nms_iou for d in keep):
            keep.append(c)
        if len(keep) == k:
            break
    return keep


def iou(a, b):
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0])); iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    return inter / ((a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter + 1e-9)


class GaussBayes:
    """PCA to d dims, then one Gaussian per class with MLE mean/covariance, priors from counts (Ch.2, 3-1, 3-2)."""

    def __init__(self, X, y, d=30, reg=1e-3):
        self.mu = X.mean(0)
        _, _, Vt = np.linalg.svd(X - self.mu, full_matrices=False)
        self.P = Vt[:d].T
        Z = (X - self.mu) @ self.P
        self.cls = []
        for c in (0, 1):
            Zc = Z[y == c]; m = Zc.mean(0); S = np.cov(Zc, rowvar=False, bias=True)   # MLE: 1/n
            S += reg * np.trace(S) / d * np.eye(d)
            _, logdet = np.linalg.slogdet(S)
            self.cls.append((m, np.linalg.inv(S), logdet, np.log(len(Zc) / len(Z))))

    def posterior(self, X):
        Z = (np.atleast_2d(X) - self.mu) @ self.P
        g = []
        for m, Si, logdet, lp in self.cls:
            d = Z - m
            g.append(-0.5 * np.einsum("ij,jk,ik->i", d, Si, d) - 0.5 * logdet + lp)
        g = np.array(g)
        return 1.0 / (1.0 + np.exp(np.clip(g[0] - g[1], -50, 50)))


def detect(img, model, k=10):
    """Returns [[x1,y1,x2,y2,posterior], ...] sorted by posterior (YOLO raw_detections format, class dropped)."""
    pyr = pyramid(channels(img))
    c = peaks(score_maps(pyr, model["fisher"]["w"]), k)
    if not c:
        return [], []
    X = np.array([window(pyr, b[5], b[6], b[7]) for b in c])
    p = model["bayes"].posterior(X)
    out = [[*b[1:5], float(q)] for b, q in zip(c, p)]
    out.sort(key=lambda d: -d[4])
    return out, c
