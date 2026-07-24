import argparse
import csv
import os
from datetime import datetime

import matplotlib.pyplot as plt
from matplotlib import rcParams


# Try to import config to respect runtime flags (hide follower detection if disabled)
try:
    import usv.config as config
except Exception:
    try:
        import config
    except Exception:
        config = None

METRICS = [
    ("leader_det_rate_pct", "Leader Detection Rate (%)"),
    ("stale_rate_pct", "Stale Rate (%)"),
    ("dsteer_mean_abs", "Steer Jerkiness (|ΔSteer|/sample)"),
    ("dthr_mean_abs", "Throttle Jerkiness (|ΔThrottle|/sample)"),
    ("mean_distance", "Mean Distance (a.u.)"),
    ("mean_formation_error", "Formation Error (norm.)"),
]

# Insert follower detection metric only when side/follower detection is enabled
if config is None or not hasattr(config, "ENABLE_SIDE_DETECTION") or getattr(config, "ENABLE_SIDE_DETECTION"):
    METRICS.insert(1, ("follower_det_rate_pct", "Follower Detection Rate (%)"))


# Publication defaults
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


def read_summaries(summary_csv):
    rows = []
    with open(summary_csv, "r", newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            rows.append(row)
    return rows


def extract_run(rows, run_id):
    # find Left and Right rows for run_id
    out = {}
    for r in rows:
        if r.get("run_id") == run_id:
            side = r.get("side")
            out[side] = r
    return out


def to_float(v):
    try:
        return float(v)
    except Exception:
        return 0.0


def plot_compare(run1_id, run2_id, rows, out_base, formats=("pdf", "svg", "png")):
    sides = ["Left", "Right"]

    run1 = extract_run(rows, run1_id)
    run2 = extract_run(rows, run2_id)

    fig, axes = plt.subplots(2, 3, figsize=(16, 9))
    axes = axes.flatten()

    for ax, (metric, title) in zip(axes, METRICS):
        vals1 = [to_float(run1.get(side, {}).get(metric, 0.0)) if side in run1 else to_float(run1.get(side, metric, 0.0)) for side in sides]
        vals2 = [to_float(run2.get(side, {}).get(metric, 0.0)) if side in run2 else to_float(run2.get(side, metric, 0.0)) for side in sides]

        x = [0, 1]
        width = 0.35
        ax.bar([xi - width / 2 for xi in x], vals1, width=width, label=f"{run1_id}")
        ax.bar([xi + width / 2 for xi in x], vals2, width=width, label=f"{run2_id}")
        ax.set_title(title)
        ax.set_xticks(x)
        ax.set_xticklabels(sides)
        ax.grid(axis="y", alpha=0.3)
        ax.legend()

    fig.suptitle(f"Compare runs: {run1_id} vs {run2_id}")
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    for fmt in formats:
        out_path = f"{out_base}.{fmt}"
        fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description="Compare two run summaries and produce publication figures")
    parser.add_argument("--run1", required=True, help="First run_id (from run_summaries.csv)")
    parser.add_argument("--run2", required=True, help="Second run_id (from run_summaries.csv)")
    parser.add_argument(
        "--summary",
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
        default="pdf,svg,png",
        help="Comma-separated output formats",
    )
    args = parser.parse_args()

    if not os.path.exists(args.summary):
        raise FileNotFoundError(f"Summary CSV not found: {args.summary}")

    rows = read_summaries(args.summary)
    os.makedirs(args.output_dir, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_base = os.path.join(args.output_dir, f"compare_{args.run1}_vs_{args.run2}_{stamp}")
    formats = [f.strip() for f in args.formats.split(",") if f.strip()]

    plot_compare(args.run1, args.run2, rows, out_base, formats=formats)
    for fmt in formats:
        print(f"Saved: {out_base}.{fmt}")


if __name__ == "__main__":
    main()
