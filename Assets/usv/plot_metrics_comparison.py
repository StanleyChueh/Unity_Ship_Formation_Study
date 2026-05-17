import argparse
import csv
import os
from datetime import datetime
from statistics import mean, stdev

import matplotlib.pyplot as plt


METRICS = [
    ("pred_mae", "Prediction MAE (offset)"),
    ("pred_flips", "Prediction Flip Count"),
    ("det_rate_pct", "Detection Rate (%)"),
    ("stale_rate_pct", "Stale Rate (%)"),
    ("dsteer_mean_abs", "Mean |ΔSteer|"),
    ("dthr_mean_abs", "Mean |ΔThrottle|"),
]


def classify_kalman(ratio):
    if ratio >= 0.95:
        return "Kalman ON"
    if ratio <= 0.05:
        return "Kalman OFF"
    return "Kalman Mixed"


def read_summary_rows(csv_path):
    rows = []
    with open(csv_path, "r", newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            try:
                row = {
                    "run_id": r["run_id"],
                    "timestamp": r["timestamp"],
                    "elapsed_s": float(r["elapsed_s"]),
                    "kalman_on_ratio": float(r["kalman_on_ratio"]),
                    "side": r["side"],
                    "samples": int(r["samples"]),
                    "det_rate_pct": float(r["det_rate_pct"]),
                    "stale_rate_pct": float(r["stale_rate_pct"]),
                    "dsteer_mean_abs": float(r["dsteer_mean_abs"]),
                    "dthr_mean_abs": float(r["dthr_mean_abs"]),
                    "pred_mae": float(r["pred_mae"]),
                    "pred_flips": float(r["pred_flips"]),
                    "kalman_label": classify_kalman(float(r["kalman_on_ratio"])),
                }
            except Exception:
                continue
            rows.append(row)
    return rows


def aggregate(rows, metric):
    grouped = {}
    for r in rows:
        key = (r["side"], r["kalman_label"])
        grouped.setdefault(key, []).append(r[metric])

    stats = {}
    for key, values in grouped.items():
        stats[key] = {
            "n": len(values),
            "mean": mean(values) if values else 0.0,
            "std": stdev(values) if len(values) > 1 else 0.0,
        }
    return stats


def plot_metric_grid(rows, out_png):
    sides = ["Left", "Right"]
    labels = ["Kalman OFF", "Kalman ON", "Kalman Mixed"]

    fig, axes = plt.subplots(2, 3, figsize=(16, 9))
    axes = axes.flatten()

    for ax, (metric, title) in zip(axes, METRICS):
        stats = aggregate(rows, metric)

        x = [0, 1]
        width = 0.23
        offsets = [-width, 0.0, width]

        for i, klabel in enumerate(labels):
            means = []
            errs = []
            ns = []
            for side in sides:
                entry = stats.get((side, klabel), {"mean": 0.0, "std": 0.0, "n": 0})
                means.append(entry["mean"])
                errs.append(entry["std"])
                ns.append(entry["n"])

            xpos = [v + offsets[i] for v in x]
            ax.bar(xpos, means, width=width, yerr=errs, capsize=3, label=f"{klabel}")

            for j, v in enumerate(means):
                ax.text(xpos[j], v, f"n={ns[j]}", ha="center", va="bottom", fontsize=8, rotation=90)

        ax.set_title(title)
        ax.set_xticks(x)
        ax.set_xticklabels(sides)
        ax.grid(axis="y", alpha=0.3)

    handles, legend_labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, legend_labels, loc="upper center", ncol=3)
    fig.suptitle("USV Tracking Metrics Comparison")
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    fig.savefig(out_png, dpi=220)
    plt.close(fig)


def plot_pred_mae_vs_kalman(rows, out_png):
    side_colors = {"Left": "tab:blue", "Right": "tab:orange"}
    fig, ax = plt.subplots(figsize=(8, 5))

    for side in ["Left", "Right"]:
        subset = [r for r in rows if r["side"] == side]
        xs = [r["kalman_on_ratio"] for r in subset]
        ys = [r["pred_mae"] for r in subset]
        ax.scatter(xs, ys, alpha=0.7, s=35, c=side_colors[side], label=side)

    ax.set_xlabel("Kalman ON Ratio (0=OFF, 1=ON)")
    ax.set_ylabel("Prediction MAE")
    ax.set_title("Prediction MAE vs Kalman Usage")
    ax.grid(alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_png, dpi=220)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description="Plot Kalman ON/OFF experiment comparison from run_summaries.csv")
    parser.add_argument(
        "--input",
        default=os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "experiment_metrics", "run_summaries.csv")),
        help="Path to run_summaries.csv",
    )
    parser.add_argument(
        "--output-dir",
        default=os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "experiment_metrics", "plots")),
        help="Directory to save figures",
    )
    args = parser.parse_args()

    if not os.path.exists(args.input):
        raise FileNotFoundError(f"Input summary file not found: {args.input}")

    rows = read_summary_rows(args.input)
    if not rows:
        raise RuntimeError("No valid rows found in summary CSV.")

    os.makedirs(args.output_dir, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    out_grid = os.path.join(args.output_dir, f"metrics_comparison_{stamp}.png")
    out_scatter = os.path.join(args.output_dir, f"pred_mae_vs_kalman_{stamp}.png")

    plot_metric_grid(rows, out_grid)
    plot_pred_mae_vs_kalman(rows, out_scatter)

    print(f"Saved: {out_grid}")
    print(f"Saved: {out_scatter}")


if __name__ == "__main__":
    main()
