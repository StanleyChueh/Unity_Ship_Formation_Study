"""
Overlay comparison: Kalman ON vs Kalman OFF on shared y-axes.

Both conditions are drawn on the SAME axes so y-scale differences cannot
mislead the viewer. A rolling-mean trend line is overlaid to make the
advantage immediately visible despite per-window noise.

Usage
-----
    python -m usv.plot_compare_snapshots \\
        --kalman-on  experiment_metrics/run_<ON_ID>_snapshots.csv  \\
        --kalman-off experiment_metrics/run_<OFF_ID>_snapshots.csv \\
        [--output-dir experiment_metrics/plots]                     \\
        [--formats pdf,png]                                         \\
        [--formation-scale 1.0]                                     \\
        [--smooth-window 6]
"""

import argparse
import math
import os
from datetime import datetime

import matplotlib.pyplot as plt
from matplotlib import rcParams

from usv.plot_snapshots import infer_kalman_mode, read_snapshots, recompute_scaled_iou

# ---------------------------------------------------------------------------
# Publication style
# ---------------------------------------------------------------------------
rcParams.update(
    {
        "font.family": "serif",
        "font.serif": ["Times New Roman", "DejaVu Serif"],
        "font.size": 10,
        "axes.titlesize": 11,
        "axes.labelsize": 10,
        "legend.fontsize": 8,
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
        "figure.dpi": 220,
    }
)

# ---------------------------------------------------------------------------
# Color palette
# ---------------------------------------------------------------------------
# Kalman ON: solid, vivid
C_ON_LEFT   = "#1565C0"   # deep blue
C_ON_RIGHT  = "#BF360C"   # deep red-orange
C_ON_FORM   = "#2E7D32"   # deep green (formation-level metrics)

# Kalman OFF: dashed, muted
C_OFF_LEFT  = "#90CAF9"   # light blue
C_OFF_RIGHT = "#FFAB91"   # light salmon
C_OFF_FORM  = "#A5D6A7"   # light green

# Trend (rolling mean) – same hue, stronger
C_ON_LEFT_TR  = "#0D47A1"
C_ON_RIGHT_TR = "#BF360C"
C_ON_FORM_TR  = "#1B5E20"
C_OFF_LEFT_TR = "#42A5F5"
C_OFF_RIGHT_TR= "#FF7043"
C_OFF_FORM_TR = "#66BB6A"


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------
def _side_rows(snapshots, side):
    return sorted(
        [r for r in snapshots if r.get("side") == side],
        key=lambda x: float(x.get("elapsed_s", 0.0)),
    )


def _xs(rows):
    return [float(r["elapsed_s"]) for r in rows]


def _get(rows, key):
    return [float(r.get(key, 0.0) or 0.0) for r in rows]


def _rolling_mean(vals, window):
    """Simple centered rolling mean; edges use available neighbors."""
    out = []
    hw = window // 2
    for i in range(len(vals)):
        lo = max(0, i - hw)
        hi = min(len(vals), i + hw + 1)
        chunk = [v for v in vals[lo:hi] if math.isfinite(v)]
        out.append(sum(chunk) / len(chunk) if chunk else 0.0)
    return out


def _shared_ylim(series_list, pad=0.10):
    all_vals = []
    for s in series_list:
        all_vals.extend([v for v in s if v is not None and math.isfinite(v)])
    if not all_vals:
        return 0.0, 1.0
    lo = min(0.0, min(all_vals))
    hi = max(all_vals)
    margin = (hi - lo) * pad
    return lo, hi + margin


def _pick_key(base_key, *snap_lists):
    """Use the _scaled variant if any snapshot has non-zero data for it."""
    scaled = base_key + "_scaled"
    for snaps in snap_lists:
        if any(r.get(scaled, 0.0) not in (0.0, None) for r in snaps):
            return scaled
    return base_key


# ---------------------------------------------------------------------------
# Main comparison plotter
# ---------------------------------------------------------------------------
def plot_comparison(
    on_snaps,
    off_snaps,
    on_label,
    off_label,
    out_base,
    formats,
    formation_scale=1.0,
    smooth_window=6,
):
    recompute_scaled_iou(on_snaps,  formation_scale=formation_scale)
    recompute_scaled_iou(off_snaps, formation_scale=formation_scale)

    on_left   = _side_rows(on_snaps,  "Left")
    on_right  = _side_rows(on_snaps,  "Right")
    off_left  = _side_rows(off_snaps, "Left")
    off_right = _side_rows(off_snaps, "Right")

    all_on  = on_snaps
    all_off = off_snaps

    iou_key  = _pick_key("formation_iou",       all_on, all_off)
    pos_key  = _pick_key("pos_error_m",          all_on, all_off)
    rms_key  = _pick_key("per_boat_rms_m",       all_on, all_off)
    cent_key = _pick_key("centroid_offset_m",    all_on, all_off)
    ferr_key = _pick_key("mean_formation_error", all_on, all_off)

    # (key, title, ylabel, higher_is_better, formation_level)
    # formation_level=True → one line per condition; False → per-side (L+R)
    metrics = [
        (iou_key,           "Formation IoU",           "IoU (0..1)",                       True,  True),
        (pos_key,           "Follower Position Error",  "Position Error (m)",               False, False),
        (ferr_key,          "Formation Area Error",     "Area Error (ratio)",               False, True),
        (cent_key,          "Centroid Offset",          "Centroid Offset (m)",              False, True),
        (rms_key,           "Per-Boat Position RMS",    "RMS Error (m)",                   False, True),
        ("dsteer_mean_abs", "Steer Jerkiness",          "|ΔSteer| per sample",             False, False),
        ("dthr_mean_abs",   "Throttle Jerkiness",       "|ΔThrottle| per sample",          False, False),
        ("speed_mps",       "Measured Speed",           "Speed (m/s)",                     None,  False),
    ]

    ncols = 2
    nrows = math.ceil(len(metrics) / ncols)
    fig, axes = plt.subplots(nrows, ncols, figsize=(14, 4.2 * nrows))
    try:
        ax_list = axes.flatten()
    except AttributeError:
        ax_list = [axes]

    w = max(3, smooth_window)

    for idx, (key, title, ylabel, higher_is_better, form_level) in enumerate(metrics):
        ax = ax_list[idx]

        if form_level:
            # Formation-level: one representative series per condition
            # prefer Left rows; fall back to Right if Left is empty
            src_on  = on_left  if on_left  else on_right
            src_off = off_left if off_left else off_right

            ys_on  = _get(src_on,  key)
            ys_off = _get(src_off, key)
            xs_on  = _xs(src_on)
            xs_off = _xs(src_off)

            lo, hi = _shared_ylim([ys_on, ys_off])
            ax.set_ylim(lo, hi)

            # raw data (thin, transparent)
            ax.plot(xs_off, ys_off, color=C_OFF_FORM,   lw=0.8, alpha=0.35, linestyle="--")
            ax.plot(xs_on,  ys_on,  color=C_ON_FORM,    lw=0.8, alpha=0.35)

            # trend (thick, opaque)
            ax.plot(xs_off, _rolling_mean(ys_off, w), color=C_OFF_FORM_TR, lw=2.0,
                    linestyle="--", label=f"KF OFF (trend)")
            ax.plot(xs_on,  _rolling_mean(ys_on,  w), color=C_ON_FORM_TR,  lw=2.2,
                    label=f"KF ON (trend)")

        else:
            ys_on_l  = _get(on_left,   key)
            ys_on_r  = _get(on_right,  key)
            ys_off_l = _get(off_left,  key)
            ys_off_r = _get(off_right, key)
            xs_on_l  = _xs(on_left)
            xs_on_r  = _xs(on_right)
            xs_off_l = _xs(off_left)
            xs_off_r = _xs(off_right)

            lo, hi = _shared_ylim([ys_on_l, ys_on_r, ys_off_l, ys_off_r])
            ax.set_ylim(lo, hi)

            # raw data
            ax.plot(xs_off_l, ys_off_l, color=C_OFF_LEFT,  lw=0.8, alpha=0.30, linestyle="--")
            ax.plot(xs_off_r, ys_off_r, color=C_OFF_RIGHT, lw=0.8, alpha=0.30, linestyle="--")
            ax.plot(xs_on_l,  ys_on_l,  color=C_ON_LEFT,   lw=0.8, alpha=0.35)
            ax.plot(xs_on_r,  ys_on_r,  color=C_ON_RIGHT,  lw=0.8, alpha=0.35)

            # trend
            ax.plot(xs_off_l, _rolling_mean(ys_off_l, w), color=C_OFF_LEFT_TR,  lw=1.8,
                    linestyle="--", label="KF OFF Left (trend)")
            ax.plot(xs_off_r, _rolling_mean(ys_off_r, w), color=C_OFF_RIGHT_TR, lw=1.8,
                    linestyle="--", label="KF OFF Right (trend)")
            ax.plot(xs_on_l,  _rolling_mean(ys_on_l,  w), color=C_ON_LEFT_TR,   lw=2.2,
                    label="KF ON Left (trend)")
            ax.plot(xs_on_r,  _rolling_mean(ys_on_r,  w), color=C_ON_RIGHT_TR,  lw=2.2,
                    label="KF ON Right (trend)")

        # "Better" badge
        if higher_is_better is True:
            badge = "KF ON: ↑ higher = better"
            badge_color = "#1B5E20"
        elif higher_is_better is False:
            badge = "KF ON: ↓ lower = better"
            badge_color = "#B71C1C"
        else:
            badge = None

        if badge:
            ax.text(
                0.98, 0.96, badge,
                transform=ax.transAxes, ha="right", va="top",
                fontsize=7.5, color=badge_color, fontstyle="italic",
                bbox=dict(boxstyle="round,pad=0.25", facecolor="white", edgecolor=badge_color, alpha=0.85),
            )

        ax.set_xlabel("Elapsed Time (s)")
        ax.set_ylabel(ylabel)
        ax.set_title(title, fontweight="bold")
        ax.grid(alpha=0.22, linestyle=":")
        ax.legend(fontsize=7.5, loc="upper left", framealpha=0.85)

    # Hide unused subplots
    for i in range(len(metrics), len(ax_list)):
        try:
            ax_list[i].set_visible(False)
        except Exception:
            pass

    fig.suptitle(
        "Kalman Filter ON vs OFF — Performance Comparison\n"
        f"KF ON: {on_label}     KF OFF: {off_label}",
        fontsize=11,
        fontweight="bold",
        y=1.01,
    )
    fig.tight_layout()

    for fmt in formats:
        out_path = f"{out_base}.{fmt}"
        fig.savefig(out_path, bbox_inches="tight")
        print(f"Saved: {out_path}")
    plt.close(fig)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Overlay comparison: Kalman ON vs OFF on shared y-axes."
    )
    parser.add_argument("--kalman-on",  required=True, help="Snapshot CSV for Kalman ON run")
    parser.add_argument("--kalman-off", required=True, help="Snapshot CSV for Kalman OFF run")
    parser.add_argument(
        "--output-dir",
        default=os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "experiment_metrics", "plots")
        ),
    )
    parser.add_argument("--formats", default="pdf,svg,png")
    parser.add_argument("--formation-scale", default=1.0, type=float,
                        help="Scale applied to target triangle side when recomputing IoU.")
    parser.add_argument("--smooth-window", default=6, type=int,
                        help="Rolling-mean window size (number of snapshot rows).")
    args = parser.parse_args()

    for path in (args.kalman_on, args.kalman_off):
        if not os.path.exists(path):
            raise FileNotFoundError(f"Snapshot CSV not found: {path}")

    on_snaps  = read_snapshots(args.kalman_on)
    off_snaps = read_snapshots(args.kalman_off)

    if not on_snaps:
        raise RuntimeError(f"No valid rows in {args.kalman_on}")
    if not off_snaps:
        raise RuntimeError(f"No valid rows in {args.kalman_off}")

    on_label,  _ = infer_kalman_mode(args.kalman_on,  on_snaps)
    off_label, _ = infer_kalman_mode(args.kalman_off, off_snaps)

    # Extract compact run IDs from filenames
    def _run_id(path):
        return os.path.basename(path).replace("run_", "").replace("_snapshots.csv", "")

    on_id  = _run_id(args.kalman_on)
    off_id = _run_id(args.kalman_off)

    os.makedirs(args.output_dir, exist_ok=True)
    stamp    = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_base = os.path.join(args.output_dir, f"compare_on_{on_id}_off_{off_id}_{stamp}")
    formats  = [f.strip() for f in args.formats.split(",") if f.strip()]

    plot_comparison(
        on_snaps,
        off_snaps,
        on_label=f"{on_id} ({on_label})",
        off_label=f"{off_id} ({off_label})",
        out_base=out_base,
        formats=formats,
        formation_scale=args.formation_scale,
        smooth_window=args.smooth_window,
    )


if __name__ == "__main__":
    main()
