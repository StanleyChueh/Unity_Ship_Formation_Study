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
import math

from usv.formation_geometry import build_ideal_formation_points

# Try to import project config to respect runtime flags when plotting.
# Support running this module either as a package or standalone script.
try:
    import usv.config as config
except Exception:
    try:
        import config
    except Exception:
        config = None


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
                def _opt_float(key):
                    v = row.get(key, None)
                    if v is None or v == "":
                        return None
                    try:
                        return float(v)
                    except Exception:
                        return None

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
                    "formation_iou": float(row.get("formation_iou", 0.0)),
                    "formation_area_err": float(row.get("formation_area_err", 0.0)),
                    "pos_error_m": float(row.get("pos_error_m", 0.0)),
                    "centroid_offset_m": float(row.get("centroid_offset_m", 0.0)),
                    "per_boat_rms_m": float(row.get("per_boat_rms_m", 0.0)),
                    "pred_mae": float(row.get("pred_mae", 0.0)),
                    "pred_flips": float(row.get("pred_flips", 0.0)),
                    "near_miss_count": int(row.get("near_miss_count", 0)),
                    "speed_mps": float(row.get("speed_mps", row.get("speed_mean", 0.0))),
                    "leader_speed_mps": float(row.get("leader_speed_mps", row.get("leader_speed_mean", 0.0))),
                    "x_m": _opt_float("x_m"),
                    "z_m": _opt_float("z_m"),
                    "leader_x_m": _opt_float("leader_x_m"),
                    "leader_z_m": _opt_float("leader_z_m"),
                    "leader_yaw": _opt_float("leader_yaw"),
                    "formation_iou_scaled": _opt_float("formation_iou_scaled") or 0.0,
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


def plot_snapshots(snapshots, run_id, out_base, formats=("pdf", "svg", "png"), command_detail="simple", formation_scale=1.0):
    """Create a grid of time-series plots for Left/Right sides."""
    
    # Recompute any scaled formation metrics and then group rows by side
    try:
        recompute_scaled_iou(snapshots, formation_scale=formation_scale)
    except Exception:
        # non-fatal: if recompute fails, continue without scaled IoU
        pass

    left_rows = [r for r in snapshots if r["side"] == "Left"]
    right_rows = [r for r in snapshots if r["side"] == "Right"]
    
    # Build metrics list and respect config flags (e.g. hide follower detection if disabled).
    metrics = [
        ("leader_det_rate_pct", "Leader Detection Rate", "Detection Rate (%)"),
    ]

    # Only include follower detection subplot if side/follower detection is enabled
    enable_follower_plot = True
    if config is not None:
        # If ENABLE_SIDE_DETECTION is present and False, skip follower plot
        if hasattr(config, "ENABLE_SIDE_DETECTION") and not getattr(config, "ENABLE_SIDE_DETECTION"):
            enable_follower_plot = False

    if enable_follower_plot:
        metrics.append(("follower_det_rate_pct", "Follower Detection Rate", "Detection Rate (%)"))

    # For formation-related metrics, prefer the world-space recomputed "_scaled"
    # variants (from recompute_scaled_iou) over the pixel-proxy CSV values.
    # The _scaled versions use actual x/z coordinates and are in real meters.
    all_rows = left_rows + right_rows
    def _prefer_scaled(base_key):
        """Return scaled key if any row has a non-zero recomputed value, else base key."""
        scaled = base_key + "_scaled"
        if any(r.get(scaled, 0.0) not in (0.0, None) for r in all_rows):
            return scaled
        return base_key

    iou_key   = _prefer_scaled("formation_iou")
    pos_key   = _prefer_scaled("pos_error_m")
    rms_key   = _prefer_scaled("per_boat_rms_m")
    cent_key  = _prefer_scaled("centroid_offset_m")
    # distance_error_mean_scaled = mean(pos_err_left, pos_err_right) in metres;
    # the raw distance_error_mean is an inverse-area proxy in pixel² units.
    dist_key  = _prefer_scaled("distance_error_mean")
    dist_ylabel = "Mean Follower-to-Target Error (m)" if dist_key.endswith("_scaled") else "Distance Error (a.u.)"
    ferr_key  = _prefer_scaled("mean_formation_error")
    ferr_ylabel = "Formation Area Error (ratio)" if ferr_key.endswith("_scaled") else "Formation Error (norm.)"

    iou_title  = "Formation IoU"
    if formation_scale != 1.0 and iou_key.endswith("_scaled"):
        iou_title = f"Formation IoU (scale={formation_scale}x)"

    metrics += [
        (iou_key,  iou_title,                    "IoU (0..1)"),
        (pos_key,  "Follower Pos Error",          "Pos Error (m)"),
        (rms_key,  "Per-Boat Position RMS",       "RMS Error (m)"),
        (cent_key, "Centroid Offset",             "Offset (m)"),
        (dist_key, "Mean Follower Error",         dist_ylabel),
        (ferr_key, "Formation Area Error",        ferr_ylabel),
        ("dsteer_mean_abs",  "Steer Jerkiness",    "Steer Jerkiness (|ΔSteer|/sample)"),
        ("dthr_mean_abs",    "Throttle Jerkiness", "Throttle Jerkiness (|ΔThrottle|/sample)"),
        ("speed_mps",        "Measured Speed",     "Speed (m/s)"),
        # Command plots: normalized control signals (unitless)
        ("steer_cmd_mean",    "Steer Command",    "Command (normalized)"),
        ("throttle_cmd_mean", "Throttle Command", "Command (normalized)"),
    ]
    
    # dynamic grid: 3 columns, compute rows from metric count
    n_metrics = len(metrics)
    ncols = 3
    nrows = max(1, math.ceil(n_metrics / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(14, 4 * nrows))

    # flatten axes safely (handles single-axis returns)
    try:
        ax_list = axes.flatten()
    except Exception:
        ax_list = [axes]

    for idx, (metric, title, ylabel) in enumerate(metrics):
        ax = ax_list[idx]

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
                ys_left = [r.get(metric, 0.0) for r in left_rows]
                ax.plot(xs_left, ys_left, "o-", label="Left", alpha=0.7, markersize=4)
            if right_rows:
                xs_right = [r["elapsed_s"] for r in right_rows]
                ys_right = [r.get(metric, 0.0) for r in right_rows]
                ax.plot(xs_right, ys_right, "s-", label="Right", alpha=0.7, markersize=4)
        
        ax.set_xlabel("Elapsed Time (s)")
        ax.set_ylabel(ylabel)
        ax.set_title(title)
        ax.grid(alpha=0.3)
        ax.legend(fontsize=8)

    # Hide any unused subplots
    total_plots = nrows * ncols
    for i in range(len(metrics), total_plots):
        try:
            ax_list[i].set_visible(False)
        except Exception:
            pass
    
    fig.suptitle(f"Time-Series Metrics: {run_id}")
    fig.tight_layout()
    
    for fmt in formats:
        out_path = f"{out_base}.{fmt}"
        fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)


    # ------------------ Helper: recompute scaled IoU from world coords ------------------
def _tri_area(pts):
    (x1, y1), (x2, y2), (x3, y3) = pts
    return abs((x1*(y2-y3) + x2*(y3-y1) + x3*(y1-y2)) * 0.5)


def _poly_area(poly):
    if not poly:
        return 0.0
    area = 0.0
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        area += x1 * y2 - x2 * y1
    return abs(area) * 0.5


def _inside(p, a, b):
    (x, y) = p
    (x1, y1) = a
    (x2, y2) = b
    return ((x2 - x1) * (y - y1) - (y2 - y1) * (x - x1)) >= -1e-9


def _compute_line_intersection(a, b, p, q):
    x1, y1 = a
    x2, y2 = b
    x3, y3 = p
    x4, y4 = q
    denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(denom) < 1e-12:
        return None
    px = ((x1*y2 - y1*x2)*(x3 - x4) - (x1 - x2)*(x3*y4 - y3*x4)) / denom
    py = ((x1*y2 - y1*x2)*(y3 - y4) - (y1 - y2)*(x3*y4 - y3*x4)) / denom
    return (px, py)


def _sutherland_hodgman(subject, clipper):
    output = subject[:]
    for i in range(len(clipper)):
        input_list = output
        output = []
        A = clipper[i]
        B = clipper[(i + 1) % len(clipper)]
        if not input_list:
            break
        S = input_list[-1]
        for E in input_list:
            if _inside(E, A, B):
                if not _inside(S, A, B):
                    inter = _compute_line_intersection(S, E, A, B)
                    if inter is not None:
                        output.append(inter)
                output.append(E)
            elif _inside(S, A, B):
                inter = _compute_line_intersection(S, E, A, B)
                if inter is not None:
                    output.append(inter)
            S = E
    return output


def _polygon_intersection_area(poly_a, poly_b):
    if not poly_a or not poly_b:
        return 0.0
    inter_poly = _sutherland_hodgman(poly_a, poly_b)
    return _poly_area(inter_poly)


def recompute_scaled_iou(snapshots, formation_scale=1.0):
    # Build time-sorted lists for Left/Right and pair by nearest timestamp
    left_rows = sorted([r for r in snapshots if r.get("side") == "Left"], key=lambda x: float(x.get("elapsed_s", 0.0)))
    right_rows = sorted([r for r in snapshots if r.get("side") == "Right"], key=lambda x: float(x.get("elapsed_s", 0.0)))
    i = 0
    j = 0
    tol = 0.05  # seconds tolerance for pairing timestamps
    prev_leader_pos = None
    while i < len(left_rows) and j < len(right_rows):
        L = left_rows[i]
        R = right_rows[j]
        tl = float(L.get("elapsed_s", 0.0))
        tr = float(R.get("elapsed_s", 0.0))
        dt = tl - tr
        if abs(dt) <= tol:
            # paired rows
            pair_left = L
            pair_right = R
            i += 1
            j += 1
        else:
            # advance the earlier time to try to find a close match
            if dt < 0:
                i += 1
                continue
            else:
                j += 1
                continue
        # need leader coordinates
        leader_x = pair_left.get("leader_x_m") if pair_left.get("leader_x_m") is not None else pair_right.get("leader_x_m")
        leader_z = pair_left.get("leader_z_m") if pair_left.get("leader_z_m") is not None else pair_right.get("leader_z_m")
        if leader_x is None or leader_z is None:
            # skip if no world coords present
            pair_left["formation_iou_scaled"] = 0.0
            pair_right["formation_iou_scaled"] = 0.0
            continue
        A = (float(leader_x), float(leader_z))
        B = (float(pair_left.get("x_m", 0.0)), float(pair_left.get("z_m", 0.0)))
        C = (float(pair_right.get("x_m", 0.0)), float(pair_right.get("z_m", 0.0)))

        actual_area = _tri_area([A, B, C])

        # scale target triangle side
        base_side = None
        try:
            base_side = float(config.LEADER_TRAJECTORY_TRIANGLE_SIDE)
        except Exception:
            base_side = 1.0
        s = base_side * float(formation_scale)
        leader_yaw = float(pair_left.get("leader_yaw", 0.0) or pair_right.get("leader_yaw", 0.0) or 0.0)
        motion_dx = None
        motion_dz = None
        if prev_leader_pos is not None:
            motion_dx = A[0] - prev_leader_pos[0]
            motion_dz = A[1] - prev_leader_pos[1]
        target_pts, _ = build_ideal_formation_points(
            leader_x=A[0],
            leader_z=A[1],
            side_length=s,
            motion_dx=motion_dx,
            motion_dz=motion_dz,
            leader_yaw_deg=leader_yaw,
        )
        prev_leader_pos = A
        target_area = _tri_area(target_pts)
        inter_area = _polygon_intersection_area([A, B, C], target_pts)
        union_area = actual_area + target_area - inter_area if (actual_area + target_area - inter_area) > 1e-12 else 0.0
        iou = (inter_area / union_area) if union_area > 1e-12 else 0.0

        # per-side position error (map Left->left vertex, Right->right vertex)
        target_left = target_pts[1]
        target_right = target_pts[2]
        def _dist(u, v):
            return math.hypot(u[0]-v[0], u[1]-v[1])

        pos_err_left = _dist(B, target_left)
        pos_err_right = _dist(C, target_right)
        mean_pos_err = 0.5 * (pos_err_left + pos_err_right)

        per_boat_rms = math.sqrt(0.5 * (pos_err_left**2 + pos_err_right**2))

        centroid_actual = ((A[0]+B[0]+C[0]) / 3.0, (A[1]+B[1]+C[1]) / 3.0)
        centroid_target = ((target_pts[0][0]+target_pts[1][0]+target_pts[2][0]) / 3.0,
                           (target_pts[0][1]+target_pts[1][1]+target_pts[2][1]) / 3.0)
        centroid_offset = _dist(centroid_actual, centroid_target)

        formation_area_err = abs(actual_area - target_area) / target_area if target_area > 1e-12 else 0.0

        # write scaled metrics back into both side rows so plotting code can use them per-side
        pair_left["formation_iou_scaled"] = iou
        pair_right["formation_iou_scaled"] = iou
        pair_left["pos_error_m_scaled"] = pos_err_left
        pair_right["pos_error_m_scaled"] = pos_err_right
        pair_left["per_boat_rms_m_scaled"] = per_boat_rms
        pair_right["per_boat_rms_m_scaled"] = per_boat_rms
        pair_left["centroid_offset_m_scaled"] = centroid_offset
        pair_right["centroid_offset_m_scaled"] = centroid_offset
        pair_left["distance_error_mean_scaled"] = mean_pos_err
        pair_right["distance_error_mean_scaled"] = mean_pos_err
        pair_left["mean_formation_error_scaled"] = formation_area_err
        pair_right["mean_formation_error_scaled"] = formation_area_err
    # end while



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
        "--formation-scale",
        default=1.0,
        type=float,
        help="Scale factor to apply to the target formation when recomputing IoU (post-hoc).",
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
        formation_scale=args.formation_scale,
    )
    for fmt in formats:
        print(f"Saved: {out_base}.{fmt}")


if __name__ == "__main__":
    main()
