"""attach3 frame construction and transform computation."""

from __future__ import annotations

import numpy as np

from rigy.errors import CompositionError

_EPSILON = 1e-9


def build_frame3(p1: np.ndarray, p2: np.ndarray, p3: np.ndarray) -> np.ndarray:
    """Construct a normalized 4x4 affine frame from three anchor points.

    Frame3 construction (per spec):
        x_hat = normalize(p2 - p1)
        t     = p3 - p1
        z_hat = normalize(x_hat x t)   (right-handed)
        y_hat = z_hat x x_hat
        Matrix columns: [x_hat, y_hat, z_hat, p1]

    This is the normalized (orthonormal) frame used for constraint validation
    and visualization. For transform computation with scale, use _build_raw_frame.

    Raises:
        CompositionError: If points are degenerate (coincident or collinear).
    """
    p1 = np.asarray(p1, dtype=np.float64)
    p2 = np.asarray(p2, dtype=np.float64)
    p3 = np.asarray(p3, dtype=np.float64)

    _validate_frame3_constraints(p1, p2, p3)

    d = p2 - p1
    x_hat = d / np.linalg.norm(d)

    t = p3 - p1
    cross = np.cross(x_hat, t)
    z_hat = cross / np.linalg.norm(cross)
    y_hat = np.cross(z_hat, x_hat)

    mat = np.eye(4, dtype=np.float64)
    mat[:3, 0] = x_hat
    mat[:3, 1] = y_hat
    mat[:3, 2] = z_hat
    mat[:3, 3] = p1
    return mat


def _validate_frame3_constraints(p1: np.ndarray, p2: np.ndarray, p3: np.ndarray) -> None:
    """Check that three points form a valid frame3 (non-degenerate)."""
    d = p2 - p1
    d_len = np.linalg.norm(d)
    if d_len < _EPSILON:
        raise CompositionError(f"Frame3 degenerate: distance(p1, p2) = {d_len:.2e} < epsilon")

    x_hat = d / d_len
    t = p3 - p1
    cross = np.cross(x_hat, t)
    cross_len = np.linalg.norm(cross)
    if cross_len < _EPSILON:
        raise CompositionError(
            f"Frame3 degenerate: points are collinear (|x_hat x t| = {cross_len:.2e})"
        )


def _build_raw_frame(p1: np.ndarray, p2: np.ndarray, p3: np.ndarray) -> np.ndarray:
    """Build an unnormalized affine frame that preserves scale information.

    Uses the same axes as build_frame3 but without normalizing lengths,
    so the resulting transform carries scale/shear information.

    Columns: [p2-p1, orthogonal_y, cross(p2-p1, p3-p1), p1]
    The Y axis is computed to be consistent and carry scale.
    """
    p1 = np.asarray(p1, dtype=np.float64)
    p2 = np.asarray(p2, dtype=np.float64)
    p3 = np.asarray(p3, dtype=np.float64)

    col0 = p2 - p1  # x direction (unnormalized)
    t = p3 - p1
    col2 = np.cross(col0, t)  # z direction (unnormalized)

    # y = z cross x (unnormalized, carries scale)
    col1 = np.cross(col2, col0)
    # Normalize y to have length matching t's component perpendicular to x
    # This gives uniform scale when spacing is uniform
    x_hat = col0 / np.linalg.norm(col0)
    t_perp = t - np.dot(t, x_hat) * x_hat
    t_perp_len = np.linalg.norm(t_perp)
    col1_len = np.linalg.norm(col1)
    if col1_len > _EPSILON and t_perp_len > _EPSILON:
        col1 = col1 / col1_len * t_perp_len

    # Normalize z to have consistent scale
    col2_len = np.linalg.norm(col2)
    x_len = np.linalg.norm(col0)
    if col2_len > _EPSILON and x_len > _EPSILON:
        col2 = col2 / col2_len * (x_len * t_perp_len / x_len)

    mat = np.eye(4, dtype=np.float64)
    mat[:3, 0] = col0
    mat[:3, 1] = col1
    mat[:3, 2] = (
        col2 / np.linalg.norm(col2) * t_perp_len if np.linalg.norm(col2) > _EPSILON else col2
    )
    mat[:3, 3] = p1
    return mat


def compute_attach3_transform(
    from_points: tuple[np.ndarray, np.ndarray, np.ndarray],
    to_points: tuple[np.ndarray, np.ndarray, np.ndarray],
    mode: str,
) -> np.ndarray:
    """Compute the attach3 transform from anchor point triplets.

    For rigid mode, uses normalized frames (no scale).
    For uniform/affine modes, uses raw frames to capture scale.

    Args:
        from_points: (p1, p2, p3) source anchor positions.
        to_points: (p1, p2, p3) target anchor positions.
        mode: One of "rigid", "uniform", "affine".

    Returns:
        4x4 transform matrix.

    Raises:
        CompositionError: If mode is unknown or constraints violated.
    """
    fp1, fp2, fp3 = from_points
    tp1, tp2, tp3 = to_points

    # Validate constraints for both sets of points
    _validate_frame3_constraints(fp1, fp2, fp3)
    _validate_frame3_constraints(tp1, tp2, tp3)

    if mode == "rigid":
        from_frame = build_frame3(fp1, fp2, fp3)
        to_frame = build_frame3(tp1, tp2, tp3)
        T = to_frame @ np.linalg.inv(from_frame)
        return _extract_rigid(T)
    elif mode == "uniform":
        from_frame = _build_raw_frame(fp1, fp2, fp3)
        to_frame = _build_raw_frame(tp1, tp2, tp3)
        T = to_frame @ np.linalg.inv(from_frame)
        return _extract_uniform(T)
    elif mode == "affine":
        from_frame = _build_raw_frame(fp1, fp2, fp3)
        to_frame = _build_raw_frame(tp1, tp2, tp3)
        T = to_frame @ np.linalg.inv(from_frame)
        return T
    else:
        raise CompositionError(f"Unknown attach3 mode: {mode!r}")


def _extract_rigid(T: np.ndarray) -> np.ndarray:
    """Extract rotation + translation only (discard any scale/shear)."""
    upper = T[:3, :3]
    U, _s, Vt = np.linalg.svd(upper)
    R = U @ Vt
    if np.linalg.det(R) < 0:
        U[:, -1] *= -1
        R = U @ Vt

    result = np.eye(4, dtype=np.float64)
    result[:3, :3] = R
    result[:3, 3] = T[:3, 3]
    return result


def _extract_uniform(T: np.ndarray) -> np.ndarray:
    """Extract rotation + translation + uniform scale."""
    upper = T[:3, :3]
    det = np.linalg.det(upper)
    scale = np.cbrt(abs(det))
    if scale < _EPSILON:
        raise CompositionError("Degenerate transform: near-zero determinant")

    normalized = upper / scale
    U, _s, Vt = np.linalg.svd(normalized)
    R = U @ Vt
    if np.linalg.det(R) < 0:
        U[:, -1] *= -1
        R = U @ Vt

    result = np.eye(4, dtype=np.float64)
    result[:3, :3] = R * scale
    result[:3, 3] = T[:3, 3]
    return result
