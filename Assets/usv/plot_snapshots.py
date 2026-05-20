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
                    "mean_distance": float(row.get("mean_distance", 0.0)),
                    "min_distance": float(row.get("min_distance", 0.0)),
                    "mean_formation_error": float(row.get("mean_formation_error", 0.0)),
                    "near_miss_count": int(row.get("near_miss_count", 0)),
                }
                rows.append(row_parsed)
            except Exception:
                continue
    return rows


def plot_snapshots(snapshots, run_id, out_base, formats=("pdf", "svg", "png")):
    """Create a 2x3 grid of time-series plots for Left/Right sides."""
    fig, axes = plt.subplots(2, 3, figsize=(14, 8))
    
    # Group rows by side
    left_rows = [r for r in snapshots if r["side"] == "Left"]
    right_rows = [r for r in snapshots if r["side"] == "Right"]
    
    metrics = [
        ("leader_det_rate_pct", "Leader Detection Rate", "Detection Rate (%)"),
        ("follower_det_rate_pct", "Follower Detection Rate", "Detection Rate (%)"),
        ("mean_distance", "Mean Distance", "Mean Distance (a.u.)"),
        ("mean_formation_error", "Formation Error", "Formation Error (norm.)"),
        ("dsteer_mean_abs", "Steer Jerkiness", "Steer Jerkiness (|ΔSteer|/sample)"),
        ("dthr_mean_abs", "Throttle Jerkiness", "Throttle Jerkiness (|ΔThrottle|/sample)"),
    ]
    
    for idx, (metric, title, ylabel) in enumerate(metrics):
        ax = axes.flatten()[idx]
        
        # Plot Left side
        if left_rows:
            xs_left = [r["elapsed_s"] for r in left_rows]
            ys_left = [r[metric] for r in left_rows]
            ax.plot(xs_left, ys_left, "o-", label="Left", alpha=0.7, markersize=4)
        
        # Plot Right side
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
    args = parser.parse_args()
    
    if not os.path.exists(args.snapshot):
        raise FileNotFoundError(f"Snapshot file not found: {args.snapshot}")
    
    snapshots = read_snapshots(args.snapshot)
    if not snapshots:
        raise RuntimeError("No valid rows found in snapshot CSV.")
    
    os.makedirs(args.output_dir, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Extract run_id from filename
    basename = os.path.basename(args.snapshot)  # e.g., run_20260520_093039_snapshots.csv
    run_id = basename.replace("run_", "").replace("_snapshots.csv", "")
    
    out_base = os.path.join(args.output_dir, f"snapshots_{run_id}_{stamp}")
    formats = [f.strip() for f in args.formats.split(",") if f.strip()]
    
    plot_snapshots(snapshots, run_id, out_base, formats=formats)
    for fmt in formats:
        print(f"Saved: {out_base}.{fmt}")


if __name__ == "__main__":
    main()
