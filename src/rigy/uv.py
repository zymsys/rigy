"""Deterministic UV coordinate generation for Rigy meshes."""

from __future__ import annotations

import math

import numpy as np

from rigy.models import Mesh


def generate_uv_sets(
    mesh: Mesh,
    positions: np.ndarray,
    prim_ranges: dict[str, tuple[int, int]],
) -> list[np.ndarray]:
    """Generate UV sets for a mesh based on its uv_sets definition.

    Args:
        mesh: The mesh definition with optional uv_sets.
        positions: (N, 3) float64 vertex positions (rest-pose).
        prim_ranges: Map of primitive_id -> (start_vertex, end_vertex).

    Returns:
        List of (N, 2) float64 arrays, one per UV set in index order.
        Empty list if mesh has no uv_sets.
    """
    if mesh.uv_sets is None:
        return []

    n_verts = len(positions)
    # Sort UV sets by index (uv0, uv1, ...)
    sorted_keys = sorted(mesh.uv_sets.keys(), key=lambda k: int(k[2:]))

    result = []
    for key in sorted_keys:
        entry = mesh.uv_sets[key]
        uv = np.zeros((n_verts, 2), dtype=np.float64)

        for prim in mesh.primitives:
            if prim.id not in prim_ranges:
                continue
            start, end = prim_ranges[prim.id]
            prim_pos = positions[start:end]
            prim_uv = _generate_for_primitive(entry.generator, prim.type, prim_pos, end - start)
            uv[start:end] = prim_uv

        result.append(uv)

    return result


def _generate_for_primitive(
    generator: str,
    prim_type: str,
    positions: np.ndarray,
    n_verts: int,
) -> np.ndarray:
    """Dispatch to the appropriate generator for a single primitive."""
    generators = {
        "planar_xy@1": _planar_xy,
        "box_project@1": _box_project,
        "sphere_latlong@1": _sphere_latlong,
        "cylindrical@1": _cylindrical,
        "capsule_cyl_latlong@1": _capsule_cyl_latlong,
    }
    gen = generators[generator]
    return gen(positions, n_verts, prim_type)


def _planar_xy(positions: np.ndarray, n_verts: int, prim_type: str) -> np.ndarray:
    """planar_xy@1: u = x, v = y for all primitive types."""
    uv = np.zeros((n_verts, 2), dtype=np.float64)
    uv[:, 0] = positions[:, 0]  # u = x
    uv[:, 1] = positions[:, 1]  # v = y
    return uv


def _box_project(positions: np.ndarray, n_verts: int, prim_type: str) -> np.ndarray:
    """box_project@1: Per-face UV mapping for box primitives.

    6 faces × 4 verts = 24 verts per box.
    Face order matches _tessellate_box: +X, -X, +Y, -Y, +Z, -Z.

    | Face | u    | v    |
    |------|------|------|
    | +X   | -z   | y    |
    | -X   | z    | y    |
    | +Y   | x    | -z   |
    | -Y   | x    | z    |
    | +Z   | x    | y    |
    | -Z   | -x   | y    |
    """
    uv = np.zeros((n_verts, 2), dtype=np.float64)

    # Process in chunks of 24 (one box primitive)
    for base in range(0, n_verts, 24):
        pos = positions[base : base + 24]

        # Face 0: +X → u=-z, v=y
        uv[base + 0 : base + 4, 0] = -pos[0:4, 2]
        uv[base + 0 : base + 4, 1] = pos[0:4, 1]

        # Face 1: -X → u=z, v=y
        uv[base + 4 : base + 8, 0] = pos[4:8, 2]
        uv[base + 4 : base + 8, 1] = pos[4:8, 1]

        # Face 2: +Y → u=x, v=-z
        uv[base + 8 : base + 12, 0] = pos[8:12, 0]
        uv[base + 8 : base + 12, 1] = -pos[8:12, 2]

        # Face 3: -Y → u=x, v=z
        uv[base + 12 : base + 16, 0] = pos[12:16, 0]
        uv[base + 12 : base + 16, 1] = pos[12:16, 2]

        # Face 4: +Z → u=x, v=y
        uv[base + 16 : base + 20, 0] = pos[16:20, 0]
        uv[base + 16 : base + 20, 1] = pos[16:20, 1]

        # Face 5: -Z → u=-x, v=y
        uv[base + 20 : base + 24, 0] = -pos[20:24, 0]
        uv[base + 20 : base + 24, 1] = pos[20:24, 1]

    return uv


def _sphere_latlong(positions: np.ndarray, n_verts: int, prim_type: str) -> np.ndarray:
    """sphere_latlong@1: Index-based UVs from tessellation loop order.

    u = i_lon / 32, v = i_lat / 16.
    17 × 33 = 561 verts per sphere primitive.
    """
    n_lat = 16
    n_lon = 32
    verts_per_sphere = (n_lat + 1) * (n_lon + 1)  # 561

    uv = np.zeros((n_verts, 2), dtype=np.float64)

    for base in range(0, n_verts, verts_per_sphere):
        idx = 0
        for lat in range(n_lat + 1):
            for lon in range(n_lon + 1):
                uv[base + idx, 0] = lon / n_lon  # u
                uv[base + idx, 1] = lat / n_lat  # v
                idx += 1

    return uv


def _cylindrical(positions: np.ndarray, n_verts: int, prim_type: str) -> np.ndarray:
    """cylindrical@1: Side + cap UVs for cylinder primitives.

    Side: u = seg/32, v = row (0=top, 1=bottom).
    Cap center: (0.5, 0.5), rim: u = 0.5+0.5*cos(angle), v = 0.5+0.5*sin(angle).

    Vertex layout per cylinder: 66 side + 34 top cap + 34 bottom cap = 134.
    """
    n_radial = 32
    side_verts = 2 * (n_radial + 1)  # 66
    cap_verts = 1 + (n_radial + 1)  # 34
    verts_per_cyl = side_verts + 2 * cap_verts  # 134

    uv = np.zeros((n_verts, 2), dtype=np.float64)

    for base in range(0, n_verts, verts_per_cyl):
        # Side vertices: 2 rows × (n_radial+1) segs
        idx = base
        for row in range(2):
            for seg in range(n_radial + 1):
                uv[idx, 0] = seg / n_radial  # u
                uv[idx, 1] = float(row)  # v: 0=top, 1=bottom
                idx += 1

        # Top cap: center + (n_radial+1) rim vertices
        uv[idx, 0] = 0.5
        uv[idx, 1] = 0.5
        idx += 1
        for seg in range(n_radial + 1):
            angle = 2.0 * math.pi * seg / n_radial
            uv[idx, 0] = 0.5 + 0.5 * math.cos(angle)
            uv[idx, 1] = 0.5 + 0.5 * math.sin(angle)
            idx += 1

        # Bottom cap: center + (n_radial+1) rim vertices
        uv[idx, 0] = 0.5
        uv[idx, 1] = 0.5
        idx += 1
        for seg in range(n_radial + 1):
            angle = 2.0 * math.pi * seg / n_radial
            uv[idx, 0] = 0.5 + 0.5 * math.cos(angle)
            uv[idx, 1] = 0.5 + 0.5 * math.sin(angle)
            idx += 1

    return uv


def _capsule_cyl_latlong(positions: np.ndarray, n_verts: int, prim_type: str) -> np.ndarray:
    """capsule_cyl_latlong@1: Continuous v spanning top hemi → cylinder → bottom hemi.

    u = seg / 32.
    Top hemisphere: rings 0..8 (9 rings × 33 verts = 297)
    Cylinder: rows 0..8 (9 rows × 33 verts = 297)
    Bottom hemisphere: rings 1..8 (8 rings × 33 verts = 264)
    Total: 858 verts per capsule.

    V_total = 8 + 8 + 8 = 24 v-divisions.
    Top hemi v: ring_i / 24 for ring_i in 0..8
    Cylinder v: (8 + row_i) / 24 for row_i in 0..8
    Bottom hemi v: (16 + ring_i) / 24 for ring_i in 1..8
    """
    n_radial = 32
    n_hemisphere_rings = 8
    n_height = 8
    v_total = n_hemisphere_rings + n_height + n_hemisphere_rings  # 24

    top_hemi_verts = (n_hemisphere_rings + 1) * (n_radial + 1)  # 297
    cyl_verts = (n_height + 1) * (n_radial + 1)  # 297
    bot_hemi_verts = n_hemisphere_rings * (n_radial + 1)  # 264
    verts_per_capsule = top_hemi_verts + cyl_verts + bot_hemi_verts  # 858

    uv = np.zeros((n_verts, 2), dtype=np.float64)

    for base in range(0, n_verts, verts_per_capsule):
        idx = base

        # Top hemisphere: rings 0..8
        for ring in range(n_hemisphere_rings + 1):
            v_val = ring / v_total
            for seg in range(n_radial + 1):
                uv[idx, 0] = seg / n_radial
                uv[idx, 1] = v_val
                idx += 1

        # Cylinder: rows 0..8
        for row in range(n_height + 1):
            v_val = (n_hemisphere_rings + row) / v_total
            for seg in range(n_radial + 1):
                uv[idx, 0] = seg / n_radial
                uv[idx, 1] = v_val
                idx += 1

        # Bottom hemisphere: rings 1..8
        for ring in range(1, n_hemisphere_rings + 1):
            v_val = (n_hemisphere_rings + n_height + ring) / v_total
            for seg in range(n_radial + 1):
                uv[idx, 0] = seg / n_radial
                uv[idx, 1] = v_val
                idx += 1

    return uv
