import argparse
import csv
import os
from datetime import datetime
from statistics import mean, stdev

import matplotlib.pyplot as plt
from matplotlib import rcParams


try:
    import usv.config as config
except Exception:
    try:
        import config
    except Exception:
        config = None

# Base metrics (follower detection will be inserted below if enabled)
METRICS = [
    ("leader_det_rate_pct", "Leader Detection Rate (%)"),
    ("stale_rate_pct", "Stale Rate (%)"),
    ("dsteer_mean_abs", "Steer Jerkiness (|ΔSteer|/sample)"),
    ("dthr_mean_abs", "Throttle Jerkiness (|ΔThrottle|/sample)"),
    ("mean_distance", "Mean Distance (a.u.)"),
    ("mean_formation_error", "Formation Error (norm.)"),
    ("mean_formation_iou", "Formation IoU (mean)"),
    ("mean_per_boat_rms_m", "Per-Boat RMS (m)"),
    ("mean_centroid_offset_m", "Centroid Offset (m)"),
]

# Insert follower detection metric only when side/follower detection is enabled
if config is None or not hasattr(config, "ENABLE_SIDE_DETECTION") or getattr(config, "ENABLE_SIDE_DETECTION"):
    METRICS.insert(1, ("follower_det_rate_pct", "Follower Detection Rate (%)"))


def classify_kalman(ratio):
    if ratio >= 0.95:
        return "Kalman ON"
    if ratio <= 0.05:
        return "Kalman OFF"
    return "Kalman Mixed"


# Publication-quality matplotlib defaults
rcParams.update(
    {
        "font.family": "serif",
        "font.serif": ["Times New Roman", "DejaVu Serif"],
        "font.size": 11,
        "axes.titlesize": 12,
        "axes.labelsize": 11,
        "legend.fontsize": 10,
        "xtick.labelsize": 10,
        "ytick.labelsize": 10,
        "figure.dpi": 220,
    }
)

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
                    "leader_det_rate_pct": float(r.get("leader_det_rate_pct", r.get("det_rate_pct", 0.0))),
                    "follower_det_rate_pct": float(r.get("follower_det_rate_pct", 0.0)),
                    "stale_rate_pct": float(r["stale_rate_pct"]),
                    "dsteer_mean_abs": float(r["dsteer_mean_abs"]),
                    "dthr_mean_abs": float(r["dthr_mean_abs"]),
                    "mean_distance": float(r.get("mean_distance", 0.0)),
                    "mean_speed_mps": float(r.get("mean_speed_mps", r.get("speed_mps", 0.0))),
                    "max_speed_mps": float(r.get("max_speed_mps", 0.0)),
                    "min_distance": float(r.get("min_distance", 0.0)),
                    "mean_formation_error": float(r.get("mean_formation_error", 0.0)),
                    "mean_formation_iou": float(r.get("mean_formation_iou", 0.0)),
                    "std_formation_iou": float(r.get("std_formation_iou", 0.0)),
                    "mean_per_boat_rms_m": float(r.get("mean_per_boat_rms_m", 0.0)),
                    "std_per_boat_rms_m": float(r.get("std_per_boat_rms_m", 0.0)),
                    "mean_centroid_offset_m": float(r.get("mean_centroid_offset_m", 0.0)),
                    "std_centroid_offset_m": float(r.get("std_centroid_offset_m", 0.0)),
                    "near_miss_count": float(r.get("near_miss_count", 0.0)),
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


def plot_metric_grid(rows, out_base, formats=("png", "pdf", "svg")):
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
    for fmt in formats:
        out_path = f"{out_base}.{fmt}"
        fig.savefig(out_path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def plot_formation_error_vs_kalman(rows, out_base, formats=("png", "pdf", "svg")):
    side_colors = {"Left": "tab:blue", "Right": "tab:orange"}
    fig, ax = plt.subplots(figsize=(8, 5))

    for side in ["Left", "Right"]:
        subset = [r for r in rows if r["side"] == side]
        xs = [r["kalman_on_ratio"] for r in subset]
        ys = [r["mean_formation_error"] for r in subset]
        ax.scatter(xs, ys, alpha=0.7, s=35, c=side_colors[side], label=side)

    ax.set_xlabel("Kalman ON Ratio (0=OFF, 1=ON)")
    ax.set_ylabel("Formation Error (norm.)")
    ax.set_title("Formation Error vs Kalman Usage")
    ax.grid(alpha=0.3)
    ax.legend()
    fig.tight_layout()
    for fmt in formats:
        out_path = f"{out_base}.{fmt}"
        fig.savefig(out_path, dpi=220, bbox_inches="tight")
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
    parser.add_argument(
        "--formats",
        default="png,pdf,svg",
        help="Comma-separated output formats (png,pdf,svg)",
    )
    args = parser.parse_args()

    if not os.path.exists(args.input):
        raise FileNotFoundError(f"Input summary file not found: {args.input}")

    rows = read_summary_rows(args.input)
    if not rows:
        raise RuntimeError("No valid rows found in summary CSV.")

    os.makedirs(args.output_dir, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    fmt_list = [f.strip() for f in args.formats.split(",") if f.strip()]
    out_base_grid = os.path.join(args.output_dir, f"metrics_comparison_{stamp}")
    out_base_scatter = os.path.join(args.output_dir, f"formation_error_vs_kalman_{stamp}")

    plot_metric_grid(rows, out_base_grid, formats=fmt_list)
    plot_formation_error_vs_kalman(rows, out_base_scatter, formats=fmt_list)

    for fmt in fmt_list:
        print(f"Saved: {out_base_grid}.{fmt}")
        print(f"Saved: {out_base_scatter}.{fmt}")


if __name__ == "__main__":
    main()
