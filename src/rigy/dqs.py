"""Dual Quaternion Skinning (DQS) and LBS pose evaluation."""

from __future__ import annotations

import numpy as np

from rigy.models import Armature, Binding, Pose, RigySpec, resolve_solver
from rigy.skinning import SkinData


def evaluate_pose(
    spec: RigySpec,
    skin_data: SkinData,
    armature: Armature,
    binding: Binding,
    pose: Pose,
    positions: np.ndarray,
    normals: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Evaluate a pose on skinned geometry.

    Returns deformed (positions, normals) as float32 arrays.
    """
    solver = resolve_solver(spec, binding)
    if solver == "dqs":
        return _evaluate_dqs(skin_data, armature, pose, positions, normals)
    else:
        return _evaluate_lbs(skin_data, armature, pose, positions, normals)


# ---------------------------------------------------------------------------
# Quaternion helpers — Hamilton product, [w, x, y, z] convention
# ---------------------------------------------------------------------------


def _quat_mul(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Hamilton product of two quaternions [w, x, y, z]."""
    aw, ax, ay, az = a
    bw, bx, by, bz = b
    return np.array(
        [
            aw * bw - ax * bx - ay * by - az * bz,
            aw * bx + ax * bw + ay * bz - az * by,
            aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw,
        ],
        dtype=np.float64,
    )


def _quat_conj(q: np.ndarray) -> np.ndarray:
    """Conjugate of quaternion [w, x, y, z]."""
    return np.array([q[0], -q[1], -q[2], -q[3]], dtype=np.float64)


def _quat_rotate(q: np.ndarray, v: np.ndarray) -> np.ndarray:
    """Rotate vector v by unit quaternion q. Returns 3-vector."""
    v_quat = np.array([0.0, v[0], v[1], v[2]], dtype=np.float64)
    result = _quat_mul(_quat_mul(q, v_quat), _quat_conj(q))
    return result[1:4]


# ---------------------------------------------------------------------------
# Bone transform building
# ---------------------------------------------------------------------------


def _build_bone_dual_quaternions(
    armature: Armature,
    pose: Pose,
    ibms: np.ndarray,
    joint_names: list[str],
) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    """Build per-bone skinning dual quaternions: DQ_pose * DQ_ibm.

    The deformation for each bone is M_pose @ IBM (same as LBS).
    IBM is a pure translation by -bone.head.  The combined transform is:
      1. translate by -bone.head  (IBM)
      2. rotate by pose rotation
      3. translate by pose translation
    Net translation = R_pose @ (-bone.head) + t_pose.

    Returns dict mapping bone_id -> (qr, qd).
    """
    # Build bone index for IBM lookup
    name_to_idx = {n: i for i, n in enumerate(joint_names)}

    result: dict[str, tuple[np.ndarray, np.ndarray]] = {}

    for bone in armature.bones:
        pbt = pose.bones.get(bone.id)

        # Pose rotation
        if pbt is not None and pbt.rotation is not None:
            qr = np.array(pbt.rotation, dtype=np.float64)
        else:
            qr = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float64)

        # Pose translation
        if pbt is not None and pbt.translation is not None:
            t_pose = np.array(pbt.translation, dtype=np.float64)
        else:
            t_pose = np.zeros(3, dtype=np.float64)

        # IBM translation (column 3 of the IBM matrix = -bone.head)
        j_idx = name_to_idx.get(bone.id)
        if j_idx is not None:
            ibm_t = ibms[j_idx, :3, 3].copy()
        else:
            ibm_t = np.array([-bone.head[0], -bone.head[1], -bone.head[2]], dtype=np.float64)

        # Combined: first IBM translation, then pose rotation + translation
        # t_combined = R_pose @ ibm_t + t_pose
        t_combined = _quat_rotate(qr, ibm_t) + t_pose

        # Build dual quaternion from (qr, t_combined)
        # qd = 0.5 * (0, tx, ty, tz) * qr
        t_quat = np.array([0.0, t_combined[0], t_combined[1], t_combined[2]], dtype=np.float64)
        qd = 0.5 * _quat_mul(t_quat, qr)

        result[bone.id] = (qr, qd)

    return result


def _build_bone_matrices(
    armature: Armature,
    pose: Pose,
) -> dict[str, np.ndarray]:
    """Build per-bone 4x4 transform matrices from a pose. For LBS path."""
    result: dict[str, np.ndarray] = {}

    for bone in armature.bones:
        pbt = pose.bones.get(bone.id)
        mat = np.eye(4, dtype=np.float64)

        if pbt is not None and pbt.rotation is not None:
            q = np.array(pbt.rotation, dtype=np.float64)
            w, x, y, z = q
            # Rotation matrix from quaternion
            mat[0, 0] = 1.0 - 2.0 * (y * y + z * z)
            mat[0, 1] = 2.0 * (x * y - w * z)
            mat[0, 2] = 2.0 * (x * z + w * y)
            mat[1, 0] = 2.0 * (x * y + w * z)
            mat[1, 1] = 1.0 - 2.0 * (x * x + z * z)
            mat[1, 2] = 2.0 * (y * z - w * x)
            mat[2, 0] = 2.0 * (x * z - w * y)
            mat[2, 1] = 2.0 * (y * z + w * x)
            mat[2, 2] = 1.0 - 2.0 * (x * x + y * y)

        if pbt is not None and pbt.translation is not None:
            mat[0, 3] = pbt.translation[0]
            mat[1, 3] = pbt.translation[1]
            mat[2, 3] = pbt.translation[2]

        result[bone.id] = mat

    return result


# ---------------------------------------------------------------------------
# DQS evaluator
# ---------------------------------------------------------------------------


def _evaluate_dqs(
    skin_data: SkinData,
    armature: Armature,
    pose: Pose,
    positions: np.ndarray,
    normals: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Evaluate DQS deformation."""
    bone_dqs = _build_bone_dual_quaternions(
        armature, pose, skin_data.inverse_bind_matrices, skin_data.joint_names,
    )

    # Map joint names to dual quaternions (indexed by joint index)
    n_joints = len(skin_data.joint_names)
    qr_arr = np.zeros((n_joints, 4), dtype=np.float64)
    qd_arr = np.zeros((n_joints, 4), dtype=np.float64)
    for j, name in enumerate(skin_data.joint_names):
        if name in bone_dqs:
            qr_arr[j] = bone_dqs[name][0]
            qd_arr[j] = bone_dqs[name][1]
        else:
            qr_arr[j] = [1.0, 0.0, 0.0, 0.0]

    n_verts = len(positions)
    out_pos = np.zeros((n_verts, 3), dtype=np.float64)
    out_norm = np.zeros((n_verts, 3), dtype=np.float64)

    joints = skin_data.joints  # (N, 4) uint16
    weights = skin_data.weights  # (N, 4) float64

    for v in range(n_verts):
        # Gather nonzero influences
        infs = []
        for k in range(4):
            w = float(weights[v, k])
            if w > 0.0:
                j_idx = int(joints[v, k])
                infs.append((j_idx, w))

        if not infs:
            out_pos[v] = positions[v]
            out_norm[v] = normals[v]
            continue

        # Reference = influence with lowest absolute bone index
        ref_idx = min(infs, key=lambda x: x[0])[0]
        qr_ref = qr_arr[ref_idx]

        # Weighted sum with hemisphere consistency
        qr_sum = np.zeros(4, dtype=np.float64)
        qd_sum = np.zeros(4, dtype=np.float64)

        for j_idx, w in infs:
            qr_i = qr_arr[j_idx].copy()
            qd_i = qd_arr[j_idx].copy()

            # Hemisphere consistency
            if np.dot(qr_i, qr_ref) < 0.0:
                qr_i = -qr_i
                qd_i = -qd_i

            qr_sum += w * qr_i
            qd_sum += w * qd_i

        # Full dual-quaternion normalization (float64)
        n_sq = np.dot(qr_sum, qr_sum)
        n_val = np.sqrt(n_sq)
        rn = 1.0 / n_val

        qr_prime = qr_sum * rn
        qd_scaled = qd_sum * rn
        qd_prime = qd_scaled - np.dot(qr_prime, qd_scaled) * qr_prime

        # Extract translation: t' = 2 * qd' * conj(qr')
        t_quat = 2.0 * _quat_mul(qd_prime, _quat_conj(qr_prime))
        t_vec = t_quat[1:4]

        # Apply: p' = rotate(qr', p) + t'
        p = positions[v].astype(np.float64)
        out_pos[v] = _quat_rotate(qr_prime, p) + t_vec

        # Normal: n' = rotate(qr', n)
        nm = normals[v].astype(np.float64)
        out_norm[v] = _quat_rotate(qr_prime, nm)

    return out_pos.astype(np.float32), out_norm.astype(np.float32)


# ---------------------------------------------------------------------------
# LBS evaluator (for mixed-solver conformance)
# ---------------------------------------------------------------------------


def _evaluate_lbs(
    skin_data: SkinData,
    armature: Armature,
    pose: Pose,
    positions: np.ndarray,
    normals: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Evaluate LBS deformation using pose transforms."""
    bone_mats = _build_bone_matrices(armature, pose)

    n_joints = len(skin_data.joint_names)
    mat_arr = np.zeros((n_joints, 4, 4), dtype=np.float64)
    for j, name in enumerate(skin_data.joint_names):
        if name in bone_mats:
            mat_arr[j] = bone_mats[name]
        else:
            mat_arr[j] = np.eye(4, dtype=np.float64)

    ibms = skin_data.inverse_bind_matrices  # (J, 4, 4)

    n_verts = len(positions)
    out_pos = np.zeros((n_verts, 3), dtype=np.float64)
    out_norm = np.zeros((n_verts, 3), dtype=np.float64)

    joints = skin_data.joints
    weights_arr = skin_data.weights

    for v in range(n_verts):
        p_h = np.array([*positions[v].astype(np.float64), 1.0], dtype=np.float64)
        n_h = np.array([*normals[v].astype(np.float64), 0.0], dtype=np.float64)

        pos_acc = np.zeros(4, dtype=np.float64)
        norm_acc = np.zeros(4, dtype=np.float64)

        for k in range(4):
            w = float(weights_arr[v, k])
            if w > 0.0:
                j_idx = int(joints[v, k])
                m = mat_arr[j_idx] @ ibms[j_idx]
                pos_acc += w * (m @ p_h)
                norm_acc += w * (m @ n_h)

        out_pos[v] = pos_acc[:3]
        n_len = np.sqrt(np.dot(norm_acc[:3], norm_acc[:3]))
        if n_len > 1e-12:
            out_norm[v] = norm_acc[:3] / n_len
        else:
            out_norm[v] = normals[v]

    return out_pos.astype(np.float32), out_norm.astype(np.float32)
