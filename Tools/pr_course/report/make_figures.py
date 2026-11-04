"""Figures for the PR course report (SVG, print-friendly light surface).
Palette: validated reference slots 1-3 (blue, orange, aqua); aqua is < 3:1 on the surface, so every bar carries
a direct value label and every figure has a table in the report (relief rule)."""
import json, sys, os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = "/home/stanley/Github/Unity_Ship_Formation_Study"
OUT = sys.argv[1]
os.makedirs(OUT, exist_ok=True)
S1, S2, S3 = "#2a78d6", "#eb6834", "#1baf7a"
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"
plt.rcParams.update({"font.family": "Liberation Sans", "font.size": 9, "axes.edgecolor": GRID, "axes.labelcolor": INK2,
                     "xtick.color": INK2, "ytick.color": INK2, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "axes.axisbelow": True,
                     "legend.frameon": False, "svg.fonttype": "none"})


def save(fig, name):
    fig.savefig(f"{OUT}/{name}.svg", bbox_inches="tight"); plt.close(fig)


def bars(ax, groups, series, colors, names, fmt="{:.0f}"):
    n = len(series); w = 0.8 / n; x = np.arange(len(groups))
    for k, (vals, c, nm) in enumerate(zip(series, colors, names)):
        b = ax.bar(x + (k - (n - 1) / 2) * w, vals, w, color=c, edgecolor="white", linewidth=1.5, label=nm)
        for r, v in zip(b, vals):
            ax.text(r.get_x() + r.get_width() / 2, v + 1, fmt.format(v), ha="center", va="bottom", fontsize=7, color=INK2)
    ax.set_xticks(x, groups); ax.grid(axis="x", visible=False)


# Fig A: USV detection errors vs vertical speed of the leader's box
bins = ["0-2", "2-5", "5-10", "10-20", "20-40"]
miss = [1.83, 2.01, 2.53, 4.66, 14.74]; wrong = [0.52, 0.62, 0.81, 1.93, 7.56]
fig, ax = plt.subplots(figsize=(5.6, 2.6))
bars(ax, bins, [miss, wrong], [S1, S2], ["Leader missed", "Wrong box labelled leader"], "{:.1f}")
ax.set_xlabel("Vertical speed of the leader's box (px per 0.1 s step)"); ax.set_ylabel("% of frames"); ax.set_ylim(0, 17.5)
ax.legend(loc="upper left"); save(fig, "fig_usv_motion")

# Fig B: MLE of detection noise vs YOLO confidence (USV, all conditions)
conf = ["0.25-0.40", "0.40-0.55", "0.55-0.70", "0.70-0.80", "0.80-0.90"]
vx = [0.0115, 0.0119, 0.0035, 0.0012, 0.0005]; vy = [0.0199, 0.0161, 0.0165, 0.0177, 0.0137]
fig, ax = plt.subplots(figsize=(5.6, 2.5))
x = np.arange(len(conf))
ax.plot(x, vx, color=S1, lw=2, marker="o", ms=6, label="Horizontal error variance")
ax.plot(x, vy, color=S2, lw=2, marker="o", ms=6, label="Vertical error variance")
ax.set_yscale("log"); ax.set_xticks(x, conf); ax.set_xlabel("YOLO confidence"); ax.set_ylabel("MLE variance (box heights²)")
ax.text(x[-1] + 0.08, vx[-1], "horizontal", color=INK2, va="center", fontsize=8)
ax.text(x[-1] + 0.08, vy[-1], "vertical", color=INK2, va="center", fontsize=8)
ax.set_xlim(-0.3, len(conf) - 0.3); ax.legend(loc="lower left"); save(fig, "fig_usv_R")

# Fig C: innovation log-likelihood vs Q scale (USV fold 0)
q = [1, 3, 10, 30, 100, 300]
hand = [-12.618, -12.416, -12.316, -12.428, -12.728, -13.087]
learned = [-11.823, -11.372, -11.214, -11.416, -11.872, -12.395]
fig, ax = plt.subplots(figsize=(5.6, 2.5))
ax.plot(q, learned, color=S1, lw=2, marker="o", ms=6, label="Learned R")
ax.plot(q, hand, color=S2, lw=2, marker="o", ms=6, label="Hand-tuned R")
for ser in (learned, hand):
    i = int(np.argmax(ser)); ax.annotate("max", (q[i], ser[i]), xytext=(0, 7), textcoords="offset points", ha="center", fontsize=8, color=INK2)
ax.set_xscale("log"); ax.set_xticks(q, [f"{v}×" for v in q]); ax.minorticks_off()
ax.set_xlabel("Process noise Q, as a multiple of the drone code's value"); ax.set_ylabel("Mean innovation log-likelihood")
ax.legend(loc="lower left"); save(fig, "fig_q_likelihood")

# Fig D: USV tracking accuracy
U = json.load(open(f"{ROOT}/Experiments/PR_Course/usv/usv_report.json"))
groups = [("clear", "Clear"), ("rain", "Rain"), ("night", "Night"), ("night_rain", "Night+rain"), ("dark_storm", "Dark storm"), ("huge_waves", "Huge waves")]
arms = [("yolo_only", "YOLO only"), ("his", "Drone tracker (hand-tuned)"), ("his+learned_Q", "Drone tracker + MLE-learned Q")]
fig, ax = plt.subplots(figsize=(6.6, 2.7))
bars(ax, [g[1] for g in groups], [[U[f"{g}|{a}"]["all"]["success50"] for g, _ in groups] for a, _ in arms], [S1, S2, S3], [a[1] for a in arms])
ax.set_ylabel("Frames with IoU ≥ 0.5 (%)"); ax.set_ylim(0, 110); ax.legend(loc="upper center", ncol=3, bbox_to_anchor=(0.5, 1.2))
save(fig, "fig_usv_tracking")

# Fig E: drone tracking accuracy
D = json.load(open(f"{ROOT}/Experiments/PR_Course/drone/drone_report.json"))["results"]
cases = [("L1|testv4", "testv4\n1-frame delay"), ("L1|img7888", "IMG_7888\n1-frame delay"),
         ("L3|testv4", "testv4\n3-frame delay"), ("L3|img7888", "IMG_7888\n3-frame delay")]
fig, ax = plt.subplots(figsize=(6.6, 2.7))
bars(ax, [c[1] for c in cases], [[D[f"{c}|{a}"]["all"]["success50"] for c, _ in cases] for a, _ in arms], [S1, S2, S3], [a[1] for a in arms])
ax.set_ylabel("Frames with IoU ≥ 0.5 (%)"); ax.set_ylim(0, 110); ax.legend(loc="upper center", ncol=3, bbox_to_anchor=(0.5, 1.2))
save(fig, "fig_drone_tracking")
print("figures written to", OUT)
