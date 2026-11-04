"""PNG charts + GIF clips for Documentation/PR_Course/README.md. All numbers come from the evidence JSON files.
Palette: validated reference slots 1-3 (blue, orange, aqua; aqua < 3:1 so every bar carries a value label).
Usage: python make_readme_media.py OUT_DIR"""
import json, os, subprocess, sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = "/home/stanley/Github/Unity_Ship_Formation_Study"
EXP = f"{ROOT}/Experiments/PR_Course"
OUT = sys.argv[1]; os.makedirs(OUT, exist_ok=True)
S1, S2, S3 = "#2a78d6", "#eb6834", "#1baf7a"
INK2, GRID = "#52514e", "#e4e3df"
plt.rcParams.update({"font.family": "Liberation Sans", "font.size": 10, "axes.edgecolor": GRID, "axes.labelcolor": INK2,
                     "xtick.color": INK2, "ytick.color": INK2, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "axes.axisbelow": True, "legend.frameon": False,
                     "figure.facecolor": "white"})
ARMS = [("YOLO only", S1), ("Drone tracker, hand-tuned", S2), ("Drone tracker + MLE-learned Q (course method)", S3)]


def bars(groups, series, title, name, ylabel="Frames tracked, IoU ≥ 0.5 (%)", width=9.5):
    fig, ax = plt.subplots(figsize=(width, 3.6), dpi=170)
    n = len(series); w = 0.8 / n; x = np.arange(len(groups))
    for k, (vals, (lab, col)) in enumerate(zip(series, ARMS)):
        b = ax.bar(x + (k - (n - 1) / 2) * w, vals, w, color=col, edgecolor="white", linewidth=1.5, label=lab)
        for r, v in zip(b, vals):
            ax.text(r.get_x() + r.get_width() / 2, v + 1, f"{v:.0f}", ha="center", va="bottom", fontsize=8, color=INK2)
    ax.set_xticks(x, groups); ax.grid(axis="x", visible=False); ax.set_ylim(0, 112); ax.set_ylabel(ylabel)
    ax.set_title(title, loc="left", fontsize=11, color="#0b0b0b", pad=24)
    ax.legend(loc="upper left", ncol=3, bbox_to_anchor=(0, 1.13), fontsize=9)
    fig.savefig(f"{OUT}/{name}.png", bbox_inches="tight"); plt.close(fig)


# boat, normal conditions (e07 replay, two folds)
U = json.load(open(f"{EXP}/usv/usv_report.json"))
g = [("clear", "Clear"), ("rain", "Rain"), ("night", "Night"), ("night_rain", "Night+rain"), ("dark_storm", "Dark storm"), ("huge_waves", "Huge waves\n(sea 3)")]
bars([b for _, b in g], [[U[f"{k}|{a}"]["all"]["success50"] for k, _ in g] for a in ("yolo_only", "his", "his+learned_Q")],
     "USV, 64 camera sequences (6 conditions)", "chart_usv_conditions")
# boat, extreme waves (e08, pre-registered)
X = json.load(open(f"{EXP}/rollouts/evidence_e08.json"))["cases"]
xg = [("X1", "Sea 4\nclear"), ("X2", "Sea 5\nclear"), ("X4", "Sea 4 +\nheavy rain"), ("X3", "Sea 4 +\ndark storm"), ("X5", "Sea 3 +\ndark storm")]
bars([b for _, b in xg], [[X[k][a] for k, _ in xg] for a in ("yolo", "hand", "learned_Q")],
     "USV, extreme waves and weather (pre-registered e08, 30 new sequences)", "chart_usv_extreme")
# drone (cross-video) + held-out Tello video
D = json.load(open(f"{EXP}/rollouts/evidence.json"))["drone"]; T = json.load(open(f"{EXP}/rollouts/evidence_img7923.json"))
dg = [("L1|testv4", "testv4\n1-frame delay"), ("L1|img7888", "IMG_7888\n1-frame delay"), ("L3|testv4", "testv4\n3-frame delay"),
      ("L3|img7888", "IMG_7888\n3-frame delay")]
vals = [[D[k][a] for k, _ in dg] + [T[L]["results"][a]["all"]["success50"] for L in ("L1", "L3")] for a in ("yolo_only", "his", "learned_Q")]
bars([b for _, b in dg] + ["Held-out Tello\n1-frame delay", "Held-out Tello\n3-frame delay"], vals,
     "Drone videos (Q learned on the other videos only)", "chart_drone", width=10.5)
# motivation: YOLO errors vs vertical speed of the box (USV)
fig, ax = plt.subplots(figsize=(6.4, 3.0), dpi=170)
bins = ["0-2", "2-5", "5-10", "10-20", "20-40"]; miss = [1.83, 2.01, 2.53, 4.66, 14.74]; wrong = [0.52, 0.62, 0.81, 1.93, 7.56]
x = np.arange(5)
for k, (v, lab, col) in enumerate([(miss, "YOLO missed the leader", S1), (wrong, "YOLO labelled the wrong box", S2)]):
    b = ax.bar(x + (k - 0.5) * 0.4, v, 0.4, color=col, edgecolor="white", linewidth=1.5, label=lab)
    for r, val in zip(b, v): ax.text(r.get_x() + r.get_width() / 2, val + 0.3, f"{val:.1f}", ha="center", fontsize=8, color=INK2)
ax.set_xticks(x, bins); ax.grid(axis="x", visible=False); ax.set_xlabel("Vertical speed of the leader's box (px per 0.1 s)")
ax.set_ylabel("% of frames"); ax.legend(loc="upper left"); ax.set_title("Why: fast vertical motion breaks detection (USV, 259k frames)", loc="left", fontsize=11)
fig.savefig(f"{OUT}/chart_motivation.png", bbox_inches="tight"); plt.close(fig)
# method: innovation likelihood vs Q (USV fold 0)
fig, ax = plt.subplots(figsize=(6.4, 3.0), dpi=170)
q = [1, 3, 10, 30, 100, 300]
for v, lab, col in [([-11.823, -11.372, -11.214, -11.416, -11.872, -12.395], "learned R", S1), ([-12.618, -12.416, -12.316, -12.428, -12.728, -13.087], "hand-tuned R", S2)]:
    ax.plot(q, v, color=col, lw=2, marker="o", ms=6, label=lab); i = int(np.argmax(v))
    ax.annotate("max", (q[i], v[i]), xytext=(0, 7), textcoords="offset points", ha="center", fontsize=8, color=INK2)
ax.set_xscale("log"); ax.set_xticks(q, [f"{v}×" for v in q]); ax.minorticks_off(); ax.legend(loc="lower left")
ax.set_xlabel("Process noise Q (multiple of the drone code's value)"); ax.set_ylabel("Mean innovation log-likelihood")
ax.set_title("MLE picks Q = 10× on the boat (10 Hz vs 30 fps)", loc="left", fontsize=11)
fig.savefig(f"{OUT}/chart_q_likelihood.png", bbox_inches="tight"); plt.close(fig)

# GIF clips (illustrative; the tables give the pooled numbers)
R = f"{EXP}/rollouts"
clips = [("drone_testv4_delay3.mp4", 3, 8, "gif_drone_slow_detector"),
         ("usv_e08_X2_Sea5_clear_seed6007_left.mp4", 30, 8, "gif_usv_sea5"),
         ("usv_huge_waves_C10_huge_waves_s_dropout_5147_on_pv_Right.mp4", 35, 8, "gif_usv_huge_waves"),
         ("usv_e08_X4_Sea4_heavyrain_seed6007_left.mp4", 30, 8, "gif_usv_sea4_heavy_rain"),
         ("usv_e08_X3_Sea4_darkstorm_seed6007_left.mp4", 30, 8, "gif_usv_dark_storm")]
for src, ss, dur, name in clips:
    vf = "fps=8,scale=960:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=128[p];[b][p]paletteuse=dither=bayer:bayer_scale=4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(ss), "-t", str(dur), "-i", f"{R}/{src}", "-vf", vf, "-loop", "0", f"{OUT}/{name}.gif"], check=True)
for f in sorted(os.listdir(OUT)):
    print(f, round(os.path.getsize(f"{OUT}/{f}") / 1e6, 2), "MB")
