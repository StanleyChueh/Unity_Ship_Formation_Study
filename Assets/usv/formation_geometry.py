"""
Utilities for constructing the ideal follower formation in world coordinates.
"""

import math


def _normalize_planar(x, z, eps=1e-6):
    if x is None or z is None:
        return None
    mag = math.hypot(float(x), float(z))
    if mag <= eps:
        return None
    return (float(x) / mag, float(z) / mag)


def planar_forward_from_yaw_deg(yaw_deg):
    """Convert a Unity-style yaw (0 deg = +z) to a planar forward vector."""
    if yaw_deg is None:
        return None
    ry = math.radians(float(yaw_deg))
    return _normalize_planar(math.sin(ry), math.cos(ry))


def resolve_leader_forward(
    leader_forward_x=None,
    leader_forward_z=None,
    motion_dx=None,
    motion_dz=None,
    leader_yaw_deg=None,
    min_motion=1e-3,
):
    """Resolve the best available leader heading in the world x/z plane.

    Preference order:
    1. Recent motion tangent, so the ideal formation follows the trajectory.
    2. Explicit forward vector reported by Unity.
    3. Raw yaw as a last-resort fallback.
    """
    if motion_dx is not None and motion_dz is not None:
        motion_mag = math.hypot(float(motion_dx), float(motion_dz))
        if motion_mag >= float(min_motion):
            forward = _normalize_planar(motion_dx, motion_dz)
            if forward is not None:
                return forward, "motion"

    forward = _normalize_planar(leader_forward_x, leader_forward_z)
    if forward is not None:
        return forward, "unity_forward"

    forward = planar_forward_from_yaw_deg(leader_yaw_deg)
    if forward is not None:
        return forward, "yaw"

    return (0.0, 1.0), "default"


def build_ideal_formation_points(
    leader_x,
    leader_z,
    side_length,
    leader_forward_x=None,
    leader_forward_z=None,
    motion_dx=None,
    motion_dz=None,
    leader_yaw_deg=None,
):
    """Build leader/left/right target points for an equilateral follower formation."""
    s = max(1e-6, float(side_length))
    leader = (float(leader_x), float(leader_z))
    forward, source = resolve_leader_forward(
        leader_forward_x=leader_forward_x,
        leader_forward_z=leader_forward_z,
        motion_dx=motion_dx,
        motion_dz=motion_dz,
        leader_yaw_deg=leader_yaw_deg,
    )
    fx, fz = forward
    right = (fz, -fx)
    half_side = 0.5 * s
    height = (math.sqrt(3.0) / 2.0) * s

    left = (
        leader[0] - (height * fx) - (half_side * right[0]),
        leader[1] - (height * fz) - (half_side * right[1]),
    )
    right_pt = (
        leader[0] - (height * fx) + (half_side * right[0]),
        leader[1] - (height * fz) + (half_side * right[1]),
    )
    return [leader, left, right_pt], source
