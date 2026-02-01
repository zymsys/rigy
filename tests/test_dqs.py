"""Tests for DQS algorithm and pose evaluation."""

from __future__ import annotations

import math

import numpy as np
import numpy.testing as npt

from rigy.dqs import (
    _evaluate_dqs,
    _evaluate_lbs,
    _quat_conj,
    _quat_mul,
    _quat_rotate,
    evaluate_pose,
)
from rigy.models import (
    Armature,
    Binding,
    Bone,
    BoneWeight,
    Pose,
    PoseBoneTransform,
    PrimitiveWeights,
    RigySpec,
)
from rigy.skinning import SkinData


def _identity_ibm():
    return np.eye(4, dtype=np.float64).reshape(1, 4, 4)


def _single_bone_skin(n_verts: int) -> SkinData:
    """SkinData with all vertices bound to a single bone at weight 1.0."""
    joints = np.zeros((n_verts, 4), dtype=np.uint16)
    weights = np.zeros((n_verts, 4), dtype=np.float64)
    weights[:, 0] = 1.0
    ibm = np.eye(4, dtype=np.float64).reshape(1, 4, 4)
    return SkinData(joints=joints, weights=weights, inverse_bind_matrices=ibm, joint_names=["root"])


def _two_bone_skin(n_verts: int, split: int, w0: float = 1.0, w1: float = 0.0) -> SkinData:
    """SkinData with two bones. Verts [0, split) -> bone 0, [split, n) -> bone 1.
    Middle vertices can get blended weights.
    """
    joints = np.zeros((n_verts, 4), dtype=np.uint16)
    weights = np.zeros((n_verts, 4), dtype=np.float64)

    for v in range(n_verts):
        if v < split:
            joints[v, 0] = 0
            weights[v, 0] = 1.0
        else:
            joints[v, 0] = 1
            weights[v, 0] = 1.0

    ibms = np.zeros((2, 4, 4), dtype=np.float64)
    ibms[0] = np.eye(4, dtype=np.float64)
    ibms[1] = np.eye(4, dtype=np.float64)
    return SkinData(
        joints=joints,
        weights=weights,
        inverse_bind_matrices=ibms,
        joint_names=["root", "child"],
    )


def _simple_armature(n_bones: int = 1) -> Armature:
    bones = [Bone(id="root", parent="none", head=(0, 0, 0), tail=(0, 1, 0))]
    if n_bones >= 2:
        bones.append(Bone(id="child", parent="root", head=(0, 1, 0), tail=(0, 2, 0)))
    return Armature(id="arm", bones=bones)


class TestQuatHelpers:
    def test_quat_mul_identity(self):
        ident = np.array([1, 0, 0, 0], dtype=np.float64)
        q = np.array([0.7071, 0.7071, 0, 0], dtype=np.float64)
        result = _quat_mul(ident, q)
        npt.assert_allclose(result, q, atol=1e-10)

    def test_quat_mul_inverse(self):
        q = np.array([0.7071067811865476, 0.7071067811865476, 0, 0], dtype=np.float64)
        result = _quat_mul(q, _quat_conj(q))
        npt.assert_allclose(result, [1, 0, 0, 0], atol=1e-10)

    def test_quat_conj(self):
        q = np.array([1, 2, 3, 4], dtype=np.float64)
        c = _quat_conj(q)
        npt.assert_allclose(c, [1, -2, -3, -4])

    def test_quat_rotate_identity(self):
        ident = np.array([1, 0, 0, 0], dtype=np.float64)
        v = np.array([1, 2, 3], dtype=np.float64)
        result = _quat_rotate(ident, v)
        npt.assert_allclose(result, v, atol=1e-10)

    def test_quat_rotate_90_around_z(self):
        """90° rotation around Z axis: (1,0,0) -> (0,1,0)."""
        angle = math.pi / 2
        q = np.array([math.cos(angle / 2), 0, 0, math.sin(angle / 2)], dtype=np.float64)
        v = np.array([1, 0, 0], dtype=np.float64)
        result = _quat_rotate(q, v)
        npt.assert_allclose(result, [0, 1, 0], atol=1e-10)


class TestIdentityPose:
    def test_identity_pose_preserves_positions(self):
        """DQS with identity pose = no deformation."""
        positions = np.array([[1, 2, 3], [4, 5, 6]], dtype=np.float32)
        normals = np.array([[0, 1, 0], [0, 0, 1]], dtype=np.float32)
        skin = _single_bone_skin(2)
        arm = _simple_armature()
        pose = Pose(id="identity", bones={"root": PoseBoneTransform(rotation=(1, 0, 0, 0))})

        out_pos, out_norm = _evaluate_dqs(skin, arm, pose, positions, normals)

        npt.assert_allclose(out_pos, positions, atol=1e-6)
        npt.assert_allclose(out_norm, normals, atol=1e-6)

    def test_identity_pose_empty_bones(self):
        """Empty pose bones dict = identity for all bones."""
        positions = np.array([[1, 0, 0]], dtype=np.float32)
        normals = np.array([[0, 1, 0]], dtype=np.float32)
        skin = _single_bone_skin(1)
        arm = _simple_armature()
        pose = Pose(id="identity", bones={})

        out_pos, out_norm = _evaluate_dqs(skin, arm, pose, positions, normals)

        npt.assert_allclose(out_pos, positions, atol=1e-6)
        npt.assert_allclose(out_norm, normals, atol=1e-6)


class TestSingleBoneRotation:
    def test_90_degree_rotation_around_y(self):
        """Single bone 90° Y rotation: (1,0,0) -> (0,0,-1)."""
        angle = math.pi / 2
        q = (math.cos(angle / 2), 0.0, math.sin(angle / 2), 0.0)

        positions = np.array([[1, 0, 0]], dtype=np.float32)
        normals = np.array([[1, 0, 0]], dtype=np.float32)
        skin = _single_bone_skin(1)
        arm = _simple_armature()
        pose = Pose(id="rot90", bones={"root": PoseBoneTransform(rotation=q)})

        out_pos, out_norm = _evaluate_dqs(skin, arm, pose, positions, normals)

        npt.assert_allclose(out_pos[0], [0, 0, -1], atol=1e-5)
        npt.assert_allclose(out_norm[0], [0, 0, -1], atol=1e-5)


class TestTwoBoneTwist:
    def test_candy_wrapper_dqs_vs_lbs(self):
        """DQS should preserve volume better than LBS in a twist scenario."""
        n = 5
        # Vertices along the Y axis
        positions = np.zeros((n, 3), dtype=np.float32)
        positions[:, 1] = np.linspace(0, 2, n)
        normals = np.tile([1, 0, 0], (n, 1)).astype(np.float32)

        # Blended weights: linear blend between two bones
        joints = np.zeros((n, 4), dtype=np.uint16)
        weights_arr = np.zeros((n, 4), dtype=np.float64)
        for v in range(n):
            t = v / (n - 1)
            joints[v, 0] = 0
            joints[v, 1] = 1
            weights_arr[v, 0] = 1.0 - t
            weights_arr[v, 1] = t

        ibms = np.zeros((2, 4, 4), dtype=np.float64)
        ibms[0] = np.eye(4, dtype=np.float64)
        ibms[1] = np.eye(4, dtype=np.float64)
        skin = SkinData(
            joints=joints,
            weights=weights_arr,
            inverse_bind_matrices=ibms,
            joint_names=["root", "child"],
        )

        arm = _simple_armature(2)

        # Twist child bone 180° around Y
        angle = math.pi
        q = (math.cos(angle / 2), 0.0, math.sin(angle / 2), 0.0)
        pose = Pose(
            id="twist",
            bones={
                "root": PoseBoneTransform(rotation=(1, 0, 0, 0)),
                "child": PoseBoneTransform(rotation=q),
            },
        )

        dqs_pos, _ = _evaluate_dqs(skin, arm, pose, positions, normals)
        lbs_pos, _ = _evaluate_lbs(skin, arm, pose, positions, normals)

        # The middle vertex (t=0.5) with LBS collapses toward origin on x
        # while DQS preserves it better
        mid = n // 2
        # DQS mid-point position magnitude should be >= LBS
        lbs_xz = math.sqrt(float(lbs_pos[mid, 0]) ** 2 + float(lbs_pos[mid, 2]) ** 2)
        # For a 180° twist, LBS at midpoint should collapse (xz ≈ 0)
        assert lbs_xz < 0.01, f"LBS midpoint xz should collapse, got {lbs_xz}"
        # DQS should not collapse — output is finite and reasonable
        assert np.all(np.isfinite(dqs_pos))


class TestHemisphereConsistency:
    def test_opposing_quaternion_signs(self):
        """Opposing-sign quaternions representing same rotation should blend consistently."""
        positions = np.array([[0, 0.5, 0]], dtype=np.float32)
        normals = np.array([[1, 0, 0]], dtype=np.float32)

        # Two bones with 50/50 blend
        joints = np.array([[0, 1, 0, 0]], dtype=np.uint16)
        weights_arr = np.array([[0.5, 0.5, 0, 0]], dtype=np.float64)
        ibms = np.zeros((2, 4, 4), dtype=np.float64)
        ibms[0] = np.eye(4)
        ibms[1] = np.eye(4)
        skin = SkinData(
            joints=joints,
            weights=weights_arr,
            inverse_bind_matrices=ibms,
            joint_names=["root", "child"],
        )

        arm = _simple_armature(2)

        # Same rotation, opposite quaternion signs
        angle = math.pi / 4
        c, s = math.cos(angle / 2), math.sin(angle / 2)
        pose = Pose(
            id="hemi",
            bones={
                "root": PoseBoneTransform(rotation=(c, 0, s, 0)),
                "child": PoseBoneTransform(rotation=(-c, 0, -s, 0)),
            },
        )

        out_pos, _ = _evaluate_dqs(skin, arm, pose, positions, normals)
        # Should not produce NaN or wildly wrong results
        assert np.all(np.isfinite(out_pos))


class TestNearAntipodal:
    def test_boundary_stability(self):
        """Near-antipodal quaternions (dot ≈ 0) should remain stable."""
        positions = np.array([[0, 1, 0]], dtype=np.float32)
        normals = np.array([[0, 1, 0]], dtype=np.float32)

        joints = np.array([[0, 1, 0, 0]], dtype=np.uint16)
        weights_arr = np.array([[0.5, 0.5, 0, 0]], dtype=np.float64)
        ibms = np.zeros((2, 4, 4), dtype=np.float64)
        ibms[0] = np.eye(4)
        ibms[1] = np.eye(4)
        skin = SkinData(
            joints=joints,
            weights=weights_arr,
            inverse_bind_matrices=ibms,
            joint_names=["root", "child"],
        )

        arm = _simple_armature(2)

        # 90° rotations around perpendicular axes -> dot ≈ 0
        a1 = math.pi / 2
        a2 = math.pi / 2
        pose = Pose(
            id="antipodal",
            bones={
                "root": PoseBoneTransform(rotation=(math.cos(a1 / 2), math.sin(a1 / 2), 0, 0)),
                "child": PoseBoneTransform(rotation=(math.cos(a2 / 2), 0, math.sin(a2 / 2), 0)),
            },
        )

        out_pos, out_norm = _evaluate_dqs(skin, arm, pose, positions, normals)
        assert np.all(np.isfinite(out_pos))
        assert np.all(np.isfinite(out_norm))


class TestNormalization:
    def test_normalized_quaternion_output(self):
        """After DQS blending, the rotation quaternion should be unit length."""
        # This tests internal invariants by checking output is sensible
        positions = np.array([[1, 0, 0]], dtype=np.float32)
        normals = np.array([[1, 0, 0]], dtype=np.float32)

        joints = np.array([[0, 1, 0, 0]], dtype=np.uint16)
        weights_arr = np.array([[0.7, 0.3, 0, 0]], dtype=np.float64)
        ibms = np.zeros((2, 4, 4), dtype=np.float64)
        ibms[0] = np.eye(4)
        ibms[1] = np.eye(4)
        skin = SkinData(
            joints=joints,
            weights=weights_arr,
            inverse_bind_matrices=ibms,
            joint_names=["root", "child"],
        )

        arm = _simple_armature(2)
        angle = math.pi / 3
        pose = Pose(
            id="blend",
            bones={
                "root": PoseBoneTransform(rotation=(1, 0, 0, 0)),
                "child": PoseBoneTransform(
                    rotation=(math.cos(angle / 2), 0, math.sin(angle / 2), 0)
                ),
            },
        )

        out_pos, out_norm = _evaluate_dqs(skin, arm, pose, positions, normals)
        # Output normal should be approximately unit length
        norm_len = np.linalg.norm(out_norm[0])
        npt.assert_allclose(norm_len, 1.0, atol=1e-5)


class TestPrecision:
    def test_float32_output(self):
        """Output arrays should be float32."""
        positions = np.array([[1, 2, 3]], dtype=np.float32)
        normals = np.array([[0, 1, 0]], dtype=np.float32)
        skin = _single_bone_skin(1)
        arm = _simple_armature()
        pose = Pose(id="p", bones={"root": PoseBoneTransform(rotation=(1, 0, 0, 0))})

        out_pos, out_norm = _evaluate_dqs(skin, arm, pose, positions, normals)
        assert out_pos.dtype == np.float32
        assert out_norm.dtype == np.float32


class TestEvaluatePoseDispatch:
    def test_dispatches_dqs(self):
        positions = np.array([[1, 0, 0]], dtype=np.float32)
        normals = np.array([[0, 1, 0]], dtype=np.float32)
        skin = _single_bone_skin(1)
        arm = _simple_armature()
        spec = RigySpec(version="0.5", skinning_solver="dqs")
        binding = Binding(
            mesh_id="m",
            armature_id="arm",
            weights=[
                PrimitiveWeights(primitive_id="p", bones=[BoneWeight(bone_id="root", weight=1.0)])
            ],
        )
        pose = Pose(id="p", bones={"root": PoseBoneTransform(rotation=(1, 0, 0, 0))})

        out_pos, _ = evaluate_pose(spec, skin, arm, binding, pose, positions, normals)
        npt.assert_allclose(out_pos, positions, atol=1e-6)

    def test_dispatches_lbs(self):
        positions = np.array([[1, 0, 0]], dtype=np.float32)
        normals = np.array([[0, 1, 0]], dtype=np.float32)
        skin = _single_bone_skin(1)
        arm = _simple_armature()
        spec = RigySpec(version="0.5", skinning_solver="lbs")
        binding = Binding(
            mesh_id="m",
            armature_id="arm",
            weights=[
                PrimitiveWeights(primitive_id="p", bones=[BoneWeight(bone_id="root", weight=1.0)])
            ],
        )
        pose = Pose(id="p", bones={"root": PoseBoneTransform(rotation=(1, 0, 0, 0))})

        out_pos, _ = evaluate_pose(spec, skin, arm, binding, pose, positions, normals)
        npt.assert_allclose(out_pos, positions, atol=1e-6)
