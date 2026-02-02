"""Tests for UV coordinate generation."""

import numpy as np
import pytest

from rigy.models import Mesh, Primitive, UvSetEntry
from rigy.tessellation import tessellate_mesh
from rigy.uv import generate_uv_sets


def _make_mesh(prim_type: str, prim_id: str = "p1", dims: dict | None = None, uv_sets: dict | None = None) -> Mesh:
    """Helper to create a mesh with one primitive and uv_sets."""
    if dims is None:
        dims = {"x": 1.0, "y": 1.0, "z": 1.0} if prim_type == "box" else {"radius": 0.5}
        if prim_type in ("cylinder", "capsule"):
            dims = {"radius": 0.5, "height": 1.0}
    return Mesh(
        id="m1",
        primitives=[Primitive(type=prim_type, id=prim_id, dimensions=dims)],
        uv_sets=uv_sets,
    )


class TestPlanarXY:
    def test_box_uvs_match_xy(self):
        mesh = _make_mesh("box", uv_sets={"uv0": UvSetEntry(generator="planar_xy@1")})
        mesh_data, prim_ranges = tessellate_mesh(mesh)
        uv_arrays = generate_uv_sets(mesh, mesh_data.positions, prim_ranges)
        assert len(uv_arrays) == 1
        uv = uv_arrays[0]
        assert uv.shape == (24, 2)
        np.testing.assert_allclose(uv[:, 0], mesh_data.positions[:, 0])
        np.testing.assert_allclose(uv[:, 1], mesh_data.positions[:, 1])

    def test_sphere_uvs_match_xy(self):
        mesh = _make_mesh("sphere", uv_sets={"uv0": UvSetEntry(generator="planar_xy@1")})
        mesh_data, prim_ranges = tessellate_mesh(mesh)
        uv_arrays = generate_uv_sets(mesh, mesh_data.positions, prim_ranges)
        uv = uv_arrays[0]
        np.testing.assert_allclose(uv[:, 0], mesh_data.positions[:, 0])
        np.testing.assert_allclose(uv[:, 1], mesh_data.positions[:, 1])

    def test_float64_intermediates(self):
        mesh = _make_mesh("box", uv_sets={"uv0": UvSetEntry(generator="planar_xy@1")})
        mesh_data, prim_ranges = tessellate_mesh(mesh)
        uv_arrays = generate_uv_sets(mesh, mesh_data.positions, prim_ranges)
        assert uv_arrays[0].dtype == np.float64


class TestBoxProject:
    def test_box_24_verts(self):
        mesh = _make_mesh("box", uv_sets={"uv0": UvSetEntry(generator="box_project@1")})
        mesh_data, prim_ranges = tessellate_mesh(mesh)
        uv_arrays = generate_uv_sets(mesh, mesh_data.positions, prim_ranges)
        assert uv_arrays[0].shape == (24, 2)

    def test_plus_x_face(self):
        """Face 0 (+X): u = -z, v = y."""
        mesh = _make_mesh("box", uv_sets={"uv0": UvSetEntry(generator="box_project@1")})
        mesh_data, prim_ranges = tessellate_mesh(mesh)
        uv_arrays = generate_uv_sets(mesh, mesh_data.positions, prim_ranges)
        uv = uv_arrays[0]
        pos = mesh_data.positions
        # Verts 0-3 are +X face
        np.testing.assert_allclose(uv[0:4, 0], -pos[0:4, 2])
        np.testing.assert_allclose(uv[0:4, 1], pos[0:4, 1])

    def test_plus_z_face(self):
        """Face 4 (+Z): u = x, v = y."""
        mesh = _make_mesh("box", uv_sets={"uv0": UvSetEntry(generator="box_project@1")})
        mesh_data, prim_ranges = tessellate_mesh(mesh)
        uv_arrays = generate_uv_sets(mesh, mesh_data.positions, prim_ranges)
        uv = uv_arrays[0]
        pos = mesh_data.positions
        # Verts 16-19 are +Z face
        np.testing.assert_allclose(uv[16:20, 0], pos[16:20, 0])
        np.testing.assert_allclose(uv[16:20, 1], pos[16:20, 1])

    def test_minus_z_face(self):
        """Face 5 (-Z): u = -x, v = y."""
        mesh = _make_mesh("box", uv_sets={"uv0": UvSetEntry(generator="box_project@1")})
        mesh_data, prim_ranges = tessellate_mesh(mesh)
        uv_arrays = generate_uv_sets(mesh, mesh_data.positions, prim_ranges)
        uv = uv_arrays[0]
        pos = mesh_data.positions
        # Verts 20-23 are -Z face
        np.testing.assert_allclose(uv[20:24, 0], -pos[20:24, 0])
        np.testing.assert_allclose(uv[20:24, 1], pos[20:24, 1])


class TestSphereLatlong:
    def test_vertex_count(self):
        mesh = _make_mesh("sphere", uv_sets={"uv0": UvSetEntry(generator="sphere_latlong@1")})
        mesh_data, prim_ranges = tessellate_mesh(mesh)
        assert len(mesh_data.positions) == 561  # 17 * 33

    def test_poles(self):
        """Top pole at v=0, bottom pole at v=1."""
        mesh = _make_mesh("sphere", uv_sets={"uv0": UvSetEntry(generator="sphere_latlong@1")})
        mesh_data, prim_ranges = tessellate_mesh(mesh)
        uv_arrays = generate_uv_sets(mesh, mesh_data.positions, prim_ranges)
        uv = uv_arrays[0]
        # First row (lat=0) should have v=0
        np.testing.assert_allclose(uv[0:33, 1], 0.0)
        # Last row (lat=16) should have v=1
        np.testing.assert_allclose(uv[528:561, 1], 1.0)

    def test_seam(self):
        """First column u=0, last column u=1."""
        mesh = _make_mesh("sphere", uv_sets={"uv0": UvSetEntry(generator="sphere_latlong@1")})
        mesh_data, prim_ranges = tessellate_mesh(mesh)
        uv_arrays = generate_uv_sets(mesh, mesh_data.positions, prim_ranges)
        uv = uv_arrays[0]
        # First vertex in each row should have u=0
        for lat in range(17):
            assert uv[lat * 33, 0] == pytest.approx(0.0)
        # Last vertex in each row should have u=1
        for lat in range(17):
            assert uv[lat * 33 + 32, 0] == pytest.approx(1.0)


class TestCylindrical:
    def test_vertex_count(self):
        mesh = _make_mesh("cylinder", uv_sets={"uv0": UvSetEntry(generator="cylindrical@1")})
        mesh_data, prim_ranges = tessellate_mesh(mesh)
        assert len(mesh_data.positions) == 134  # 66 + 34 + 34

    def test_side_seam(self):
        """Side vertices: first column u=0, last column u=1."""
        mesh = _make_mesh("cylinder", uv_sets={"uv0": UvSetEntry(generator="cylindrical@1")})
        mesh_data, prim_ranges = tessellate_mesh(mesh)
        uv_arrays = generate_uv_sets(mesh, mesh_data.positions, prim_ranges)
        uv = uv_arrays[0]
        # Top row first vertex: u=0, v=0
        assert uv[0, 0] == pytest.approx(0.0)
        assert uv[0, 1] == pytest.approx(0.0)
        # Top row last vertex: u=1, v=0
        assert uv[32, 0] == pytest.approx(1.0)
        assert uv[32, 1] == pytest.approx(0.0)
        # Bottom row first vertex: u=0, v=1
        assert uv[33, 0] == pytest.approx(0.0)
        assert uv[33, 1] == pytest.approx(1.0)

    def test_cap_center(self):
        """Cap center at (0.5, 0.5)."""
        mesh = _make_mesh("cylinder", uv_sets={"uv0": UvSetEntry(generator="cylindrical@1")})
        mesh_data, prim_ranges = tessellate_mesh(mesh)
        uv_arrays = generate_uv_sets(mesh, mesh_data.positions, prim_ranges)
        uv = uv_arrays[0]
        # Top cap center is at index 66
        assert uv[66, 0] == pytest.approx(0.5)
        assert uv[66, 1] == pytest.approx(0.5)
        # Bottom cap center is at index 100
        assert uv[100, 0] == pytest.approx(0.5)
        assert uv[100, 1] == pytest.approx(0.5)


class TestCapsuleCylLatlong:
    def test_vertex_count(self):
        mesh = _make_mesh("capsule", uv_sets={"uv0": UvSetEntry(generator="capsule_cyl_latlong@1")})
        mesh_data, prim_ranges = tessellate_mesh(mesh)
        assert len(mesh_data.positions) == 858  # 297 + 297 + 264

    def test_monotonic_v(self):
        """v should increase from 0 to 1 across the capsule."""
        mesh = _make_mesh("capsule", uv_sets={"uv0": UvSetEntry(generator="capsule_cyl_latlong@1")})
        mesh_data, prim_ranges = tessellate_mesh(mesh)
        uv_arrays = generate_uv_sets(mesh, mesh_data.positions, prim_ranges)
        uv = uv_arrays[0]
        # Check v=0 at top pole
        assert uv[0, 1] == pytest.approx(0.0)
        # Check v=1 at bottom pole
        assert uv[-1, 1] == pytest.approx(1.0)
        # Check monotonicity: sample first vertex per ring
        prev_v = -1.0
        ring_stride = 33
        for ring_start in range(0, 858, ring_stride):
            v = uv[ring_start, 1]
            assert v >= prev_v - 1e-12
            prev_v = v

    def test_equator_continuity(self):
        """v should be continuous at the top-hemi/cylinder and cylinder/bottom-hemi boundaries."""
        mesh = _make_mesh("capsule", uv_sets={"uv0": UvSetEntry(generator="capsule_cyl_latlong@1")})
        mesh_data, prim_ranges = tessellate_mesh(mesh)
        uv_arrays = generate_uv_sets(mesh, mesh_data.positions, prim_ranges)
        uv = uv_arrays[0]
        # Top hemi last ring (ring 8) = v = 8/24
        # Cylinder first row (row 0) = v = 8/24
        top_hemi_last = 8 * 33  # first vert of ring 8
        cyl_first = 9 * 33  # first vert of cylinder row 0
        assert uv[top_hemi_last, 1] == pytest.approx(uv[cyl_first, 1])


class TestMultiUvSets:
    def test_returns_correct_number(self):
        mesh = _make_mesh(
            "box",
            uv_sets={
                "uv0": UvSetEntry(generator="planar_xy@1"),
                "uv1": UvSetEntry(generator="box_project@1"),
            },
        )
        mesh_data, prim_ranges = tessellate_mesh(mesh)
        uv_arrays = generate_uv_sets(mesh, mesh_data.positions, prim_ranges)
        assert len(uv_arrays) == 2
        assert uv_arrays[0].shape == (24, 2)
        assert uv_arrays[1].shape == (24, 2)


class TestNoUvSets:
    def test_returns_empty_list(self):
        mesh = _make_mesh("box")
        mesh_data, prim_ranges = tessellate_mesh(mesh)
        uv_arrays = generate_uv_sets(mesh, mesh_data.positions, prim_ranges)
        assert uv_arrays == []
