"""Tests for skinning computation."""

import numpy as np

from rigy.models import Armature, Binding, Bone, BoneWeight, PrimitiveWeights
from rigy.skinning import compute_skinning


def _simple_armature():
    return Armature(
        id="arm",
        bones=[
            Bone(id="root", parent="none", head=(0, 0, 0), tail=(0, 1, 0)),
            Bone(id="child", parent="root", head=(0, 1, 0), tail=(0, 2, 0)),
        ],
    )


class TestSkinning:
    def test_single_bone_full_weight(self):
        arm = _simple_armature()
        binding = Binding(
            mesh_id="m",
            armature_id="arm",
            weights=[
                PrimitiveWeights(
                    primitive_id="p1",
                    bones=[BoneWeight(bone_id="root", weight=1.0)],
                )
            ],
        )
        prim_ranges = {"p1": (0, 10)}
        sd = compute_skinning(binding, arm, prim_ranges, 10)

        # All verts should have joint 0 with weight 1.0
        assert sd.joints.shape == (10, 4)
        assert sd.weights.shape == (10, 4)
        assert np.all(sd.joints[:, 0] == 0)
        np.testing.assert_allclose(sd.weights[:, 0], 1.0)
        np.testing.assert_allclose(sd.weights[:, 1:], 0.0)

    def test_multi_bone_split_weights(self):
        arm = _simple_armature()
        binding = Binding(
            mesh_id="m",
            armature_id="arm",
            weights=[
                PrimitiveWeights(
                    primitive_id="p1",
                    bones=[
                        BoneWeight(bone_id="root", weight=0.6),
                        BoneWeight(bone_id="child", weight=0.4),
                    ],
                )
            ],
        )
        prim_ranges = {"p1": (0, 5)}
        sd = compute_skinning(binding, arm, prim_ranges, 5)

        # Weights should be normalized (already sum to 1.0)
        np.testing.assert_allclose(sd.weights[:, 0], 0.6, atol=1e-5)
        np.testing.assert_allclose(sd.weights[:, 1], 0.4, atol=1e-5)

    def test_normalization(self):
        arm = _simple_armature()
        binding = Binding(
            mesh_id="m",
            armature_id="arm",
            weights=[
                PrimitiveWeights(
                    primitive_id="p1",
                    bones=[
                        BoneWeight(bone_id="root", weight=0.3),
                        BoneWeight(bone_id="child", weight=0.3),
                    ],
                )
            ],
        )
        prim_ranges = {"p1": (0, 3)}
        sd = compute_skinning(binding, arm, prim_ranges, 3)

        # Should be normalized to sum to 1.0
        weight_sums = sd.weights.sum(axis=1)
        np.testing.assert_allclose(weight_sums, 1.0, atol=1e-5)

    def test_joint_index_matches_yaml_order(self):
        arm = _simple_armature()
        assert arm.bones[0].id == "root"
        assert arm.bones[1].id == "child"

        binding = Binding(
            mesh_id="m",
            armature_id="arm",
            weights=[
                PrimitiveWeights(
                    primitive_id="p1",
                    bones=[BoneWeight(bone_id="child", weight=1.0)],
                )
            ],
        )
        prim_ranges = {"p1": (0, 3)}
        sd = compute_skinning(binding, arm, prim_ranges, 3)

        # "child" is index 1 in YAML order
        assert np.all(sd.joints[:, 0] == 1)
        assert sd.joint_names == ["root", "child"]

    def test_ibm_shape(self):
        arm = _simple_armature()
        binding = Binding(
            mesh_id="m",
            armature_id="arm",
            weights=[],
        )
        sd = compute_skinning(binding, arm, {}, 0)
        assert sd.inverse_bind_matrices.shape == (2, 4, 4)

    def test_ibm_correctness(self):
        """IBM should be inverse of translation to bone head."""
        arm = _simple_armature()
        binding = Binding(mesh_id="m", armature_id="arm", weights=[])
        sd = compute_skinning(binding, arm, {}, 0)
        # root at (0,0,0) -> IBM is identity
        np.testing.assert_allclose(sd.inverse_bind_matrices[0], np.eye(4), atol=1e-6)
        # child at (0,1,0) -> IBM translates by (0,-1,0)
        expected = np.eye(4, dtype=np.float32)
        expected[1, 3] = -1.0
        np.testing.assert_allclose(sd.inverse_bind_matrices[1], expected, atol=1e-6)

    def test_padded_to_4_joints(self):
        arm = _simple_armature()
        binding = Binding(
            mesh_id="m",
            armature_id="arm",
            weights=[
                PrimitiveWeights(
                    primitive_id="p1",
                    bones=[BoneWeight(bone_id="root", weight=1.0)],
                )
            ],
        )
        prim_ranges = {"p1": (0, 3)}
        sd = compute_skinning(binding, arm, prim_ranges, 3)
        assert sd.joints.shape[1] == 4
        assert sd.weights.shape[1] == 4
