"""Tests for attach3 frame construction and transform computation."""

import numpy as np
import pytest
from numpy.testing import assert_allclose

from rigy.attach3 import build_frame3, compute_attach3_transform
from rigy.errors import CompositionError


class TestFrame3Construction:
    def test_identity_frame(self):
        """Standard basis at origin: p3 in Y direction produces identity frame."""
        p1 = np.array([0, 0, 0], dtype=np.float64)
        p2 = np.array([1, 0, 0], dtype=np.float64)
        p3 = np.array([0, 1, 0], dtype=np.float64)
        frame = build_frame3(p1, p2, p3)

        assert_allclose(frame[:3, 0], [1, 0, 0], atol=1e-12)  # x_hat
        assert_allclose(frame[:3, 1], [0, 1, 0], atol=1e-12)  # y_hat
        assert_allclose(frame[:3, 2], [0, 0, 1], atol=1e-12)  # z_hat
        assert_allclose(frame[:3, 3], [0, 0, 0], atol=1e-12)  # origin

    def test_wheel_convention_frame(self):
        """Wheel mount convention: p3 at +Z gives frame with y->+Z, z->-Y."""
        p1 = np.array([0, 0, 0], dtype=np.float64)
        p2 = np.array([1, 0, 0], dtype=np.float64)
        p3 = np.array([0, 0, 1], dtype=np.float64)
        frame = build_frame3(p1, p2, p3)

        assert_allclose(frame[:3, 0], [1, 0, 0], atol=1e-12)
        assert_allclose(frame[:3, 1], [0, 0, 1], atol=1e-12)
        assert_allclose(frame[:3, 2], [0, -1, 0], atol=1e-12)

    def test_translated_frame(self):
        """Frame at a non-zero origin."""
        p1 = np.array([5, 3, 2], dtype=np.float64)
        p2 = np.array([6, 3, 2], dtype=np.float64)
        p3 = np.array([5, 4, 2], dtype=np.float64)
        frame = build_frame3(p1, p2, p3)

        assert_allclose(frame[:3, 3], [5, 3, 2], atol=1e-12)
        assert_allclose(frame[:3, 0], [1, 0, 0], atol=1e-12)

    def test_orthonormality(self):
        """Frame axes must be orthonormal."""
        p1 = np.array([1, 2, 3], dtype=np.float64)
        p2 = np.array([4, 2, 3], dtype=np.float64)
        p3 = np.array([1, 5, 3], dtype=np.float64)
        frame = build_frame3(p1, p2, p3)

        x = frame[:3, 0]
        y = frame[:3, 1]
        z = frame[:3, 2]

        assert_allclose(np.linalg.norm(x), 1.0, atol=1e-12)
        assert_allclose(np.linalg.norm(y), 1.0, atol=1e-12)
        assert_allclose(np.linalg.norm(z), 1.0, atol=1e-12)
        assert_allclose(np.dot(x, y), 0.0, atol=1e-12)
        assert_allclose(np.dot(x, z), 0.0, atol=1e-12)
        assert_allclose(np.dot(y, z), 0.0, atol=1e-12)

    def test_right_handed(self):
        """det(rotation) = +1."""
        p1 = np.array([0, 0, 0], dtype=np.float64)
        p2 = np.array([1, 0, 0], dtype=np.float64)
        p3 = np.array([0, 1, 0], dtype=np.float64)
        frame = build_frame3(p1, p2, p3)
        assert_allclose(np.linalg.det(frame[:3, :3]), 1.0, atol=1e-12)

    def test_coincident_points_raises(self):
        p1 = np.array([1, 2, 3], dtype=np.float64)
        with pytest.raises(CompositionError, match="degenerate"):
            build_frame3(p1, p1, np.array([4, 5, 6]))

    def test_collinear_points_raises(self):
        with pytest.raises(CompositionError, match="collinear"):
            build_frame3(
                np.array([0, 0, 0]),
                np.array([1, 0, 0]),
                np.array([2, 0, 0]),
            )


def _pts(p1, p2, p3):
    """Helper to make a point triplet."""
    return (
        np.array(p1, dtype=np.float64),
        np.array(p2, dtype=np.float64),
        np.array(p3, dtype=np.float64),
    )


class TestAttach3Modes:
    def test_rigid_pure_translation(self):
        """Rigid mode: aligned frames with only translation."""
        from_pts = _pts([0, 0, 0], [1, 0, 0], [0, 1, 0])
        to_pts = _pts([5, 0, 0], [6, 0, 0], [5, 1, 0])
        T = compute_attach3_transform(from_pts, to_pts, "rigid")

        assert_allclose(T[:3, :3], np.eye(3), atol=1e-10)
        assert_allclose(T[:3, 3], [5, 0, 0], atol=1e-10)

    def test_uniform_pure_translation(self):
        """Uniform mode with same-size frames: pure translation."""
        from_pts = _pts([0, 0, 0], [1, 0, 0], [0, 1, 0])
        to_pts = _pts([5, 0, 0], [6, 0, 0], [5, 1, 0])
        T = compute_attach3_transform(from_pts, to_pts, "uniform")

        assert_allclose(T[:3, :3], np.eye(3), atol=1e-10)
        assert_allclose(T[:3, 3], [5, 0, 0], atol=1e-10)

    def test_affine_pure_translation(self):
        """Affine mode with same-size frames: pure translation."""
        from_pts = _pts([0, 0, 0], [1, 0, 0], [0, 1, 0])
        to_pts = _pts([5, 0, 0], [6, 0, 0], [5, 1, 0])
        T = compute_attach3_transform(from_pts, to_pts, "affine")

        assert_allclose(T[:3, :3], np.eye(3), atol=1e-10)
        assert_allclose(T[:3, 3], [5, 0, 0], atol=1e-10)

    def test_rigid_discards_scale(self):
        """Rigid mode should discard scale."""
        from_pts = _pts([0, 0, 0], [1, 0, 0], [0, 1, 0])
        to_pts = _pts([0, 0, 0], [2, 0, 0], [0, 2, 0])
        T = compute_attach3_transform(from_pts, to_pts, "rigid")

        upper = T[:3, :3]
        assert_allclose(abs(np.linalg.det(upper)), 1.0, atol=1e-10)

    def test_uniform_extracts_scale(self):
        """Uniform mode should extract uniform scale factor 2."""
        from_pts = _pts([0, 0, 0], [1, 0, 0], [0, 1, 0])
        to_pts = _pts([0, 0, 0], [2, 0, 0], [0, 2, 0])
        T = compute_attach3_transform(from_pts, to_pts, "uniform")

        upper = T[:3, :3]
        det = np.linalg.det(upper)
        scale = np.cbrt(abs(det))
        assert_allclose(scale, 2.0, atol=1e-10)

    def test_affine_preserves_full_transform(self):
        """Affine mode maps origin correctly."""
        from_pts = _pts([0, 0, 0], [1, 0, 0], [0, 1, 0])
        to_pts = _pts([10, 0, 0], [12, 0, 0], [10, 3, 0])
        T = compute_attach3_transform(from_pts, to_pts, "affine")

        origin = np.array([0, 0, 0, 1])
        result = T @ origin
        assert_allclose(result[:3], [10, 0, 0], atol=1e-10)

    def test_unknown_mode_raises(self):
        from_pts = _pts([0, 0, 0], [1, 0, 0], [0, 1, 0])
        with pytest.raises(CompositionError, match="Unknown"):
            compute_attach3_transform(from_pts, from_pts, "invalid")

    def test_rigid_rotation(self):
        """Rigid mode: 90-degree rotation around Y (X -> -Z)."""
        from_pts = _pts([0, 0, 0], [1, 0, 0], [0, 1, 0])
        to_pts = _pts([0, 0, 0], [0, 0, -1], [0, 1, 0])
        T = compute_attach3_transform(from_pts, to_pts, "rigid")

        x_dir = T[:3, :3] @ np.array([1, 0, 0])
        assert_allclose(x_dir, [0, 0, -1], atol=1e-10)

    def test_determinism(self):
        """Same inputs produce identical outputs."""
        from_pts = _pts([1, 2, 3], [4, 2, 3], [1, 5, 3])
        to_pts = _pts([10, 0, 0], [11, 0, 0], [10, 1, 0])
        T1 = compute_attach3_transform(from_pts, to_pts, "rigid")
        T2 = compute_attach3_transform(from_pts, to_pts, "rigid")
        assert_allclose(T1, T2, atol=0)

    def test_collinear_from_raises(self):
        from_pts = _pts([0, 0, 0], [1, 0, 0], [2, 0, 0])
        to_pts = _pts([0, 0, 0], [1, 0, 0], [0, 1, 0])
        with pytest.raises(CompositionError):
            compute_attach3_transform(from_pts, to_pts, "rigid")

    def test_collinear_to_raises(self):
        from_pts = _pts([0, 0, 0], [1, 0, 0], [0, 1, 0])
        to_pts = _pts([0, 0, 0], [1, 0, 0], [2, 0, 0])
        with pytest.raises(CompositionError):
            compute_attach3_transform(from_pts, to_pts, "rigid")
