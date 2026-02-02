"""Tests for tessellation geometry generation."""

import numpy as np
import pytest

from rigy.errors import TessellationError
from rigy.models import Mesh, Primitive, Transform
from rigy.tessellation import tessellate_mesh, tessellate_primitive


class TestBox:
    def test_vertex_count(self):
        p = Primitive(type="box", id="b", dimensions={"x": 1, "y": 1, "z": 1})
        md = tessellate_primitive(p)
        assert md.positions.shape == (24, 3)

    def test_index_count(self):
        p = Primitive(type="box", id="b", dimensions={"x": 1, "y": 1, "z": 1})
        md = tessellate_primitive(p)
        assert md.indices.shape == (36,)

    def test_dimensions_respected(self):
        p = Primitive(type="box", id="b", dimensions={"x": 2.0, "y": 4.0, "z": 6.0})
        md = tessellate_primitive(p)
        assert np.isclose(md.positions[:, 0].max(), 1.0, atol=1e-5)  # half of x=2
        assert np.isclose(md.positions[:, 1].max(), 2.0, atol=1e-5)  # half of y=4
        assert np.isclose(md.positions[:, 2].max(), 3.0, atol=1e-5)  # half of z=6

    def test_normals_unit_length(self):
        p = Primitive(type="box", id="b", dimensions={"x": 1, "y": 1, "z": 1})
        md = tessellate_primitive(p)
        lengths = np.linalg.norm(md.normals, axis=1)
        np.testing.assert_allclose(lengths, 1.0, atol=1e-5)


class TestSphere:
    def test_vertex_count(self):
        p = Primitive(type="sphere", id="s", dimensions={"radius": 0.5})
        md = tessellate_primitive(p)
        # (16+1) * (32+1) = 561
        assert md.positions.shape == (561, 3)

    def test_radius_respected(self):
        p = Primitive(type="sphere", id="s", dimensions={"radius": 2.0})
        md = tessellate_primitive(p)
        distances = np.linalg.norm(md.positions, axis=1)
        np.testing.assert_allclose(distances, 2.0, atol=1e-4)

    def test_normals_unit_length(self):
        p = Primitive(type="sphere", id="s", dimensions={"radius": 1.0})
        md = tessellate_primitive(p)
        # Exclude poles where normals might be degenerate
        lengths = np.linalg.norm(md.normals, axis=1)
        # All normals should be unit length (sphere normals = normalized positions)
        np.testing.assert_allclose(lengths, 1.0, atol=1e-4)


class TestCylinder:
    def test_vertex_count(self):
        p = Primitive(type="cylinder", id="c", dimensions={"radius": 0.5, "height": 1.0})
        md = tessellate_primitive(p)
        # Side: 2 * (32+1) = 66
        # Top cap: 1 center + (32+1) = 34
        # Bottom cap: 1 center + (32+1) = 34
        # Total: 66 + 34 + 34 = 134
        assert md.positions.shape == (134, 3)

    def test_height_respected(self):
        p = Primitive(type="cylinder", id="c", dimensions={"radius": 0.5, "height": 3.0})
        md = tessellate_primitive(p)
        assert np.isclose(md.positions[:, 1].max(), 1.5, atol=1e-5)
        assert np.isclose(md.positions[:, 1].min(), -1.5, atol=1e-5)


class TestCapsule:
    def test_vertex_count(self):
        p = Primitive(type="capsule", id="cap", dimensions={"radius": 0.25, "height": 1.0})
        md = tessellate_primitive(p)
        # Top hemisphere: (8+1) * (32+1) = 297
        # Cylinder: (8+1) * (32+1) = 297
        # Bottom hemisphere: 8 * (32+1) = 264
        # Total: 297 + 297 + 264 = 858
        assert md.positions.shape == (858, 3)

    def test_height_extents(self):
        p = Primitive(type="capsule", id="cap", dimensions={"radius": 0.25, "height": 1.0})
        md = tessellate_primitive(p)
        # Total extent: half_h + radius = 0.5 + 0.25 = 0.75
        assert md.positions[:, 1].max() <= 0.76
        assert md.positions[:, 1].min() >= -0.76


class TestWedge:
    def test_vertex_count(self):
        p = Primitive(type="wedge", id="w", dimensions={"x": 2, "y": 2, "z": 2})
        md = tessellate_primitive(p)
        assert md.positions.shape == (18, 3)

    def test_index_count(self):
        p = Primitive(type="wedge", id="w", dimensions={"x": 2, "y": 2, "z": 2})
        md = tessellate_primitive(p)
        assert md.indices.shape == (24,)

    def test_dimensions_respected(self):
        p = Primitive(type="wedge", id="w", dimensions={"x": 4.0, "y": 6.0, "z": 2.0})
        md = tessellate_primitive(p)
        # Half-extents: hx=2, hy=3, hz=1
        np.testing.assert_allclose(md.positions[:, 0].min(), -2.0, atol=1e-10)
        np.testing.assert_allclose(md.positions[:, 0].max(), 2.0, atol=1e-10)
        np.testing.assert_allclose(md.positions[:, 1].min(), -3.0, atol=1e-10)
        np.testing.assert_allclose(md.positions[:, 1].max(), 3.0, atol=1e-10)
        np.testing.assert_allclose(md.positions[:, 2].min(), -1.0, atol=1e-10)
        np.testing.assert_allclose(md.positions[:, 2].max(), 1.0, atol=1e-10)

    def test_normals_unit_length(self):
        p = Primitive(type="wedge", id="w", dimensions={"x": 2, "y": 2, "z": 2})
        md = tessellate_primitive(p)
        lengths = np.linalg.norm(md.normals, axis=1)
        np.testing.assert_allclose(lengths, 1.0, atol=1e-10)

    def test_flat_normals(self):
        """Each face's vertices should share a single normal."""
        p = Primitive(type="wedge", id="w", dimensions={"x": 2, "y": 2, "z": 2})
        md = tessellate_primitive(p)
        # Face vertex counts: 4, 4, 4, 3, 3 = 18
        face_sizes = [4, 4, 4, 3, 3]
        offset = 0
        for size in face_sizes:
            face_normals = md.normals[offset : offset + size]
            # All normals in a face should be identical
            for i in range(1, size):
                np.testing.assert_allclose(face_normals[i], face_normals[0], atol=1e-10)
            offset += size

    def test_slope_normal(self):
        """Slope normal should be normalize(z, 0, x) for given dimensions."""
        import math

        p = Primitive(type="wedge", id="w", dimensions={"x": 3.0, "y": 2.0, "z": 4.0})
        md = tessellate_primitive(p)
        # Slope face starts at vertex 8 (after -z:4 + -x:4)
        slope_normal = md.normals[8]
        x, z = 3.0, 4.0
        length = math.sqrt(z * z + x * x)
        expected = np.array([z / length, 0.0, x / length])
        np.testing.assert_allclose(slope_normal, expected, atol=1e-10)


class TestTransform:
    def test_translation_applied(self):
        p = Primitive(
            type="box",
            id="b",
            dimensions={"x": 1, "y": 1, "z": 1},
            transform=Transform(translation=(10.0, 20.0, 30.0)),
        )
        md = tessellate_primitive(p)
        # Center should be at (10, 20, 30)
        center = md.positions.mean(axis=0)
        np.testing.assert_allclose(center, [10.0, 20.0, 30.0], atol=1e-5)

    def test_rotation_applied(self):
        import math

        p = Primitive(
            type="box",
            id="b",
            dimensions={"x": 2, "y": 2, "z": 2},
            transform=Transform(rotation_euler=(0, 0, math.pi / 2)),
        )
        md = tessellate_primitive(p)
        # After 90° rotation around Z, x extent should become y extent
        assert md.positions[:, 0].max() <= 1.01
        assert md.positions[:, 1].max() <= 1.01


class TestDeterminism:
    def test_identical_across_calls(self):
        p = Primitive(type="sphere", id="s", dimensions={"radius": 1.0})
        md1 = tessellate_primitive(p)
        md2 = tessellate_primitive(p)
        np.testing.assert_array_equal(md1.positions, md2.positions)
        np.testing.assert_array_equal(md1.normals, md2.normals)
        np.testing.assert_array_equal(md1.indices, md2.indices)


class TestMeshMerge:
    def test_merge_two_primitives(self):
        mesh = Mesh(
            id="m1",
            primitives=[
                Primitive(type="box", id="p1", dimensions={"x": 1, "y": 1, "z": 1}),
                Primitive(type="box", id="p2", dimensions={"x": 1, "y": 1, "z": 1}),
            ],
        )
        md, prim_ranges = tessellate_mesh(mesh)
        assert len(md.positions) == 48  # 24 + 24
        assert "p1" in prim_ranges
        assert "p2" in prim_ranges
        assert prim_ranges["p1"] == (0, 24)
        assert prim_ranges["p2"] == (24, 48)


class TestUnknownProfile:
    def test_unknown_profile_rejected(self):
        p = Primitive(type="box", id="b", dimensions={"x": 1, "y": 1, "z": 1})
        with pytest.raises(TessellationError, match="Unknown tessellation profile"):
            tessellate_primitive(p, profile="custom_v2")
