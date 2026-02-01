"""Tests for v0.3 per-vertex weight maps."""

from __future__ import annotations

import json
import warnings
from pathlib import Path

import numpy as np
import pytest
from numpy.testing import assert_allclose
from pydantic import ValidationError as PydanticValidationError

from rigy.errors import ExportError
from rigy.models import (
    Armature,
    Binding,
    Bone,
    BoneWeight,
    Gradient,
    PrimitiveWeights,
    RigySpec,
    VertexOverride,
    WeightMap,
)
from rigy.skinning import compute_skinning
from rigy.validation import validate


def _make_spec(**overrides) -> RigySpec:
    base = {
        "version": "0.3",
        "units": "meters",
        "coordinate_system": {"up": "Y", "forward": "-Z", "handedness": "right"},
        "tessellation_profile": "v0_1_default",
    }
    base.update(overrides)
    return RigySpec(**base)


def _arm_with_3_bones():
    return Armature(
        id="arm",
        bones=[
            Bone(id="root", parent="none", head=(0, 0, 0), tail=(0, 1, 0)),
            Bone(id="mid", parent="root", head=(0, 1, 0), tail=(0, 2, 0)),
            Bone(id="tip", parent="mid", head=(0, 2, 0), tail=(0, 3, 0)),
        ],
    )


class TestGradientModel:
    def test_single_bone_weight_normalized_to_list(self):
        g = Gradient(
            axis="y",
            range=(0.0, 1.0),
            **{"from": {"bone_id": "a", "weight": 1.0}},
            to=[{"bone_id": "b", "weight": 1.0}],
        )
        assert len(g.from_) == 1
        assert g.from_[0].bone_id == "a"

    def test_single_to_normalized_to_list(self):
        g = Gradient(
            axis="y",
            range=(0.0, 1.0),
            **{"from": [{"bone_id": "a", "weight": 1.0}]},
            to={"bone_id": "b", "weight": 1.0},
        )
        assert len(g.to) == 1

    def test_invalid_range_rejected(self):
        with pytest.raises(PydanticValidationError, match="range"):
            Gradient(
                axis="y",
                range=(1.0, 0.5),
                **{"from": [{"bone_id": "a", "weight": 1.0}]},
                to=[{"bone_id": "b", "weight": 1.0}],
            )

    def test_equal_range_rejected(self):
        with pytest.raises(PydanticValidationError, match="range"):
            Gradient(
                axis="x",
                range=(1.0, 1.0),
                **{"from": [{"bone_id": "a", "weight": 1.0}]},
                to=[{"bone_id": "b", "weight": 1.0}],
            )


class TestVertexOverrideModel:
    def test_negative_vertex_rejected(self):
        with pytest.raises(PydanticValidationError, match=">="):
            VertexOverride(
                vertices=[-1, 0],
                bones=[BoneWeight(bone_id="a", weight=1.0)],
            )


class TestWeightMapModel:
    def test_requires_at_least_one_strategy(self):
        with pytest.raises(PydanticValidationError, match="at least one"):
            WeightMap(primitive_id="p1")

    def test_gradients_only_valid(self):
        wm = WeightMap(
            primitive_id="p1",
            gradients=[
                Gradient(
                    axis="y",
                    range=(0.0, 1.0),
                    **{"from": [{"bone_id": "a", "weight": 1.0}]},
                    to=[{"bone_id": "b", "weight": 1.0}],
                )
            ],
        )
        assert len(wm.gradients) == 1

    def test_overrides_only_valid(self):
        wm = WeightMap(
            primitive_id="p1",
            overrides=[
                VertexOverride(vertices=[0, 1], bones=[BoneWeight(bone_id="a", weight=1.0)])
            ],
        )
        assert len(wm.overrides) == 1

    def test_source_only_valid(self):
        wm = WeightMap(primitive_id="p1", source="weights.json")
        assert wm.source == "weights.json"


class TestWeightMapYAMLRoundTrip:
    def test_parse_yaml_with_weight_maps(self):
        yaml_str = """\
version: "0.3"
meshes:
  - id: m1
    primitives:
      - type: box
        id: p1
        dimensions: { x: 1, y: 1, z: 1 }
armatures:
  - id: a1
    bones:
      - id: root
        parent: none
        head: [0, 0, 0]
        tail: [0, 1, 0]
      - id: child
        parent: root
        head: [0, 1, 0]
        tail: [0, 2, 0]
bindings:
  - mesh_id: m1
    armature_id: a1
    weights: []
    weight_maps:
      - primitive_id: p1
        gradients:
          - axis: y
            range: [0.0, 1.0]
            from:
              - bone_id: root
                weight: 1.0
            to:
              - bone_id: child
                weight: 1.0
"""
        from rigy.parser import parse_yaml

        spec = parse_yaml(yaml_str)
        assert spec.bindings[0].weight_maps is not None
        assert len(spec.bindings[0].weight_maps) == 1
        wm = spec.bindings[0].weight_maps[0]
        assert wm.primitive_id == "p1"
        assert len(wm.gradients) == 1
        assert wm.gradients[0].axis == "y"


class TestSkinningDefaultBinding:
    def test_unweighted_verts_get_root_bone(self):
        arm = _arm_with_3_bones()
        binding = Binding(mesh_id="m", armature_id="arm", weights=[])
        prim_ranges = {"p1": (0, 5)}
        sd = compute_skinning(binding, arm, prim_ranges, 5)
        # Root bone is index 0; all verts should get root w=1.0
        assert np.all(sd.joints[:, 0] == 0)
        assert_allclose(sd.weights[:, 0], 1.0)


class TestSkinningGradients:
    def _make_positions_y(self, n, y_values):
        """Create positions with specified Y values."""
        pos = np.zeros((n, 3), dtype=np.float32)
        pos[:, 1] = y_values
        return pos

    def test_gradient_linear_interpolation(self):
        arm = _arm_with_3_bones()
        binding = Binding(
            mesh_id="m",
            armature_id="arm",
            weights=[],
            weight_maps=[
                WeightMap(
                    primitive_id="p1",
                    gradients=[
                        Gradient(
                            axis="y",
                            range=(0.0, 2.0),
                            from_=[BoneWeight(bone_id="root", weight=1.0)],
                            to=[BoneWeight(bone_id="mid", weight=1.0)],
                        )
                    ],
                )
            ],
        )
        # 3 vertices at y=0, y=1, y=2
        positions = self._make_positions_y(3, [0.0, 1.0, 2.0])
        prim_ranges = {"p1": (0, 3)}
        sd = compute_skinning(
            binding, arm, prim_ranges, 3, positions=positions,
        )
        # y=0 -> t=0 -> root:1.0
        assert sd.joints[0, 0] == 0  # root
        assert_allclose(sd.weights[0, 0], 1.0, atol=1e-5)

        # y=2 -> t=1 -> mid:1.0
        assert sd.joints[2, 0] == 1  # mid
        assert_allclose(sd.weights[2, 0], 1.0, atol=1e-5)

        # y=1 -> t=0.5 -> root:0.5, mid:0.5
        w_sum = sd.weights[1, :2].sum()
        assert_allclose(w_sum, 1.0, atol=1e-5)

    def test_gradient_clamping(self):
        arm = _arm_with_3_bones()
        binding = Binding(
            mesh_id="m",
            armature_id="arm",
            weights=[],
            weight_maps=[
                WeightMap(
                    primitive_id="p1",
                    gradients=[
                        Gradient(
                            axis="y",
                            range=(1.0, 2.0),
                            from_=[BoneWeight(bone_id="root", weight=1.0)],
                            to=[BoneWeight(bone_id="mid", weight=1.0)],
                        )
                    ],
                )
            ],
        )
        # Vertex below range -> clamped to t=0
        positions = self._make_positions_y(2, [0.0, 3.0])
        prim_ranges = {"p1": (0, 2)}
        sd = compute_skinning(binding, arm, prim_ranges, 2, positions=positions)
        # y=0 -> t clamped to 0 -> root:1.0
        assert sd.joints[0, 0] == 0
        assert_allclose(sd.weights[0, 0], 1.0, atol=1e-5)
        # y=3 -> t clamped to 1 -> mid:1.0
        assert sd.joints[1, 0] == 1
        assert_allclose(sd.weights[1, 0], 1.0, atol=1e-5)

    def test_full_lerp_midpoint(self):
        arm = _arm_with_3_bones()
        binding = Binding(
            mesh_id="m",
            armature_id="arm",
            weights=[],
            weight_maps=[
                WeightMap(
                    primitive_id="p1",
                    gradients=[
                        Gradient(
                            axis="y",
                            range=(0.0, 1.0),
                            from_=[BoneWeight(bone_id="root", weight=1.0)],
                            to=[BoneWeight(bone_id="mid", weight=1.0)],
                        )
                    ],
                )
            ],
        )
        positions = self._make_positions_y(1, [0.5])
        prim_ranges = {"p1": (0, 1)}
        sd = compute_skinning(binding, arm, prim_ranges, 1, positions=positions)
        # Midpoint: root:0.5, mid:0.5 (normalized)
        assert_allclose(sd.weights[0, 0], 0.5, atol=1e-5)
        assert_allclose(sd.weights[0, 1], 0.5, atol=1e-5)

    def test_multiple_gradients_last_wins(self):
        arm = _arm_with_3_bones()
        binding = Binding(
            mesh_id="m",
            armature_id="arm",
            weights=[],
            weight_maps=[
                WeightMap(
                    primitive_id="p1",
                    gradients=[
                        Gradient(
                            axis="y",
                            range=(0.0, 1.0),
                            from_=[BoneWeight(bone_id="root", weight=1.0)],
                            to=[BoneWeight(bone_id="mid", weight=1.0)],
                        ),
                        Gradient(
                            axis="y",
                            range=(0.0, 1.0),
                            from_=[BoneWeight(bone_id="mid", weight=1.0)],
                            to=[BoneWeight(bone_id="tip", weight=1.0)],
                        ),
                    ],
                )
            ],
        )
        positions = self._make_positions_y(1, [0.0])
        prim_ranges = {"p1": (0, 1)}
        sd = compute_skinning(binding, arm, prim_ranges, 1, positions=positions)
        # Second gradient at t=0: mid:1.0
        assert sd.joints[0, 0] == 1  # mid
        assert_allclose(sd.weights[0, 0], 1.0, atol=1e-5)


class TestSkinningOverrides:
    def test_override_replaces_gradient(self):
        arm = _arm_with_3_bones()
        binding = Binding(
            mesh_id="m",
            armature_id="arm",
            weights=[],
            weight_maps=[
                WeightMap(
                    primitive_id="p1",
                    gradients=[
                        Gradient(
                            axis="y",
                            range=(0.0, 1.0),
                            from_=[BoneWeight(bone_id="root", weight=1.0)],
                            to=[BoneWeight(bone_id="mid", weight=1.0)],
                        )
                    ],
                    overrides=[
                        VertexOverride(
                            vertices=[0],
                            bones=[BoneWeight(bone_id="tip", weight=1.0)],
                        )
                    ],
                )
            ],
        )
        positions = np.zeros((3, 3), dtype=np.float32)
        prim_ranges = {"p1": (0, 3)}
        sd = compute_skinning(binding, arm, prim_ranges, 3, positions=positions)
        # Vertex 0: override -> tip (index 2)
        assert sd.joints[0, 0] == 2
        assert_allclose(sd.weights[0, 0], 1.0, atol=1e-5)

    def test_override_specific_vertices(self):
        arm = _arm_with_3_bones()
        binding = Binding(
            mesh_id="m",
            armature_id="arm",
            weights=[
                PrimitiveWeights(
                    primitive_id="p1",
                    bones=[BoneWeight(bone_id="root", weight=1.0)],
                )
            ],
            weight_maps=[
                WeightMap(
                    primitive_id="p1",
                    overrides=[
                        VertexOverride(
                            vertices=[1],
                            bones=[BoneWeight(bone_id="tip", weight=1.0)],
                        )
                    ],
                )
            ],
        )
        prim_ranges = {"p1": (0, 3)}
        sd = compute_skinning(binding, arm, prim_ranges, 3)
        # Vertex 0: per-primitive -> root
        assert sd.joints[0, 0] == 0
        # Vertex 1: override -> tip
        assert sd.joints[1, 0] == 2
        # Vertex 2: per-primitive -> root
        assert sd.joints[2, 0] == 0

    def test_override_out_of_bounds_raises(self):
        arm = _arm_with_3_bones()
        binding = Binding(
            mesh_id="m",
            armature_id="arm",
            weights=[],
            weight_maps=[
                WeightMap(
                    primitive_id="p1",
                    overrides=[
                        VertexOverride(
                            vertices=[10],
                            bones=[BoneWeight(bone_id="root", weight=1.0)],
                        )
                    ],
                )
            ],
        )
        prim_ranges = {"p1": (0, 3)}
        with pytest.raises(ExportError, match="out of bounds"):
            compute_skinning(binding, arm, prim_ranges, 3)


class TestSkinningExternalJSON:
    def test_load_external_weights(self, tmp_path):
        arm = _arm_with_3_bones()
        json_data = {
            "primitive_id": "p1",
            "vertex_count": 3,
            "weights": [
                {"vertex": 0, "bones": [{"bone_id": "tip", "weight": 1.0}]},
                {"vertex": 2, "bones": [{"bone_id": "mid", "weight": 0.5}, {"bone_id": "tip", "weight": 0.5}]},
            ],
        }
        json_path = tmp_path / "weights.json"
        json_path.write_text(json.dumps(json_data))

        binding = Binding(
            mesh_id="m",
            armature_id="arm",
            weights=[],
            weight_maps=[
                WeightMap(primitive_id="p1", source="weights.json")
            ],
        )
        prim_ranges = {"p1": (0, 3)}
        sd = compute_skinning(binding, arm, prim_ranges, 3, yaml_dir=tmp_path)
        # Vertex 0: external -> tip
        assert sd.joints[0, 0] == 2
        # Vertex 1: not in external -> falls through to default (root)
        assert sd.joints[1, 0] == 0
        # Vertex 2: external -> mid:0.5, tip:0.5
        assert_allclose(sd.weights[2, 0], 0.5, atol=1e-5)

    def test_external_vertex_count_mismatch(self, tmp_path):
        arm = _arm_with_3_bones()
        json_data = {"primitive_id": "p1", "vertex_count": 999, "weights": []}
        json_path = tmp_path / "weights.json"
        json_path.write_text(json.dumps(json_data))

        binding = Binding(
            mesh_id="m",
            armature_id="arm",
            weights=[],
            weight_maps=[WeightMap(primitive_id="p1", source="weights.json")],
        )
        prim_ranges = {"p1": (0, 3)}
        with pytest.raises(ExportError, match="vertex_count mismatch"):
            compute_skinning(binding, arm, prim_ranges, 3, yaml_dir=tmp_path)


class TestSkinningInfluenceSortAndCap:
    def test_sort_by_weight_desc_then_bone_id_asc(self):
        arm = Armature(
            id="arm",
            bones=[
                Bone(id="a", parent="none", head=(0, 0, 0), tail=(0, 1, 0)),
                Bone(id="b", parent="a", head=(0, 1, 0), tail=(0, 2, 0)),
                Bone(id="c", parent="a", head=(0, 1, 0), tail=(0, 0, 1)),
            ],
        )
        binding = Binding(
            mesh_id="m",
            armature_id="arm",
            weights=[
                PrimitiveWeights(
                    primitive_id="p1",
                    bones=[
                        BoneWeight(bone_id="c", weight=0.5),
                        BoneWeight(bone_id="a", weight=0.5),
                    ],
                )
            ],
        )
        prim_ranges = {"p1": (0, 1)}
        sd = compute_skinning(binding, arm, prim_ranges, 1)
        # Both weight=0.5, so sorted by bone_id: "a" (idx 0) before "c" (idx 2)
        assert sd.joints[0, 0] == 0  # "a"
        assert sd.joints[0, 1] == 2  # "c"

    def test_cap_to_4_with_warning(self):
        bones = [
            Bone(id=f"b{i}", parent="none" if i == 0 else "b0",
                 head=(0, i, 0), tail=(0, i + 1, 0))
            for i in range(6)
        ]
        arm = Armature(id="arm", bones=bones)
        binding = Binding(
            mesh_id="m",
            armature_id="arm",
            weights=[],
            weight_maps=[
                WeightMap(
                    primitive_id="p1",
                    overrides=[
                        VertexOverride(
                            vertices=[0],
                            bones=[BoneWeight(bone_id=f"b{i}", weight=0.2) for i in range(5)],
                        )
                    ],
                )
            ],
        )
        prim_ranges = {"p1": (0, 1)}
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            sd = compute_skinning(binding, arm, prim_ranges, 1)
            cap_warnings = [x for x in w if "capping to 4" in str(x.message)]
            assert len(cap_warnings) >= 1

        # Only 4 joints kept, weights normalized
        assert_allclose(sd.weights[0].sum(), 1.0, atol=1e-5)

    def test_normalize_after_cap(self):
        arm = _arm_with_3_bones()
        binding = Binding(
            mesh_id="m",
            armature_id="arm",
            weights=[
                PrimitiveWeights(
                    primitive_id="p1",
                    bones=[
                        BoneWeight(bone_id="root", weight=0.3),
                        BoneWeight(bone_id="mid", weight=0.3),
                    ],
                )
            ],
        )
        prim_ranges = {"p1": (0, 1)}
        sd = compute_skinning(binding, arm, prim_ranges, 1)
        assert_allclose(sd.weights[0].sum(), 1.0, atol=1e-5)

    def test_zero_weights_fallback_to_root(self):
        arm = _arm_with_3_bones()
        binding = Binding(
            mesh_id="m",
            armature_id="arm",
            weights=[
                PrimitiveWeights(
                    primitive_id="p1",
                    bones=[BoneWeight(bone_id="root", weight=0.0)],
                )
            ],
        )
        prim_ranges = {"p1": (0, 1)}
        sd = compute_skinning(binding, arm, prim_ranges, 1)
        # Zero weight should fall back to root w=1.0
        assert sd.joints[0, 0] == 0
        assert_allclose(sd.weights[0, 0], 1.0, atol=1e-5)


class TestSkinningPWAndWMWarning:
    def test_pw_and_wm_same_primitive_warns(self):
        spec = _make_spec(
            meshes=[
                {
                    "id": "m1",
                    "primitives": [
                        {"type": "box", "id": "p1", "dimensions": {"x": 1, "y": 1, "z": 1}}
                    ],
                }
            ],
            armatures=[
                {
                    "id": "a1",
                    "bones": [
                        {"id": "root", "parent": "none", "head": [0, 0, 0], "tail": [0, 1, 0]}
                    ],
                }
            ],
            bindings=[
                {
                    "mesh_id": "m1",
                    "armature_id": "a1",
                    "weights": [
                        {"primitive_id": "p1", "bones": [{"bone_id": "root", "weight": 1.0}]}
                    ],
                    "weight_maps": [
                        {
                            "primitive_id": "p1",
                            "overrides": [
                                {"vertices": [0], "bones": [{"bone_id": "root", "weight": 1.0}]}
                            ],
                        }
                    ],
                }
            ],
        )
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            validate(spec)
            overlap_warnings = [x for x in w if "both per-primitive" in str(x.message)]
            assert len(overlap_warnings) == 1


class TestFixtureCompiles:
    def test_arm_weight_maps_compiles(self, tmp_path):
        from rigy.parser import parse_yaml
        from rigy.symmetry import expand_symmetry
        from rigy.exporter import export_gltf

        fixture = Path(__file__).parent / "fixtures" / "arm_weight_maps.rigy.yaml"
        spec = parse_yaml(fixture)
        spec = expand_symmetry(spec)
        validate(spec)
        out = tmp_path / "arm.glb"
        export_gltf(spec, out, yaml_dir=fixture.parent)
        assert out.exists()
        assert out.stat().st_size > 0

    def test_arm_weight_maps_deterministic(self, tmp_path):
        from rigy.parser import parse_yaml
        from rigy.symmetry import expand_symmetry
        from rigy.exporter import export_gltf

        fixture = Path(__file__).parent / "fixtures" / "arm_weight_maps.rigy.yaml"
        spec = parse_yaml(fixture)
        spec = expand_symmetry(spec)
        validate(spec)
        out1 = tmp_path / "a.glb"
        out2 = tmp_path / "b.glb"
        export_gltf(spec, out1, yaml_dir=fixture.parent)
        export_gltf(spec, out2, yaml_dir=fixture.parent)
        assert out1.read_bytes() == out2.read_bytes()
