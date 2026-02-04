"""Inspection diagnostics for Rigy geometry."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

import numpy as np

from rigy.models import Primitive, RigySpec
from rigy.tessellation import tessellate_primitive

IMPLICIT_DEFAULT_MATERIAL = "implicit_default"

_FACE_LAYOUTS: dict[str, list[tuple[str, int]]] = {
    "box": [("+x", 4), ("-x", 4), ("+y", 4), ("-y", 4), ("+z", 4), ("-z", 4)],
    "wedge": [("-z", 4), ("-x", 4), ("slope", 4), ("-y", 3), ("+y", 3)],
}


@dataclass(frozen=True)
class PrimitiveDiagnostics:
    primitive: Primitive
    aabb_min: np.ndarray
    aabb_max: np.ndarray
    center: np.ndarray
    extents: np.ndarray
    positions: np.ndarray
    normals: np.ndarray


def inspect_spec(
    spec: RigySpec,
    *,
    selected_primitive_ids: set[str] | None = None,
    pairwise_gaps: bool = False,
    include_intent_checks: bool = False,
) -> dict[str, object]:
    """Inspect a validated spec and return deterministic diagnostics."""
    all_entries: list[PrimitiveDiagnostics] = []
    for mesh in spec.meshes:
        for primitive in mesh.primitives:
            mesh_data = tessellate_primitive(primitive, spec.tessellation_profile)
            if len(mesh_data.positions) == 0:
                aabb_min = np.zeros(3, dtype=np.float64)
                aabb_max = np.zeros(3, dtype=np.float64)
            else:
                aabb_min = mesh_data.positions.min(axis=0).astype(np.float64)
                aabb_max = mesh_data.positions.max(axis=0).astype(np.float64)
            center = (aabb_min + aabb_max) * 0.5
            extents = aabb_max - aabb_min
            all_entries.append(
                PrimitiveDiagnostics(
                    primitive=primitive,
                    aabb_min=aabb_min,
                    aabb_max=aabb_max,
                    center=center,
                    extents=extents,
                    positions=mesh_data.positions,
                    normals=mesh_data.normals,
                )
            )

    selected_entries = _select_entries(all_entries, selected_primitive_ids)

    summary = {
        "rigy_version": spec.version,
        "mesh_count": len(spec.meshes),
        "primitive_count": len(all_entries),
        "bounds": _asset_bounds(all_entries),
    }

    primitives = [_primitive_payload(entry) for entry in selected_entries]
    faces = _face_payloads(selected_entries, spec.version)

    result: dict[str, object] = {
        "summary": summary,
        "primitives": primitives,
        "faces": faces,
    }

    if pairwise_gaps:
        result["pairs"] = _pairwise_payloads(selected_entries)
    if include_intent_checks:
        # Intent checks are tooling-only and optional; when no checks are
        # configured we still emit a deterministic empty array.
        result["checks"] = []
    return result


def validate_selected_primitive_ids(spec: RigySpec, selected_ids: set[str]) -> list[str]:
    """Return sorted unknown primitive ids."""
    known_ids = {primitive.id for mesh in spec.meshes for primitive in mesh.primitives}
    return sorted(pid for pid in selected_ids if pid not in known_ids)


def has_failed_intent_checks(payload: dict[str, object]) -> bool:
    """Return True when any emitted check has pass=false."""
    checks_obj = payload.get("checks")
    if not isinstance(checks_obj, list):
        return False
    for check in checks_obj:
        if isinstance(check, dict) and check.get("pass") is False:
            return True
    return False


def render_text(payload: dict[str, object], expanded_yaml: str | None = None) -> str:
    """Render human-readable text output for inspect diagnostics."""
    lines: list[str] = []

    summary = payload["summary"]
    bounds = summary["bounds"]
    lines.append("summary:")
    lines.append(f"  rigy_version: {summary['rigy_version']}")
    lines.append(f"  mesh_count: {summary['mesh_count']}")
    lines.append(f"  primitive_count: {summary['primitive_count']}")
    lines.append(f"  bounds.min: {_fmt_vec(bounds['min'])}")
    lines.append(f"  bounds.max: {_fmt_vec(bounds['max'])}")

    lines.append("primitives:")
    primitives = payload.get("primitives", [])
    if isinstance(primitives, list) and primitives:
        for primitive in primitives:
            lines.append(f"  - id: {primitive['id']}")
            lines.append(f"    type: {primitive['type']}")
            lines.append(f"    material: {primitive['material']}")
            lines.append(f"    aabb.min: {_fmt_vec(primitive['aabb']['min'])}")
            lines.append(f"    aabb.max: {_fmt_vec(primitive['aabb']['max'])}")
            lines.append(f"    center: {_fmt_vec(primitive['center'])}")
            lines.append(f"    extents: {_fmt_vec(primitive['extents'])}")
    else:
        lines.append("  []")

    faces = payload.get("faces", [])
    lines.append("faces:")
    if isinstance(faces, list) and faces:
        for face in faces:
            lines.append(
                f"  - primitive_id: {face['primitive_id']} surface_key: {face['surface_key']}"
            )
            lines.append(f"    normal: {_fmt_vec(face['normal'])}")
            lines.append(f"    plane.n: {_fmt_vec(face['plane']['n'])}")
            lines.append(f"    plane.d: {face['plane']['d']:.6g}")
    else:
        lines.append("  []")

    pairs = payload.get("pairs")
    if isinstance(pairs, list):
        lines.append("pairs:")
        if pairs:
            for pair in pairs:
                gap = pair["gap"]
                lines.append(f"  - a: {pair['a']} b: {pair['b']}")
                lines.append(
                    "    gap: "
                    f"x={gap['x']:.6g}, y={gap['y']:.6g}, z={gap['z']:.6g}, "
                    f"overall={gap['overall']:.6g}"
                )
        else:
            lines.append("  []")

    checks = payload.get("checks")
    if isinstance(checks, list):
        lines.append("checks:")
        lines.append("  []" if not checks else f"  {checks}")

    if expanded_yaml is not None:
        lines.append("expanded_yaml:")
        lines.append(expanded_yaml.rstrip("\n"))

    return "\n".join(lines) + "\n"


def _select_entries(
    entries: list[PrimitiveDiagnostics],
    selected_primitive_ids: set[str] | None,
) -> list[PrimitiveDiagnostics]:
    if not selected_primitive_ids:
        return entries
    return [entry for entry in entries if entry.primitive.id in selected_primitive_ids]


def _asset_bounds(entries: list[PrimitiveDiagnostics]) -> dict[str, list[float]]:
    if not entries:
        zeros = [0.0, 0.0, 0.0]
        return {"min": zeros, "max": zeros}

    min_bounds = np.minimum.reduce([entry.aabb_min for entry in entries])
    max_bounds = np.maximum.reduce([entry.aabb_max for entry in entries])
    return {
        "min": _to_list(min_bounds),
        "max": _to_list(max_bounds),
    }


def _primitive_payload(entry: PrimitiveDiagnostics) -> dict[str, object]:
    return {
        "id": entry.primitive.id,
        "type": entry.primitive.type,
        "material": entry.primitive.material or IMPLICIT_DEFAULT_MATERIAL,
        "aabb": {"min": _to_list(entry.aabb_min), "max": _to_list(entry.aabb_max)},
        "center": _to_list(entry.center),
        "extents": _to_list(entry.extents),
    }


def _face_payloads(entries: list[PrimitiveDiagnostics], version: str) -> list[dict[str, object]]:
    if not _supports_surface_keys(version):
        return []

    faces: list[dict[str, object]] = []
    for entry in entries:
        face_layout = _FACE_LAYOUTS.get(entry.primitive.type)
        if face_layout is None:
            continue

        offset = 0
        for surface_key, vertex_count in face_layout:
            normal = _normalize(entry.normals[offset])
            point = entry.positions[offset]
            d = -float(np.dot(normal, point))
            faces.append(
                {
                    "primitive_id": entry.primitive.id,
                    "surface_key": surface_key,
                    "normal": _to_list(normal),
                    "plane": {"n": _to_list(normal), "d": d},
                }
            )
            offset += vertex_count
    return faces


def _pairwise_payloads(entries: list[PrimitiveDiagnostics]) -> list[dict[str, object]]:
    pairs: list[dict[str, object]] = []
    for a_entry, b_entry in combinations(entries, 2):
        gap_x = _axis_gap(a_entry.aabb_min[0], a_entry.aabb_max[0], b_entry.aabb_min[0], b_entry.aabb_max[0])
        gap_y = _axis_gap(a_entry.aabb_min[1], a_entry.aabb_max[1], b_entry.aabb_min[1], b_entry.aabb_max[1])
        gap_z = _axis_gap(a_entry.aabb_min[2], a_entry.aabb_max[2], b_entry.aabb_min[2], b_entry.aabb_max[2])
        pairs.append(
            {
                "a": a_entry.primitive.id,
                "b": b_entry.primitive.id,
                "gap": {
                    "x": gap_x,
                    "y": gap_y,
                    "z": gap_z,
                    "overall": max(gap_x, gap_y, gap_z),
                },
            }
        )
    return pairs


def _axis_gap(a_min: float, a_max: float, b_min: float, b_max: float) -> float:
    if a_max < b_min:
        return float(b_min - a_max)
    if b_max < a_min:
        return float(a_min - b_max)
    overlap = min(a_max, b_max) - max(a_min, b_min)
    return float(-overlap)


def _supports_surface_keys(version: str) -> bool:
    try:
        major_s, minor_s = version.split(".")
        major = int(major_s)
        minor = int(minor_s)
    except Exception:
        return False
    return (major, minor) >= (0, 9)


def _normalize(vec: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(vec)
    if norm == 0:
        return vec.astype(np.float64)
    return (vec / norm).astype(np.float64)


def _to_list(vec: np.ndarray) -> list[float]:
    return [float(v) for v in vec.tolist()]


def _fmt_vec(vec: object) -> str:
    if not isinstance(vec, list):
        return str(vec)
    return "[" + ", ".join(f"{float(v):.6g}" for v in vec) + "]"
