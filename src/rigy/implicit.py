"""Implicit surface tessellation via marching cubes."""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np

from rigy.models import FieldOperator, Primitive
from rigy.tessellation import MeshData, _euler_to_matrix, _quat_to_matrix

# --- Lookup tables (loaded once at import time) ---

_TABLES_PATH = (
    Path(__file__).parent.parent.parent / "spec" / "constants" / "marching_cubes@1_tables.bin"
)
_raw = np.fromfile(str(_TABLES_PATH), dtype="<i4")
EDGE_TABLE: np.ndarray = _raw[:256].copy()
TRI_TABLE: np.ndarray = _raw[256:].reshape(256, 16).copy()

# Edge-to-corner mapping (standard MC convention)
_EDGE_CORNERS = [
    (0, 1),
    (1, 2),
    (2, 3),
    (3, 0),
    (4, 5),
    (5, 6),
    (6, 7),
    (7, 4),
    (0, 4),
    (1, 5),
    (2, 6),
    (3, 7),
]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def tessellate_implicit_surface(primitive: Primitive) -> MeshData:
    """Tessellate an implicit_surface primitive via marching cubes."""
    domain = primitive.domain
    iso = primitive.iso
    ops = primitive.ops

    aabb_min = np.array(domain.aabb.min, dtype=np.float64)
    aabb_max = np.array(domain.aabb.max, dtype=np.float64)
    nx, ny, nz = domain.grid.nx, domain.grid.ny, domain.grid.nz

    # Sample scalar field on grid
    field = _sample_field_on_grid(aabb_min, aabb_max, nx, ny, nz, ops)

    # Extract surface via marching cubes
    positions, indices = _marching_cubes(field, aabb_min, aabb_max, nx, ny, nz, iso)

    if len(positions) == 0:
        return MeshData(
            positions=np.zeros((0, 3), dtype=np.float64),
            normals=np.zeros((0, 3), dtype=np.float64),
            indices=np.zeros(0, dtype=np.uint32),
        )

    # Generate normals via central differences
    normals = _compute_normals(positions, aabb_min, aabb_max, nx, ny, nz, ops)

    return MeshData(
        positions=positions,
        normals=normals,
        indices=indices,
    )


# ---------------------------------------------------------------------------
# Grid sampling
# ---------------------------------------------------------------------------


def _sample_field_on_grid(
    aabb_min: np.ndarray,
    aabb_max: np.ndarray,
    nx: int,
    ny: int,
    nz: int,
    ops: list[FieldOperator],
) -> np.ndarray:
    """Evaluate the total scalar field at all grid points.

    Returns array of shape (nz, ny, nx).
    """
    x = np.linspace(aabb_min[0], aabb_max[0], nx)
    y = np.linspace(aabb_min[1], aabb_max[1], ny)
    z = np.linspace(aabb_min[2], aabb_max[2], nz)

    # Meshgrid with ij indexing gives (nz, ny, nx) shape.
    # Ravel order (C) is z-outer, y-middle, x-inner — matching spec.
    zz, yy, xx = np.meshgrid(z, y, x, indexing="ij")
    points = np.column_stack([xx.ravel(), yy.ravel(), zz.ravel()])

    total = _evaluate_field_batch(points, ops)
    return total.reshape(nz, ny, nx)


# ---------------------------------------------------------------------------
# Field evaluation (vectorised)
# ---------------------------------------------------------------------------


def _evaluate_field_batch(points: np.ndarray, ops: list[FieldOperator]) -> np.ndarray:
    """Evaluate the total scalar field at *points* (N×3)."""
    total = np.zeros(len(points), dtype=np.float64)
    for op in ops:
        p_local = _transform_to_local(points, op.transform)
        value = _field_func_batch(op.field, p_local, op)
        if op.op == "subtract":
            value = -value
        total += value
    return total


def _transform_to_local(points: np.ndarray, transform: object | None) -> np.ndarray:
    """Convert world-space points to operator-local space."""
    if transform is None:
        return points

    p = points.copy()

    # Inverse: p_local = R^T @ (p_world - t)
    if transform.translation is not None:
        p = p - np.array(transform.translation, dtype=np.float64)

    rot = None
    if transform.rotation_quat is not None:
        qx, qy, qz, qw = transform.rotation_quat
        rot = _quat_to_matrix(qx, qy, qz, qw)
    elif transform.rotation_axis_angle is not None:
        rot = _axis_angle_to_matrix(transform.rotation_axis_angle)
    elif transform.rotation_euler is not None:
        rx, ry, rz = transform.rotation_euler
        rot = _euler_to_matrix(rx, ry, rz)

    if rot is not None:
        p = (rot.T @ p.T).T

    return p


def _axis_angle_to_matrix(aa: object) -> np.ndarray:
    """Convert RotationAxisAngle to a 3×3 rotation matrix (Rodrigues)."""
    angle = math.radians(aa.degrees)
    axis = np.array(aa.axis, dtype=np.float64)
    n = np.linalg.norm(axis)
    if n > 0:
        axis = axis / n
    c = math.cos(angle)
    s = math.sin(angle)
    t = 1.0 - c
    x, y, z = axis
    return np.array(
        [
            [t * x * x + c, t * x * y - s * z, t * x * z + s * y],
            [t * y * x + s * z, t * y * y + c, t * y * z - s * x],
            [t * z * x - s * y, t * z * y + s * x, t * z * z + c],
        ],
        dtype=np.float64,
    )


def _field_func_batch(field_id: str, points: np.ndarray, op: FieldOperator) -> np.ndarray:
    """Dispatch to the correct field function."""
    if field_id == "metaball_sphere@1":
        return _metaball_sphere_batch(points, op.radius, op.strength)
    elif field_id == "metaball_capsule@1":
        return _metaball_capsule_batch(points, op.radius, op.height, op.strength)
    elif field_id == "sdf_sphere@1":
        return _sdf_sphere_batch(points, op.radius, op.strength)
    elif field_id == "sdf_capsule@1":
        return _sdf_capsule_batch(points, op.radius, op.height, op.strength)
    else:
        raise ValueError(f"Unknown field: {field_id!r}")


# --- metaball_sphere@1 ---


def _metaball_sphere_batch(points: np.ndarray, radius: float, strength: float) -> np.ndarray:
    r = np.linalg.norm(points, axis=1)
    result = np.zeros(len(points), dtype=np.float64)
    mask = r < radius
    t = 1.0 - r[mask] / radius
    result[mask] = strength * t * t
    return result


# --- metaball_capsule@1 ---


def _metaball_capsule_batch(
    points: np.ndarray, radius: float, height: float, strength: float
) -> np.ndarray:
    half_h = height / 2.0
    # Capsule axis along Y: A=(0,-h/2,0), B=(0,+h/2,0)
    t_param = np.clip((points[:, 1] + half_h) / height, 0.0, 1.0)
    qy = -half_h + t_param * height
    q = np.zeros_like(points)
    q[:, 1] = qy
    d = np.linalg.norm(points - q, axis=1)
    result = np.zeros(len(points), dtype=np.float64)
    mask = d < radius
    t = 1.0 - d[mask] / radius
    result[mask] = strength * t * t
    return result


# --- sdf_sphere@1 ---


def _sdf_sphere_batch(points: np.ndarray, radius: float, strength: float) -> np.ndarray:
    r = np.linalg.norm(points, axis=1)
    d = r - radius
    result = np.zeros(len(points), dtype=np.float64)
    mask_full = d <= -radius
    result[mask_full] = strength
    mask_ramp = (~mask_full) & (d < radius)
    result[mask_ramp] = strength * (1.0 - d[mask_ramp] / radius) / 2.0
    return result


# --- sdf_capsule@1 ---


def _sdf_capsule_batch(
    points: np.ndarray, radius: float, height: float, strength: float
) -> np.ndarray:
    half_h = height / 2.0
    t_param = np.clip((points[:, 1] + half_h) / height, 0.0, 1.0)
    qy = -half_h + t_param * height
    q = np.zeros_like(points)
    q[:, 1] = qy
    d_cap = np.linalg.norm(points - q, axis=1)
    d = d_cap - radius
    result = np.zeros(len(points), dtype=np.float64)
    mask_full = d <= -radius
    result[mask_full] = strength
    mask_ramp = (~mask_full) & (d < radius)
    result[mask_ramp] = strength * (1.0 - d[mask_ramp] / radius) / 2.0
    return result


# ---------------------------------------------------------------------------
# Marching Cubes extraction
# ---------------------------------------------------------------------------


def _marching_cubes(
    field: np.ndarray,
    aabb_min: np.ndarray,
    aabb_max: np.ndarray,
    nx: int,
    ny: int,
    nz: int,
    iso: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Extract isosurface triangles from the scalar field."""
    x_coords = np.linspace(aabb_min[0], aabb_max[0], nx)
    y_coords = np.linspace(aabb_min[1], aabb_max[1], ny)
    z_coords = np.linspace(aabb_min[2], aabb_max[2], nz)

    vertices: list[tuple[float, float, float]] = []
    vertex_count = 0

    for cz in range(nz - 1):
        for cy in range(ny - 1):
            for cx in range(nx - 1):
                # Corner values — c0..c7 per spec
                vals = [
                    field[cz, cy, cx],  # c0
                    field[cz, cy, cx + 1],  # c1
                    field[cz, cy + 1, cx + 1],  # c2
                    field[cz, cy + 1, cx],  # c3
                    field[cz + 1, cy, cx],  # c4
                    field[cz + 1, cy, cx + 1],  # c5
                    field[cz + 1, cy + 1, cx + 1],  # c6
                    field[cz + 1, cy + 1, cx],  # c7
                ]

                # Case index: bit i set if corner i >= iso
                case_index = 0
                for i in range(8):
                    if vals[i] >= iso:
                        case_index |= 1 << i

                edges = int(EDGE_TABLE[case_index])
                if edges == 0:
                    continue

                # Corner positions
                pos = [
                    (x_coords[cx], y_coords[cy], z_coords[cz]),
                    (x_coords[cx + 1], y_coords[cy], z_coords[cz]),
                    (x_coords[cx + 1], y_coords[cy + 1], z_coords[cz]),
                    (x_coords[cx], y_coords[cy + 1], z_coords[cz]),
                    (x_coords[cx], y_coords[cy], z_coords[cz + 1]),
                    (x_coords[cx + 1], y_coords[cy], z_coords[cz + 1]),
                    (x_coords[cx + 1], y_coords[cy + 1], z_coords[cz + 1]),
                    (x_coords[cx], y_coords[cy + 1], z_coords[cz + 1]),
                ]

                # Interpolate vertices on active edges
                edge_verts: list[tuple[float, float, float] | None] = [None] * 12
                for i in range(12):
                    if edges & (1 << i):
                        ca, cb = _EDGE_CORNERS[i]
                        va, vb = vals[ca], vals[cb]
                        pa, pb = pos[ca], pos[cb]
                        if va == vb:
                            t = 0.5
                        else:
                            t = (iso - va) / (vb - va)
                        edge_verts[i] = (
                            pa[0] + t * (pb[0] - pa[0]),
                            pa[1] + t * (pb[1] - pa[1]),
                            pa[2] + t * (pb[2] - pa[2]),
                        )

                # Emit triangles (per-cell, no welding)
                tri_row = TRI_TABLE[case_index]
                j = 0
                while j < 16 and tri_row[j] != -1:
                    vertices.append(edge_verts[tri_row[j]])
                    vertices.append(edge_verts[tri_row[j + 1]])
                    vertices.append(edge_verts[tri_row[j + 2]])
                    vertex_count += 3
                    j += 3

    if vertex_count == 0:
        return np.zeros((0, 3), dtype=np.float64), np.zeros(0, dtype=np.uint32)

    positions = np.array(vertices, dtype=np.float64)
    indices = np.arange(vertex_count, dtype=np.uint32)
    return positions, indices


# ---------------------------------------------------------------------------
# Normal generation (central differences)
# ---------------------------------------------------------------------------


def _compute_normals(
    positions: np.ndarray,
    aabb_min: np.ndarray,
    aabb_max: np.ndarray,
    nx: int,
    ny: int,
    nz: int,
    ops: list[FieldOperator],
) -> np.ndarray:
    """Compute outward-pointing normals via central differences of F."""
    n = len(positions)
    eps = (aabb_max - aabb_min) / np.array([nx - 1, ny - 1, nz - 1], dtype=np.float64)

    grad = np.zeros((n, 3), dtype=np.float64)

    for axis in range(3):
        offset = np.zeros(3, dtype=np.float64)
        offset[axis] = eps[axis]

        p_plus = np.clip(positions + offset, aabb_min, aabb_max)
        p_minus = np.clip(positions - offset, aabb_min, aabb_max)

        f_plus = _evaluate_field_batch(p_plus, ops)
        f_minus = _evaluate_field_batch(p_minus, ops)

        grad[:, axis] = f_plus - f_minus

    # Negate: gradient of F points inward, normals point outward
    normals = -grad

    # Normalize
    magnitudes = np.linalg.norm(normals, axis=1, keepdims=True)
    zero_mask = (magnitudes < 1e-30).ravel()
    magnitudes[zero_mask.reshape(-1, 1)] = 1.0  # avoid div-by-zero
    normals = normals / magnitudes
    normals[zero_mask] = [0.0, 1.0, 0.0]

    return normals
