"""Per-primitive weight to per-vertex glTF JOINTS_0/WEIGHTS_0 arrays."""

from __future__ import annotations

import json
import warnings
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from rigy.errors import ExportError, ValidationError
from rigy.models import Armature, Binding, Bone, Gradient


@dataclass
class SkinData:
    """Skinning data ready for glTF export."""

    joints: np.ndarray  # (N, 4) uint16
    weights: np.ndarray  # (N, 4) float32
    inverse_bind_matrices: np.ndarray  # (J, 4, 4) float32
    joint_names: list[str]


def compute_skinning(
    binding: Binding,
    armature: Armature,
    prim_ranges: dict[str, tuple[int, int]],
    total_vertices: int,
    *,
    positions: np.ndarray | None = None,
    yaml_dir: Path | None = None,
) -> SkinData:
    """Compute skinning arrays for a bound mesh.

    Args:
        binding: The binding connecting mesh to armature.
        armature: The armature with bone definitions.
        prim_ranges: Map of primitive_id -> (start_vertex, end_vertex).
        total_vertices: Total vertex count of the merged mesh.
        positions: Vertex positions array (N, 3), needed for gradient evaluation.
        yaml_dir: Directory of the source YAML, for resolving external JSON sources.

    Returns:
        SkinData with joints, weights, IBMs, and joint names.
    """
    # Build bone index map (YAML order)
    joint_names = [bone.id for bone in armature.bones]
    bone_index = {bone.id: i for i, bone in enumerate(armature.bones)}
    root_bone_idx = _find_root_bone_index(armature)

    # Per-vertex influence map: vertex_index -> list[(bone_idx, weight)]
    influences: dict[int, list[tuple[int, float]]] = {}

    # Layer 1: Default — all vertices get root bone w=1.0
    for v in range(total_vertices):
        influences[v] = [(root_bone_idx, 1.0)]

    # Layer 2: Per-primitive weights (uniform for all verts in primitive)
    for pw in binding.weights:
        if pw.primitive_id not in prim_ranges:
            continue
        start, end = prim_ranges[pw.primitive_id]
        bw_list = []
        for bw in pw.bones:
            if bw.bone_id in bone_index:
                bw_list.append((bone_index[bw.bone_id], bw.weight))
        if bw_list:
            for v in range(start, end):
                influences[v] = list(bw_list)

    # Layer 3+: Weight maps
    if binding.weight_maps:
        for wm in binding.weight_maps:
            if wm.primitive_id not in prim_ranges:
                continue
            start, end = prim_ranges[wm.primitive_id]

            # Layer 3: External JSON source
            if wm.source:
                ext = _load_external_weights(
                    wm.source, yaml_dir, wm.primitive_id, bone_index, end - start,
                )
                for local_v, bws in ext.items():
                    influences[start + local_v] = bws

            # Layer 4: Gradients (declaration order, each replaces all verts)
            if wm.gradients:
                if positions is None:
                    raise ExportError(
                        f"Weight map for primitive {wm.primitive_id!r} has gradients "
                        f"but no vertex positions are available"
                    )
                for grad in wm.gradients:
                    grad_influences = _evaluate_gradient(
                        grad, positions, bone_index, start, end,
                        root_bone_idx=root_bone_idx,
                    )
                    for v, bws in grad_influences.items():
                        influences[v] = bws

            # Layer 5: Overrides (declaration order, replaces listed verts)
            if wm.overrides:
                for ov in wm.overrides:
                    bw_list = []
                    for bw in ov.bones:
                        if bw.bone_id in bone_index:
                            bw_list.append((bone_index[bw.bone_id], bw.weight))
                    for local_v in ov.vertices:
                        abs_v = start + local_v
                        if abs_v >= end:
                            raise ValidationError(
                                f"Override vertex index {local_v} out of bounds for "
                                f"primitive {wm.primitive_id!r} "
                                f"(vertex count: {end - start})"
                            )
                        influences[abs_v] = list(bw_list)

    # Final pass: sort, cap to 4, normalize
    joints = np.zeros((total_vertices, 4), dtype=np.uint16)
    weights = np.zeros((total_vertices, 4), dtype=np.float32)

    for v in range(total_vertices):
        bone_weights = influences.get(v, [(root_bone_idx, 1.0)])

        if len(bone_weights) > 4:
            warnings.warn(
                f"Vertex {v} has {len(bone_weights)} joint influences; "
                f"capping to 4",
                stacklevel=2,
            )

        # Sort: weight desc, bone_id string asc, bone_index asc
        bone_weights.sort(key=lambda x: (-x[1], joint_names[x[0]], x[0]))
        bone_weights = bone_weights[:4]

        # Normalize
        total_w = sum(w for _, w in bone_weights)
        if total_w > 0:
            bone_weights = [(j, w / total_w) for j, w in bone_weights]
        else:
            # Zero weights -> fall back to root bone
            bone_weights = [(root_bone_idx, 1.0)]

        # Pad to 4
        while len(bone_weights) < 4:
            bone_weights.append((0, 0.0))

        for i, (j, w) in enumerate(bone_weights):
            joints[v, i] = j
            weights[v, i] = w

    # Compute inverse bind matrices
    ibms = _compute_inverse_bind_matrices(armature.bones)

    return SkinData(
        joints=joints,
        weights=weights,
        inverse_bind_matrices=ibms,
        joint_names=joint_names,
    )


def _find_root_bone_index(armature: Armature) -> int:
    """Return the index of the root bone (parent == 'none')."""
    for i, bone in enumerate(armature.bones):
        if bone.parent == "none":
            return i
    return 0


def _load_external_weights(
    source: str,
    yaml_dir: Path | None,
    primitive_id: str,
    bone_index: dict[str, int],
    vertex_count: int,
) -> dict[int, list[tuple[int, float]]]:
    """Load per-vertex weights from an external JSON file.

    Returns:
        Map of local vertex index -> [(bone_idx, weight), ...]
    """
    if yaml_dir is None:
        raise ValidationError(
            f"External weight source {source!r} specified but no yaml_dir available"
        )

    json_path = yaml_dir / source
    if not json_path.exists():
        raise ValidationError(f"External weight file not found: {json_path}")

    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        raise ValidationError(f"Failed to load external weights from {json_path}: {e}") from e

    if data.get("primitive_id") != primitive_id:
        raise ValidationError(
            f"External weight file {source!r}: primitive_id mismatch "
            f"(expected {primitive_id!r}, got {data.get('primitive_id')!r})"
        )

    file_vc = data.get("vertex_count")
    if file_vc != vertex_count:
        raise ValidationError(
            f"External weight file {source!r}: vertex_count mismatch "
            f"(expected {vertex_count}, got {file_vc})"
        )

    result: dict[int, list[tuple[int, float]]] = {}
    for entry in data.get("influences", []):
        vi = entry["vertex"]
        bws = []
        for bw in entry["bones"]:
            bid = bw["bone_id"]
            if bid in bone_index:
                bws.append((bone_index[bid], bw["weight"]))
        result[vi] = bws

    return result


def _evaluate_gradient(
    gradient: Gradient,
    positions: np.ndarray,
    bone_index: dict[str, int],
    start: int,
    end: int,
    root_bone_idx: int = 0,
) -> dict[int, list[tuple[int, float]]]:
    """Evaluate a gradient across vertices in [start, end).

    For each vertex, interpolates between from and to bone weights
    based on position along the gradient axis.
    """
    axis_idx = {"x": 0, "y": 1, "z": 2}[gradient.axis]
    r0, r1 = gradient.range

    # Collect union of bone indices from both sides
    from_bones: dict[int, float] = {}
    for bw in gradient.from_:
        if bw.bone_id in bone_index:
            from_bones[bone_index[bw.bone_id]] = bw.weight

    to_bones: dict[int, float] = {}
    for bw in gradient.to:
        if bw.bone_id in bone_index:
            to_bones[bone_index[bw.bone_id]] = bw.weight

    all_bone_idxs = set(from_bones.keys()) | set(to_bones.keys())

    result: dict[int, list[tuple[int, float]]] = {}
    for v in range(start, end):
        p = float(positions[v, axis_idx])
        # Clamp t to [0, 1]
        t = (p - r0) / (r1 - r0)
        t = max(0.0, min(1.0, t))

        bws = []
        for bi in all_bone_idxs:
            w_from = from_bones.get(bi, 0.0)
            w_to = to_bones.get(bi, 0.0)
            w = w_from * (1.0 - t) + w_to * t
            if w > 0:
                bws.append((bi, w))

        if bws:
            result[v] = bws
        else:
            result[v] = [(root_bone_idx, 1.0)]

    return result


def _compute_inverse_bind_matrices(bones: list[Bone]) -> np.ndarray:
    """Compute inverse bind matrices from bone rest poses.

    The glTF node tree uses translation-only transforms (bone head positions).
    The world transform of each joint node is a pure translation to bone.head.
    The IBM is the inverse: translate(-bone.head).
    """
    n = len(bones)
    ibms = np.zeros((n, 4, 4), dtype=np.float32)

    for i, bone in enumerate(bones):
        # IBM = inverse of world-space translation to bone head
        mat = np.eye(4, dtype=np.float32)
        mat[0, 3] = -float(bone.head[0])
        mat[1, 3] = -float(bone.head[1])
        mat[2, 3] = -float(bone.head[2])
        ibms[i] = mat

    return ibms
