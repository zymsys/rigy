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
    mesh_material: str | None = None


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
                    mesh_material=mesh.material,
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
        "inspect_schema_version": 1,
        "summary": summary,
        "primitives": primitives,
        "faces": faces,
    }

    if pairwise_gaps:
        result["pairs"] = _pairwise_payloads(selected_entries)
    if include_intent_checks:
        gc = spec.geometry_checks
        alignment_checks: list[dict] = []
        if isinstance(gc, dict):
            alignment_list = gc.get("alignment", [])
            if isinstance(alignment_list, list):
                alignment_checks = alignment_list

        feature_map = {e.primitive.id: _compute_derived_features(e) for e in all_entries}

        checks: list[dict] = []
        for check_def in alignment_checks:
            checks.append(_evaluate_alignment_check(check_def, feature_map))
        result["checks"] = checks
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

    isv = payload.get("inspect_schema_version")
    if isv is not None:
        lines.append(f"inspect_schema_version: {isv}")

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
        if not checks:
            lines.append("  []")
        else:
            for chk in checks:
                if isinstance(chk, dict):
                    chk_label = chk.get("label", "")
                    chk_type = chk.get("check", "")
                    chk_pass = chk.get("pass")
                    pass_str = "null" if chk_pass is None else str(chk_pass).lower()
                    lines.append(f"  - check: {chk_type}")
                    lines.append(f"    label: {chk_label}")
                    lines.append(f"    pass: {pass_str}")
                    if "error" in chk:
                        lines.append(f"    error: {chk['error']}")
                    if "cross_magnitude" in chk:
                        lines.append(f"    cross_magnitude: {chk['cross_magnitude']:.6g}")
                    if "distance" in chk:
                        lines.append(f"    distance: {chk['distance']:.6g}")
                else:
                    lines.append(f"  - {chk}")

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
        "material": entry.primitive.material or entry.mesh_material or IMPLICIT_DEFAULT_MATERIAL,
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
        gap_x = _axis_gap(
            a_entry.aabb_min[0], a_entry.aabb_max[0], b_entry.aabb_min[0], b_entry.aabb_max[0]
        )
        gap_y = _axis_gap(
            a_entry.aabb_min[1], a_entry.aabb_max[1], b_entry.aabb_min[1], b_entry.aabb_max[1]
        )
        gap_z = _axis_gap(
            a_entry.aabb_min[2], a_entry.aabb_max[2], b_entry.aabb_min[2], b_entry.aabb_max[2]
        )
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


# ---------------------------------------------------------------------------
# Derived features & alignment checks
# ---------------------------------------------------------------------------


def _compute_derived_features(entry: PrimitiveDiagnostics) -> dict[str, dict]:
    """Compute named derived features from tessellated geometry."""
    features: dict[str, dict] = {}
    ptype = entry.primitive.type

    if ptype == "wedge":
        face_layout = _FACE_LAYOUTS["wedge"]
        offset = 0
        for surface_key, vertex_count in face_layout:
            if surface_key == "slope":
                normal = _normalize(entry.normals[offset])
                point = entry.positions[offset].astype(np.float64)
                features["slope_face"] = {
                    "type": "face",
                    "normal": normal,
                    "point": point,
                }
            offset += vertex_count

        # +y face: triangle at vertices 15,16,17
        py_start = sum(vc for _, vc in face_layout[:-1])  # 4+4+4+3 = 15
        py_verts = entry.positions[py_start : py_start + 3]
        apex_point = np.mean(py_verts, axis=0).astype(np.float64)
        features["apex"] = {"type": "point", "point": apex_point}

        # ridge: the top edge on -x face (v3 to v5)
        # -x face starts at offset 4, vertices are [v0, v3, v5, v2]
        # v3 is at buffer index 5, v5 is at buffer index 6
        mx_start = 4  # after -z face (4 verts)
        v3_world = entry.positions[mx_start + 1].astype(np.float64)
        v5_world = entry.positions[mx_start + 2].astype(np.float64)
        ridge_dir = _normalize(v5_world - v3_world)
        ridge_point = ((v3_world + v5_world) / 2.0).astype(np.float64)
        features["ridge"] = {
            "type": "line",
            "point": ridge_point,
            "direction": ridge_dir,
        }

    if ptype in ("box", "wedge"):
        face_layout = _FACE_LAYOUTS[ptype]
        offset = 0
        for surface_key, vertex_count in face_layout:
            verts = entry.positions[offset : offset + vertex_count]
            center = np.mean(verts, axis=0).astype(np.float64)
            normal = _normalize(entry.normals[offset])
            features[surface_key] = {
                "type": "face",
                "normal": normal,
                "point": center,
            }
            offset += vertex_count

    return features


def _resolve_feature_ref(
    ref: str,
    feature_map: dict[str, dict[str, dict]],
) -> dict | None:
    """Resolve 'primitive_id.feature_name' to a feature dict."""
    parts = ref.split(".", 1)
    if len(parts) != 2:
        return None
    prim_id, feat_name = parts
    prim_features = feature_map.get(prim_id)
    if prim_features is None:
        return None
    return prim_features.get(feat_name)


def _evaluate_alignment_check(
    check_def: dict,
    feature_map: dict[str, dict[str, dict]],
) -> dict:
    check_type = check_def.get("check")
    label = check_def.get("label", "")

    if check_type == "normal_parallel":
        return _check_normal_parallel(check_def, feature_map, label)
    elif check_type == "point_on_line":
        return _check_point_on_line(check_def, feature_map, label)
    else:
        return {
            "check": check_type,
            "label": label,
            "pass": None,
            "error": f"unknown check type: {check_type}",
        }


def _check_normal_parallel(
    check_def: dict,
    feature_map: dict[str, dict[str, dict]],
    label: str,
) -> dict:
    tolerance = float(check_def.get("tolerance", 1e-6))
    a_ref = check_def.get("a", "")
    b_ref = check_def.get("b", "")

    a_feat = _resolve_feature_ref(a_ref, feature_map)
    b_feat = _resolve_feature_ref(b_ref, feature_map)

    if a_feat is None:
        return {
            "check": "normal_parallel",
            "label": label,
            "pass": None,
            "error": f"cannot resolve feature: {a_ref}",
        }
    if b_feat is None:
        return {
            "check": "normal_parallel",
            "label": label,
            "pass": None,
            "error": f"cannot resolve feature: {b_ref}",
        }

    if a_feat.get("type") != "face" or b_feat.get("type") != "face":
        return {
            "check": "normal_parallel",
            "label": label,
            "pass": None,
            "error": "normal_parallel requires two face features",
        }

    n_a = np.asarray(a_feat["normal"], dtype=np.float64)
    n_b = np.asarray(b_feat["normal"], dtype=np.float64)
    cross_mag = float(np.linalg.norm(np.cross(n_a, n_b)))

    return {
        "check": "normal_parallel",
        "label": label,
        "pass": cross_mag < tolerance,
        "cross_magnitude": cross_mag,
    }


def _check_point_on_line(
    check_def: dict,
    feature_map: dict[str, dict[str, dict]],
    label: str,
) -> dict:
    tolerance = float(check_def.get("tolerance", 1e-6))
    point_ref = check_def.get("point", "")
    line_ref = check_def.get("line", "")

    point_feat = _resolve_feature_ref(point_ref, feature_map)
    line_feat = _resolve_feature_ref(line_ref, feature_map)

    if point_feat is None:
        return {
            "check": "point_on_line",
            "label": label,
            "pass": None,
            "error": f"cannot resolve feature: {point_ref}",
        }
    if line_feat is None:
        return {
            "check": "point_on_line",
            "label": label,
            "pass": None,
            "error": f"cannot resolve feature: {line_ref}",
        }

    if point_feat.get("type") != "point":
        return {
            "check": "point_on_line",
            "label": label,
            "pass": None,
            "error": f"expected point feature, got {point_feat.get('type')}",
        }
    if line_feat.get("type") != "line":
        return {
            "check": "point_on_line",
            "label": label,
            "pass": None,
            "error": f"expected line feature, got {line_feat.get('type')}",
        }

    pt = np.asarray(point_feat["point"], dtype=np.float64)
    line_pt = np.asarray(line_feat["point"], dtype=np.float64)
    line_dir = np.asarray(line_feat["direction"], dtype=np.float64)

    dir_len = float(np.linalg.norm(line_dir))
    if dir_len < 1e-12:
        return {
            "check": "point_on_line",
            "label": label,
            "pass": None,
            "error": "line direction has zero length",
        }

    diff = pt - line_pt
    distance = float(np.linalg.norm(np.cross(line_dir, diff))) / dir_len

    return {
        "check": "point_on_line",
        "label": label,
        "pass": distance < tolerance,
        "distance": distance,
    }
