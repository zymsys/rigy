"""Placement transform math for Rigs scene composition."""

from __future__ import annotations

import re

import numpy as np

from rigy.attach3 import build_frame3

_UNIT_CONVERSIONS = {
    "m": 1.0,
    "cm": 0.01,
    "in": 0.0254,
    "ft": 0.3048,
}

_DISTANCE_PATTERN = re.compile(r"^(-?\d+(?:\.\d+)?)(cm|m|in|ft)?$")

# Precomputed Y-axis rotation matrices for discrete angles
_YROT = {
    0: np.eye(3, dtype=np.float64),
    90: np.array(
        [
            [0.0, 0.0, 1.0],
            [0.0, 1.0, 0.0],
            [-1.0, 0.0, 0.0],
        ],
        dtype=np.float64,
    ),
    180: np.array(
        [
            [-1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, -1.0],
        ],
        dtype=np.float64,
    ),
    270: np.array(
        [
            [0.0, 0.0, -1.0],
            [0.0, 1.0, 0.0],
            [1.0, 0.0, 0.0],
        ],
        dtype=np.float64,
    ),
}


def parse_distance(value: str) -> float:
    """Parse a distance string with optional unit to meters.

    Accepted formats: "0", "10cm", "0.25m", "2in", "1ft", "-5cm"

    Returns:
        Distance in meters.

    Raises:
        ValueError: If format is invalid.
    """
    s = str(value).strip()
    m = _DISTANCE_PATTERN.match(s)
    if not m:
        raise ValueError(f"Invalid distance value: {value!r}")
    num = float(m.group(1))
    unit = m.group(2)
    if unit is None:
        return num  # bare number treated as meters
    return num * _UNIT_CONVERSIONS[unit]


def compute_placement_transform(
    slot_points: tuple[np.ndarray, np.ndarray, np.ndarray],
    mount_points: tuple[np.ndarray, np.ndarray, np.ndarray],
    rotate_deg: int,
    nudge_meters: tuple[float, float, float],
) -> np.ndarray:
    """Compute the placement 4x4 transform per Rigs spec Section 9.

    Args:
        slot_points: (p1, p2, p3) anchor positions defining the slot frame.
        mount_points: (p1, p2, p3) anchor positions defining the mount frame.
        rotate_deg: Discrete rotation in degrees (0, 90, 180, 270).
        nudge_meters: (east, up, north) nudge in meters.

    Returns:
        4x4 affine transform matrix (float64).
    """
    # Build slot frame: columns [Xs, Ys, Zs, Os]
    slot_frame = build_frame3(slot_points[0], slot_points[1], slot_points[2])
    Rs = slot_frame[:3, :3]  # [Xs, Ys, Zs] as columns
    Os = slot_frame[:3, 3]

    # Build mount frame: columns [Xm, Ym, Zm, Om]
    mount_frame = build_frame3(mount_points[0], mount_points[1], mount_points[2])
    Rm = mount_frame[:3, :3]
    Om = mount_frame[:3, 3]

    # Y-axis rotation in slot frame
    Rrot = _YROT[rotate_deg]

    # Nudge in slot frame axes: east*Xs + up*Ys + north*Zs
    east, up, north = nudge_meters
    Tnudge = east * Rs[:, 0] + up * Rs[:, 1] + north * Rs[:, 2]

    # R = Rs @ Rrot @ inv(Rm)
    R = Rs @ Rrot @ np.linalg.inv(Rm)

    # T = (Os + Tnudge) - R @ Om
    T = (Os + Tnudge) - R @ Om

    result = np.eye(4, dtype=np.float64)
    result[:3, :3] = R
    result[:3, 3] = T
    return result
