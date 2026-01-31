"""Per-primitive weight to per-vertex glTF JOINTS_0/WEIGHTS_0 arrays."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from rigy.models import Armature, Binding, Bone


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
) -> SkinData:
    """Compute skinning arrays for a bound mesh.

    Args:
        binding: The binding connecting mesh to armature.
        armature: The armature with bone definitions.
        prim_ranges: Map of primitive_id -> (start_vertex, end_vertex).
        total_vertices: Total vertex count of the merged mesh.

    Returns:
        SkinData with joints, weights, IBMs, and joint names.
    """
    # Build bone index map (YAML order)
    joint_names = [bone.id for bone in armature.bones]
    bone_index = {bone.id: i for i, bone in enumerate(armature.bones)}
    joints = np.zeros((total_vertices, 4), dtype=np.uint16)
    weights = np.zeros((total_vertices, 4), dtype=np.float32)

    for pw in binding.weights:
        if pw.primitive_id not in prim_ranges:
            continue
        start, end = prim_ranges[pw.primitive_id]

        # Collect bone weights for this primitive
        bone_weights: list[tuple[int, float]] = []
        for bw in pw.bones:
            if bw.bone_id in bone_index:
                bone_weights.append((bone_index[bw.bone_id], bw.weight))

        # Sort by weight descending, take top 4
        bone_weights.sort(key=lambda x: x[1], reverse=True)
        bone_weights = bone_weights[:4]

        # Normalize
        total_w = sum(w for _, w in bone_weights)
        if total_w > 0:
            bone_weights = [(j, w / total_w) for j, w in bone_weights]

        # Pad to 4
        while len(bone_weights) < 4:
            bone_weights.append((0, 0.0))

        j_arr = np.array([j for j, _ in bone_weights], dtype=np.uint16)
        w_arr = np.array([w for _, w in bone_weights], dtype=np.float32)

        # All vertices of this primitive get the same weights
        for v in range(start, end):
            joints[v] = j_arr
            weights[v] = w_arr

    # Compute inverse bind matrices
    ibms = _compute_inverse_bind_matrices(armature.bones)

    return SkinData(
        joints=joints,
        weights=weights,
        inverse_bind_matrices=ibms,
        joint_names=joint_names,
    )


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
