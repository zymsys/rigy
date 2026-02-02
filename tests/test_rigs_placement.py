"""Tests for Rigs placement math."""

import numpy as np
import pytest
from numpy.testing import assert_allclose

from rigy.rigs_placement import compute_placement_transform, parse_distance


class TestParseDistance:
    def test_bare_zero(self):
        assert parse_distance("0") == 0.0

    def test_meters(self):
        assert_allclose(parse_distance("1.5m"), 1.5)

    def test_centimeters(self):
        assert_allclose(parse_distance("20cm"), 0.20)

    def test_inches(self):
        assert_allclose(parse_distance("2in"), 0.0508)

    def test_feet(self):
        assert_allclose(parse_distance("1ft"), 0.3048)

    def test_negative(self):
        assert_allclose(parse_distance("-5cm"), -0.05)

    def test_invalid(self):
        with pytest.raises(ValueError, match="Invalid distance"):
            parse_distance("abc")


class TestComputePlacementTransform:
    def _standard_points(self):
        """Frame at origin where Y=world_Y (up).

        build_frame3([0,0,0], [1,0,0], [0,1,0]) produces:
          X=[1,0,0], Y=[0,1,0], Z=[0,0,1]
        """
        p1 = np.array([0.0, 0.0, 0.0])
        p2 = np.array([1.0, 0.0, 0.0])
        p3 = np.array([0.0, 1.0, 0.0])
        return (p1, p2, p3)

    def test_identity_placement(self):
        """Slot and mount at same frame -> identity transform."""
        pts = self._standard_points()
        T = compute_placement_transform(pts, pts, 0, (0.0, 0.0, 0.0))
        assert_allclose(T, np.eye(4), atol=1e-12)

    def test_translation_offset(self):
        """Slot offset from mount -> translation in result."""
        slot_pts = (
            np.array([1.0, 0.0, 0.0]),
            np.array([2.0, 0.0, 0.0]),
            np.array([1.0, 1.0, 0.0]),
        )
        mount_pts = self._standard_points()
        T = compute_placement_transform(slot_pts, mount_pts, 0, (0.0, 0.0, 0.0))
        assert_allclose(T[:3, :3], np.eye(3), atol=1e-12)
        assert_allclose(T[:3, 3], [1.0, 0.0, 0.0], atol=1e-12)

    def test_90deg_rotation(self):
        """90deg rotation about slot frame Y axis (= world Y)."""
        pts = self._standard_points()
        T = compute_placement_transform(pts, pts, 90, (0.0, 0.0, 0.0))
        # Y-axis rotation by 90deg: X->-Z, Z->X
        expected_R = np.array(
            [
                [0.0, 0.0, 1.0],
                [0.0, 1.0, 0.0],
                [-1.0, 0.0, 0.0],
            ]
        )
        assert_allclose(T[:3, :3], expected_R, atol=1e-12)
        assert_allclose(T[:3, 3], [0.0, 0.0, 0.0], atol=1e-12)

    def test_180deg_rotation(self):
        pts = self._standard_points()
        T = compute_placement_transform(pts, pts, 180, (0.0, 0.0, 0.0))
        expected_R = np.array(
            [
                [-1.0, 0.0, 0.0],
                [0.0, 1.0, 0.0],
                [0.0, 0.0, -1.0],
            ]
        )
        assert_allclose(T[:3, :3], expected_R, atol=1e-12)

    def test_nudge(self):
        """Nudge shifts in slot frame axes."""
        pts = self._standard_points()
        # east=0.1, up=0.2, north=0.3
        T = compute_placement_transform(pts, pts, 0, (0.1, 0.2, 0.3))
        # Slot frame axes: east=X=[1,0,0], up=Y=[0,1,0], north=Z=[0,0,1]
        assert_allclose(T[:3, :3], np.eye(3), atol=1e-12)
        assert_allclose(T[:3, 3], [0.1, 0.2, 0.3], atol=1e-12)

    def test_combined_rotation_and_nudge(self):
        """Rotation + nudge combined."""
        pts = self._standard_points()
        T = compute_placement_transform(pts, pts, 90, (0.1, 0.0, 0.0))
        # Nudge of east=0.1 in slot frame X direction = world X
        assert_allclose(T[:3, 3], [0.1, 0.0, 0.0], atol=1e-12)
