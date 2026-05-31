"""
Plot within-run time-series metrics from snapshot CSV.
Useful for detailed temporal analysis and identifying transient behaviors.
"""

import argparse
import csv
import os
from datetime import datetime

import matplotlib.pyplot as plt
from matplotlib import rcParams


# Publication defaults
rcParams.update(
    {
        "font.family": "serif",
        "font.serif": ["Times New Roman", "DejaVu Serif"],
        "font.size": 10,
        "axes.titlesize": 11,
        "axes.labelsize": 10,
        "legend.fontsize": 9,
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
        "figure.dpi": 220,
    }
)


def read_snapshots(snapshots_csv):
    """Read snapshot CSV and return list of dicts."""
    rows = []
    with open(snapshots_csv, "r", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                row_parsed = {
                    "elapsed_s": float(row.get("elapsed_s", 0.0)),
                    "kalman_enabled": int(row.get("kalman_enabled", 0)),
                    "side": row.get("side", ""),
                    "leader_det_rate_pct": float(row.get("leader_det_rate_pct", row.get("det_rate_pct", 0.0))),
                    "follower_det_rate_pct": float(row.get("follower_det_rate_pct", 0.0)),
                    "stale_rate_pct": float(row.get("stale_rate_pct", 0.0)),
                    "dsteer_mean_abs": float(row.get("dsteer_mean_abs", 0.0)),
                    "dthr_mean_abs": float(row.get("dthr_mean_abs", 0.0)),
                    "steer_cmd_mean": float(row.get("steer_cmd_mean", row.get("last_steer", row.get("steer", 0.0)))),
                    "steer_cmd_min": float(row.get("steer_cmd_min", row.get("steer_cmd_min", 0.0))),
                    "steer_cmd_max": float(row.get("steer_cmd_max", row.get("steer_cmd_max", 0.0))),
                    "steer_cmd_mean_abs": float(row.get("steer_cmd_mean_abs", 0.0)),
                    "throttle_cmd_mean": float(row.get("throttle_cmd_mean", row.get("last_throttle", row.get("throttle", 0.0)))),
                    "throttle_cmd_min": float(row.get("throttle_cmd_min", row.get("throttle_cmd_min", 0.0))),
                    "throttle_cmd_max": float(row.get("throttle_cmd_max", row.get("throttle_cmd_max", 0.0))),
                    "throttle_cmd_mean_abs": float(row.get("throttle_cmd_mean_abs", 0.0)),
                    "mean_distance": float(row.get("mean_distance", 0.0)),
                    "min_distance": float(row.get("min_distance", 0.0)),
                    "distance_error_mean": float(row.get("distance_error_mean", row.get("mean_distance", 0.0))),
                    "mean_formation_error": float(row.get("mean_formation_error", 0.0)),
                    "pred_mae": float(row.get("pred_mae", 0.0)),
                    "pred_flips": float(row.get("pred_flips", 0.0)),
                    "near_miss_count": int(row.get("near_miss_count", 0)),
                }
                rows.append(row_parsed)
            except Exception:
                continue
    return rows


def infer_kalman_mode(snapshot_path, snapshots):
    """Infer the Kalman-filter mode for a snapshot run.

    Filename hints take precedence when present so runs can be identified even
    when the snapshot rows come from a mixed or partial capture.
    """
    basename = os.path.basename(snapshot_path).lower()
    if "without_kalman" in basename:
        return "Kalman OFF", "kalman_off"
    if "with_kalman" in basename:
        return "Kalman ON", "kalman_on"

    kalman_values = [int(row.get("kalman_enabled", 0)) for row in snapshots]
    if not kalman_values:
        return "Kalman mode unknown", "kalman_unknown"

    enabled_count = sum(1 for value in kalman_values if value)
    disabled_count = len(kalman_values) - enabled_count
    if enabled_count == 0:
        return "Kalman OFF", "kalman_off"
    if disabled_count == 0:
        return "Kalman ON", "kalman_on"
    if enabled_count >= disabled_count:
        return "Kalman ON (majority)", "kalman_on_majority"
    return "Kalman OFF (majority)", "kalman_off_majority"


def plot_snapshots(snapshots, run_id, out_base, formats=("pdf", "svg", "png"), command_detail="simple"):
    """Create a 2x3 grid of time-series plots for Left/Right sides."""
    # Expand to 3x3 to include raw control commands and the core tracking metrics
    fig, axes = plt.subplots(3, 3, figsize=(14, 12))
    
    # Group rows by side
    left_rows = [r for r in snapshots if r["side"] == "Left"]
    right_rows = [r for r in snapshots if r["side"] == "Right"]
    
    metrics = [
        ("leader_det_rate_pct", "Leader Detection Rate", "Detection Rate (%)"),
        ("follower_det_rate_pct", "Follower Detection Rate", "Detection Rate (%)"),
        ("distance_error_mean", "Distance Error vs Target", "Distance Error (a.u.)"),
        ("mean_formation_error", "Formation Error", "Formation Error (norm.)"),
        ("dsteer_mean_abs", "Steer Jerkiness", "Steer Jerkiness (|ΔSteer|/sample)"),
        ("dthr_mean_abs", "Throttle Jerkiness", "Throttle Jerkiness (|ΔThrottle|/sample)"),
        ("steer_cmd_mean", "Steer Command", "Command"),
        ("throttle_cmd_mean", "Throttle Command", "Command"),
    ]
    
    for idx, (metric, title, ylabel) in enumerate(metrics):
        ax = axes.flatten()[idx]
        
        # Optional detailed handling for command metrics (min/max band + mean-abs)
        if metric in ("steer_cmd_mean", "throttle_cmd_mean") and command_detail == "band":
            key_base = metric.replace("_mean", "")

            # Left
            if left_rows:
                xs_left = [r["elapsed_s"] for r in left_rows]
                ys_left_mean = [r[metric] for r in left_rows]
                ys_left_min = [r.get(f"{key_base}_min", 0.0) for r in left_rows]
                ys_left_max = [r.get(f"{key_base}_max", 0.0) for r in left_rows]
                ys_left_abs = [r.get(f"{key_base}_mean_abs", 0.0) for r in left_rows]
                ax.plot(xs_left, ys_left_mean, "o-", label="Left mean", alpha=0.8, markersize=4)
                ax.fill_between(xs_left, ys_left_min, ys_left_max, color="C0", alpha=0.15)
                ax.plot(xs_left, ys_left_abs, "--", color="C0", label="Left mean-abs", alpha=0.8)

            # Right
            if right_rows:
                xs_right = [r["elapsed_s"] for r in right_rows]
                ys_right_mean = [r[metric] for r in right_rows]
                ys_right_min = [r.get(f"{key_base}_min", 0.0) for r in right_rows]
                ys_right_max = [r.get(f"{key_base}_max", 0.0) for r in right_rows]
                ys_right_abs = [r.get(f"{key_base}_mean_abs", 0.0) for r in right_rows]
                ax.plot(xs_right, ys_right_mean, "s-", label="Right mean", alpha=0.8, markersize=4)
                ax.fill_between(xs_right, ys_right_min, ys_right_max, color="C1", alpha=0.12)
                ax.plot(xs_right, ys_right_abs, "--", color="C1", label="Right mean-abs", alpha=0.8)

        else:
            # Plot generic metric for Left/Right
            if left_rows:
                xs_left = [r["elapsed_s"] for r in left_rows]
                ys_left = [r[metric] for r in left_rows]
                ax.plot(xs_left, ys_left, "o-", label="Left", alpha=0.7, markersize=4)
            if right_rows:
                xs_right = [r["elapsed_s"] for r in right_rows]
                ys_right = [r[metric] for r in right_rows]
                ax.plot(xs_right, ys_right, "s-", label="Right", alpha=0.7, markersize=4)
        
        ax.set_xlabel("Elapsed Time (s)")
        ax.set_ylabel(ylabel)
        ax.set_title(title)
        ax.grid(alpha=0.3)
        if idx == 0:
            ax.legend()

    # If there are empty subplots (3x3 grid but only 8 metrics), hide them
    total_plots = 3 * 3
    for i in range(len(metrics), total_plots):
        axes.flatten()[i].set_visible(False)
    
    fig.suptitle(f"Time-Series Metrics: {run_id}")
    fig.tight_layout()
    
    for fmt in formats:
        out_path = f"{out_base}.{fmt}"
        fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description="Plot time-series metrics from snapshot CSV")
    parser.add_argument(
        "--snapshot",
        required=True,
        help="Path to run_<RUN_ID>_snapshots.csv",
    )
    parser.add_argument(
        "--output-dir",
        default=os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "experiment_metrics", "plots")),
        help="Directory to save figures",
    )
    parser.add_argument(
        "--formats",
        default="pdf,svg,png",
        help="Comma-separated output formats",
    )
    parser.add_argument(
        "--command-detail",
        default="simple",
        choices=["simple", "band"],
        help="Command subplot style: simple=Left/Right mean only, band=mean + min/max band + mean-abs",
    )
    args = parser.parse_args()
    
    if not os.path.exists(args.snapshot):
        raise FileNotFoundError(f"Snapshot file not found: {args.snapshot}")
    
    snapshots = read_snapshots(args.snapshot)
    if not snapshots:
        raise RuntimeError("No valid rows found in snapshot CSV.")

    kalman_mode_label, kalman_mode_slug = infer_kalman_mode(args.snapshot, snapshots)
    
    os.makedirs(args.output_dir, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Extract run_id from filename
    basename = os.path.basename(args.snapshot)  # e.g., run_20260520_093039_snapshots.csv
    run_id = basename.replace("run_", "").replace("_snapshots.csv", "")
    
    out_base = os.path.join(args.output_dir, f"snapshots_{kalman_mode_slug}_{run_id}_{stamp}")
    formats = [f.strip() for f in args.formats.split(",") if f.strip()]
    
    plot_snapshots(
        snapshots,
        f"{run_id} · {kalman_mode_label}",
        out_base,
        formats=formats,
        command_detail=args.command_detail,
    )
    for fmt in formats:
        print(f"Saved: {out_base}.{fmt}")


if __name__ == "__main__":
    main()
