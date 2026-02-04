"""Deterministic primitive geometry generation."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from rigy.errors import TessellationError
from rigy.models import Mesh, Primitive


@dataclass
class MeshData:
    """Tessellated mesh geometry."""

    positions: np.ndarray  # (N, 3) float64
    normals: np.ndarray  # (N, 3) float64
    indices: np.ndarray  # (M,) uint32


def tessellate_primitive(primitive: Primitive, profile: str = "v0_1_default") -> MeshData:
    """Generate deterministic geometry for a single primitive."""
    if profile != "v0_1_default":
        raise TessellationError(f"Unknown tessellation profile: {profile!r}")

    generators = {
        "box": _tessellate_box,
        "sphere": _tessellate_sphere,
        "cylinder": _tessellate_cylinder,
        "capsule": _tessellate_capsule,
        "wedge": _tessellate_wedge,
    }

    gen = generators.get(primitive.type)
    if gen is None:
        raise TessellationError(f"Unknown primitive type: {primitive.type!r}")

    mesh_data = gen(primitive.dimensions)
    mesh_data = _apply_transform(mesh_data, primitive)
    return mesh_data


def tessellate_mesh(
    mesh: Mesh, profile: str = "v0_1_default"
) -> tuple[MeshData, dict[str, tuple[int, int]]]:
    """Tessellate all primitives in a mesh and merge.

    Returns:
        Merged MeshData and a map of primitive_id -> (start_vertex, end_vertex).
    """
    all_positions = []
    all_normals = []
    all_indices = []
    prim_ranges: dict[str, tuple[int, int]] = {}
    vertex_offset = 0

    for prim in mesh.primitives:
        md = tessellate_primitive(prim, profile)
        n_verts = len(md.positions)

        prim_ranges[prim.id] = (vertex_offset, vertex_offset + n_verts)

        all_positions.append(md.positions)
        all_normals.append(md.normals)
        all_indices.append(md.indices + vertex_offset)

        vertex_offset += n_verts

    if not all_positions:
        return MeshData(
            positions=np.zeros((0, 3), dtype=np.float64),
            normals=np.zeros((0, 3), dtype=np.float64),
            indices=np.zeros(0, dtype=np.uint32),
        ), prim_ranges

    return MeshData(
        positions=np.concatenate(all_positions, axis=0),
        normals=np.concatenate(all_normals, axis=0),
        indices=np.concatenate(all_indices, axis=0),
    ), prim_ranges


def _apply_transform(mesh_data: MeshData, primitive: Primitive) -> MeshData:
    """Apply translation and rotation to mesh data."""
    if primitive.transform is None:
        return mesh_data

    positions = mesh_data.positions.copy()
    normals = mesh_data.normals.copy()

    # Apply rotation first — prefer rotation_quat (v0.12+), fall back to rotation_euler
    if primitive.transform.rotation_quat is not None:
        qx, qy, qz, qw = primitive.transform.rotation_quat
        rot = _quat_to_matrix(qx, qy, qz, qw)
        positions = (rot @ positions.T).T
        normals = (rot @ normals.T).T
    elif primitive.transform.rotation_euler is not None:
        rx, ry, rz = primitive.transform.rotation_euler
        rot = _euler_to_matrix(rx, ry, rz)
        positions = (rot @ positions.T).T
        normals = (rot @ normals.T).T

    # Then translation
    if primitive.transform.translation is not None:
        tx, ty, tz = primitive.transform.translation
        positions = positions + np.array([tx, ty, tz], dtype=np.float64)

    return MeshData(positions=positions, normals=normals, indices=mesh_data.indices)


def _euler_to_matrix(rx: float, ry: float, rz: float) -> np.ndarray:
    """Convert Euler angles (radians, XYZ order) to a 3x3 rotation matrix."""
    cx, sx = math.cos(rx), math.sin(rx)
    cy, sy = math.cos(ry), math.sin(ry)
    cz, sz = math.cos(rz), math.sin(rz)

    # Rotation order: X then Y then Z
    Rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]], dtype=np.float64)
    Ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]], dtype=np.float64)
    Rz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]], dtype=np.float64)

    return Rz @ Ry @ Rx


def _quat_to_matrix(qx: float, qy: float, qz: float, qw: float) -> np.ndarray:
    """Convert quaternion (x, y, z, w) to a 3x3 rotation matrix."""
    x2 = qx + qx
    y2 = qy + qy
    z2 = qz + qz
    xx = qx * x2
    xy = qx * y2
    xz = qx * z2
    yy = qy * y2
    yz = qy * z2
    zz = qz * z2
    wx = qw * x2
    wy = qw * y2
    wz = qw * z2

    return np.array(
        [
            [1 - (yy + zz), xy - wz, xz + wy],
            [xy + wz, 1 - (xx + zz), yz - wx],
            [xz - wy, yz + wx, 1 - (xx + yy)],
        ],
        dtype=np.float64,
    )


def _tessellate_box(dims: dict[str, float]) -> MeshData:
    """Box: 24 verts, 36 indices (6 faces x 4 verts, 12 tris)."""
    hx = dims.get("width", dims.get("x", 1.0)) / 2
    hy = dims.get("height", dims.get("y", 1.0)) / 2
    hz = dims.get("depth", dims.get("z", 1.0)) / 2

    # 6 faces, each with 4 vertices and a normal
    face_data = [
        # +X face
        ([(hx, -hy, -hz), (hx, hy, -hz), (hx, hy, hz), (hx, -hy, hz)], (1, 0, 0)),
        # -X face
        ([(-hx, -hy, hz), (-hx, hy, hz), (-hx, hy, -hz), (-hx, -hy, -hz)], (-1, 0, 0)),
        # +Y face
        (
            [(-hx, hy, -hz), (-hx, hy, hz), (hx, hy, hz), (hx, hy, -hz)],
            (0, 1, 0),
        ),  # top  (was wrong)
        # -Y face
        (
            [(-hx, -hy, hz), (-hx, -hy, -hz), (hx, -hy, -hz), (hx, -hy, hz)],
            (0, -1, 0),
        ),  # bottom  (was wrong)
        # +Z face
        ([(-hx, -hy, hz), (hx, -hy, hz), (hx, hy, hz), (-hx, hy, hz)], (0, 0, 1)),
        # -Z face
        ([(hx, -hy, -hz), (-hx, -hy, -hz), (-hx, hy, -hz), (hx, hy, -hz)], (0, 0, -1)),
    ]

    positions = []
    normals = []
    indices = []

    for i, (verts, normal) in enumerate(face_data):
        base = i * 4
        for v in verts:
            positions.append(v)
            normals.append(normal)
        # Two triangles per face
        indices.extend([base, base + 1, base + 2, base, base + 2, base + 3])

    return MeshData(
        positions=np.array(positions, dtype=np.float64),
        normals=np.array(normals, dtype=np.float64),
        indices=np.array(indices, dtype=np.uint32),
    )


def _tessellate_wedge(dims: dict[str, float]) -> MeshData:
    """Wedge: 18 verts, 24 indices (8 triangles, 5 faces).

    Right triangular prism extruded along Y. See spec v0.9 Section 4.2.
    """
    x = dims.get("x", 1.0)
    y = dims.get("y", 1.0)
    z = dims.get("z", 1.0)
    hx = x / 2
    hy = y / 2
    hz = z / 2

    # Conceptual vertices
    v0 = (-hx, -hy, -hz)
    v1 = (+hx, -hy, -hz)
    v2 = (-hx, -hy, +hz)
    v3 = (-hx, +hy, -hz)
    v4 = (+hx, +hy, -hz)
    v5 = (-hx, +hy, +hz)

    # Slope normal: normalize(z, 0, x)
    slope_len = math.sqrt(z * z + x * x)
    slope_normal = (z / slope_len, 0.0, x / slope_len)

    # Face definitions: (local_verts, normal, local_indices)
    faces = [
        # -z face (rect, 4 verts)
        ([v0, v1, v4, v3], (0.0, 0.0, -1.0), [(0, 2, 1), (0, 3, 2)]),
        # -x face (rect, 4 verts)
        ([v0, v3, v5, v2], (-1.0, 0.0, 0.0), [(0, 2, 3), (0, 1, 2)]),
        # slope face (rect, 4 verts)
        ([v1, v2, v5, v4], slope_normal, [(0, 2, 1), (0, 3, 2)]),
        # -y face (tri, 3 verts)
        ([v0, v1, v2], (0.0, -1.0, 0.0), [(0, 1, 2)]),
        # +y face (tri, 3 verts)
        ([v3, v5, v4], (0.0, 1.0, 0.0), [(0, 1, 2)]),
    ]

    positions = []
    normals = []
    indices = []
    base = 0

    for verts, normal, local_indices in faces:
        for v in verts:
            positions.append(v)
            normals.append(normal)
        for tri in local_indices:
            indices.extend([base + tri[0], base + tri[1], base + tri[2]])
        base += len(verts)

    return MeshData(
        positions=np.array(positions, dtype=np.float64),
        normals=np.array(normals, dtype=np.float64),
        indices=np.array(indices, dtype=np.uint32),
    )


def _tessellate_sphere(dims: dict[str, float]) -> MeshData:
    """UV sphere: 16 latitude x 32 longitude."""
    radius = dims.get("radius", 0.5)
    n_lat = 16
    n_lon = 32

    positions = []
    normals = []
    indices = []

    # Generate vertices
    for lat in range(n_lat + 1):
        theta = math.pi * lat / n_lat
        sin_theta = math.sin(theta)
        cos_theta = math.cos(theta)

        for lon in range(n_lon + 1):
            phi = 2.0 * math.pi * lon / n_lon
            sin_phi = math.sin(phi)
            cos_phi = math.cos(phi)

            nx = sin_theta * cos_phi
            ny = cos_theta
            nz = sin_theta * sin_phi

            positions.append((radius * nx, radius * ny, radius * nz))
            normals.append((nx, ny, nz))

    # Generate indices
    for lat in range(n_lat):
        for lon in range(n_lon):
            current = lat * (n_lon + 1) + lon
            next_row = current + n_lon + 1

            indices.extend([current, next_row, current + 1])
            indices.extend([current + 1, next_row, next_row + 1])

    return MeshData(
        positions=np.array(positions, dtype=np.float64),
        normals=np.array(normals, dtype=np.float64),
        indices=np.array(indices, dtype=np.uint32),
    )


def _tessellate_cylinder(dims: dict[str, float]) -> MeshData:
    """Cylinder: 32 radial segments x 1 height + caps."""
    radius = dims.get("radius", 0.5)
    height = dims.get("height", 1.0)
    n_radial = 32

    half_h = height / 2
    positions = []
    normals = []
    indices = []

    # Side vertices: 2 rings of n_radial+1 verts
    for row in range(2):
        y = half_h if row == 0 else -half_h
        for seg in range(n_radial + 1):
            angle = 2.0 * math.pi * seg / n_radial
            nx = math.cos(angle)
            nz = math.sin(angle)
            positions.append((radius * nx, y, radius * nz))
            normals.append((nx, 0.0, nz))

    # Side indices
    for seg in range(n_radial):
        top = seg
        bottom = seg + n_radial + 1
        indices.extend([top, bottom, top + 1])
        indices.extend([top + 1, bottom, bottom + 1])

    # Top cap
    cap_center_top = len(positions)
    positions.append((0, half_h, 0))
    normals.append((0, 1, 0))
    cap_start_top = len(positions)
    for seg in range(n_radial + 1):
        angle = 2.0 * math.pi * seg / n_radial
        positions.append((radius * math.cos(angle), half_h, radius * math.sin(angle)))
        normals.append((0, 1, 0))
    for seg in range(n_radial):
        indices.extend([cap_center_top, cap_start_top + seg, cap_start_top + seg + 1])

    # Bottom cap
    cap_center_bot = len(positions)
    positions.append((0, -half_h, 0))
    normals.append((0, -1, 0))
    cap_start_bot = len(positions)
    for seg in range(n_radial + 1):
        angle = 2.0 * math.pi * seg / n_radial
        positions.append((radius * math.cos(angle), -half_h, radius * math.sin(angle)))
        normals.append((0, -1, 0))
    for seg in range(n_radial):
        indices.extend([cap_center_bot, cap_start_bot + seg, cap_start_bot + seg + 1])

    return MeshData(
        positions=np.array(positions, dtype=np.float64),
        normals=np.array(normals, dtype=np.float64),
        indices=np.array(indices, dtype=np.uint32),
    )


def _tessellate_capsule(dims: dict[str, float]) -> MeshData:
    """Capsule: cylinder (8 height segments) + hemispheres (8 rings each)."""
    radius = dims.get("radius", 0.25)
    height = dims.get("height", 1.0)
    n_radial = 32
    n_height = 8
    n_hemisphere_rings = 8

    half_h = height / 2
    positions = []
    normals = []
    indices = []

    # Top hemisphere (from pole down to equator)
    for ring in range(n_hemisphere_rings + 1):
        theta = (math.pi / 2) * ring / n_hemisphere_rings  # 0 to pi/2
        sin_theta = math.sin(theta)
        cos_theta = math.cos(theta)
        y = half_h + radius * cos_theta

        for seg in range(n_radial + 1):
            phi = 2.0 * math.pi * seg / n_radial
            nx = sin_theta * math.cos(phi)
            nz = sin_theta * math.sin(phi)
            ny = cos_theta
            positions.append((radius * nx, y, radius * nz))
            normals.append((nx, ny, nz))

    # Cylinder section (from top to bottom, n_height+1 rows)
    for row in range(n_height + 1):
        y = half_h - height * row / n_height
        for seg in range(n_radial + 1):
            phi = 2.0 * math.pi * seg / n_radial
            nx = math.cos(phi)
            nz = math.sin(phi)
            positions.append((radius * nx, y, radius * nz))
            normals.append((nx, 0.0, nz))

    # Bottom hemisphere (from equator down to pole)
    for ring in range(1, n_hemisphere_rings + 1):
        theta = (math.pi / 2) + (math.pi / 2) * ring / n_hemisphere_rings  # pi/2 to pi
        sin_theta = math.sin(theta)
        cos_theta = math.cos(theta)
        y = -half_h + radius * cos_theta

        for seg in range(n_radial + 1):
            phi = 2.0 * math.pi * seg / n_radial
            nx = sin_theta * math.cos(phi)
            nz = sin_theta * math.sin(phi)
            ny = cos_theta
            positions.append((radius * nx, y, radius * nz))
            normals.append((nx, ny, nz))

    # Generate indices for all rows
    total_rows = (n_hemisphere_rings + 1) + (n_height + 1) + n_hemisphere_rings
    for row in range(total_rows - 1):
        for seg in range(n_radial):
            current = row * (n_radial + 1) + seg
            next_row = current + n_radial + 1
            indices.extend([current, next_row, current + 1])
            indices.extend([current + 1, next_row, next_row + 1])

    return MeshData(
        positions=np.array(positions, dtype=np.float64),
        normals=np.array(normals, dtype=np.float64),
        indices=np.array(indices, dtype=np.uint32),
    )
