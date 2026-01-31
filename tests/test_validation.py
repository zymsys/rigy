"""Tests for semantic validation."""

import pytest
import yaml

from rigy.errors import ValidationError
from rigy.models import RigySpec
from rigy.validation import validate


def _make_spec(**overrides) -> RigySpec:
    """Helper to create a spec with overrides."""
    base = {
        "version": "0.1",
        "units": "meters",
        "coordinate_system": {"up": "Y", "forward": "-Z", "handedness": "right"},
        "tessellation_profile": "v0_1_default",
    }
    base.update(overrides)
    return RigySpec(**base)


class TestValidation:
    def test_valid_minimal_passes(self, minimal_mesh_yaml):
        spec = RigySpec(**yaml.safe_load(minimal_mesh_yaml))
        validate(spec)  # should not raise

    def test_valid_full_passes(self, full_humanoid_yaml):
        from rigy.symmetry import expand_symmetry

        spec = RigySpec(**yaml.safe_load(full_humanoid_yaml))
        spec = expand_symmetry(spec)
        validate(spec)  # should not raise

    def test_mesh_only_is_valid(self):
        spec = _make_spec(
            meshes=[
                {
                    "id": "m1",
                    "primitives": [
                        {"type": "box", "id": "p1", "dimensions": {"x": 1, "y": 1, "z": 1}}
                    ],
                }
            ]
        )
        validate(spec)  # should not raise

    def test_duplicate_mesh_id(self):
        spec = _make_spec(
            meshes=[
                {
                    "id": "m1",
                    "primitives": [
                        {"type": "box", "id": "p1", "dimensions": {"x": 1, "y": 1, "z": 1}}
                    ],
                },
                {
                    "id": "m1",
                    "primitives": [
                        {"type": "box", "id": "p2", "dimensions": {"x": 1, "y": 1, "z": 1}}
                    ],
                },
            ]
        )
        with pytest.raises(ValidationError, match="Duplicate mesh id"):
            validate(spec)

    def test_duplicate_primitive_id_within_mesh(self):
        spec = _make_spec(
            meshes=[
                {
                    "id": "m1",
                    "primitives": [
                        {"type": "box", "id": "p1", "dimensions": {"x": 1, "y": 1, "z": 1}},
                        {"type": "box", "id": "p1", "dimensions": {"x": 1, "y": 1, "z": 1}},
                    ],
                }
            ]
        )
        with pytest.raises(ValidationError, match="Duplicate primitive id"):
            validate(spec)

    def test_duplicate_armature_id(self):
        spec = _make_spec(
            armatures=[
                {
                    "id": "a1",
                    "bones": [
                        {"id": "root", "parent": "none", "head": [0, 0, 0], "tail": [0, 1, 0]}
                    ],
                },
                {
                    "id": "a1",
                    "bones": [
                        {"id": "root", "parent": "none", "head": [0, 0, 0], "tail": [0, 1, 0]}
                    ],
                },
            ]
        )
        with pytest.raises(ValidationError, match="Duplicate armature id"):
            validate(spec)

    def test_duplicate_bone_id(self):
        spec = _make_spec(
            armatures=[
                {
                    "id": "a1",
                    "bones": [
                        {"id": "root", "parent": "none", "head": [0, 0, 0], "tail": [0, 1, 0]},
                        {"id": "root", "parent": "none", "head": [0, 0, 0], "tail": [0, 1, 0]},
                    ],
                }
            ]
        )
        with pytest.raises(ValidationError, match="Duplicate bone id"):
            validate(spec)

    def test_bone_cycle_detected(self):
        spec = _make_spec(
            armatures=[
                {
                    "id": "a1",
                    "bones": [
                        {"id": "a", "parent": "b", "head": [0, 0, 0], "tail": [0, 1, 0]},
                        {"id": "b", "parent": "a", "head": [0, 1, 0], "tail": [0, 2, 0]},
                    ],
                }
            ]
        )
        with pytest.raises(ValidationError, match="Cycle"):
            validate(spec)

    def test_zero_length_bone(self):
        spec = _make_spec(
            armatures=[
                {
                    "id": "a1",
                    "bones": [
                        {"id": "root", "parent": "none", "head": [0, 0, 0], "tail": [0, 0, 0]},
                    ],
                }
            ]
        )
        with pytest.raises(ValidationError, match="Zero-length"):
            validate(spec)

    def test_non_positive_dimension(self):
        spec = _make_spec(
            meshes=[
                {
                    "id": "m1",
                    "primitives": [
                        {"type": "box", "id": "p1", "dimensions": {"x": 0, "y": 1, "z": 1}},
                    ],
                }
            ]
        )
        with pytest.raises(ValidationError, match="non-positive"):
            validate(spec)

    def test_binding_unknown_mesh(self):
        spec = _make_spec(
            armatures=[
                {
                    "id": "a1",
                    "bones": [
                        {"id": "root", "parent": "none", "head": [0, 0, 0], "tail": [0, 1, 0]}
                    ],
                },
            ],
            bindings=[
                {
                    "mesh_id": "nonexistent",
                    "armature_id": "a1",
                    "weights": [],
                }
            ],
        )
        with pytest.raises(ValidationError, match="unknown mesh"):
            validate(spec)

    def test_binding_unknown_armature(self):
        spec = _make_spec(
            meshes=[
                {
                    "id": "m1",
                    "primitives": [
                        {"type": "box", "id": "p1", "dimensions": {"x": 1, "y": 1, "z": 1}}
                    ],
                },
            ],
            bindings=[
                {
                    "mesh_id": "m1",
                    "armature_id": "nonexistent",
                    "weights": [],
                }
            ],
        )
        with pytest.raises(ValidationError, match="unknown armature"):
            validate(spec)

    def test_binding_unknown_primitive(self):
        spec = _make_spec(
            meshes=[
                {
                    "id": "m1",
                    "primitives": [
                        {"type": "box", "id": "p1", "dimensions": {"x": 1, "y": 1, "z": 1}}
                    ],
                },
            ],
            armatures=[
                {
                    "id": "a1",
                    "bones": [
                        {"id": "root", "parent": "none", "head": [0, 0, 0], "tail": [0, 1, 0]}
                    ],
                },
            ],
            bindings=[
                {
                    "mesh_id": "m1",
                    "armature_id": "a1",
                    "weights": [{"primitive_id": "nonexistent", "bones": []}],
                }
            ],
        )
        with pytest.raises(ValidationError, match="unknown primitive"):
            validate(spec)

    def test_binding_unknown_bone(self):
        spec = _make_spec(
            meshes=[
                {
                    "id": "m1",
                    "primitives": [
                        {"type": "box", "id": "p1", "dimensions": {"x": 1, "y": 1, "z": 1}}
                    ],
                },
            ],
            armatures=[
                {
                    "id": "a1",
                    "bones": [
                        {"id": "root", "parent": "none", "head": [0, 0, 0], "tail": [0, 1, 0]}
                    ],
                },
            ],
            bindings=[
                {
                    "mesh_id": "m1",
                    "armature_id": "a1",
                    "weights": [
                        {
                            "primitive_id": "p1",
                            "bones": [{"bone_id": "nonexistent", "weight": 1.0}],
                        }
                    ],
                }
            ],
        )
        with pytest.raises(ValidationError, match="unknown bone"):
            validate(spec)

    def test_mesh_in_multiple_bindings(self):
        spec = _make_spec(
            meshes=[
                {
                    "id": "m1",
                    "primitives": [
                        {"type": "box", "id": "p1", "dimensions": {"x": 1, "y": 1, "z": 1}}
                    ],
                },
            ],
            armatures=[
                {
                    "id": "a1",
                    "bones": [
                        {"id": "root", "parent": "none", "head": [0, 0, 0], "tail": [0, 1, 0]}
                    ],
                },
                {
                    "id": "a2",
                    "bones": [
                        {"id": "root", "parent": "none", "head": [0, 0, 0], "tail": [0, 1, 0]}
                    ],
                },
            ],
            bindings=[
                {"mesh_id": "m1", "armature_id": "a1", "weights": []},
                {"mesh_id": "m1", "armature_id": "a2", "weights": []},
            ],
        )
        with pytest.raises(ValidationError, match="multiple bindings"):
            validate(spec)

    def test_weight_out_of_range(self):
        spec = _make_spec(
            meshes=[
                {
                    "id": "m1",
                    "primitives": [
                        {"type": "box", "id": "p1", "dimensions": {"x": 1, "y": 1, "z": 1}}
                    ],
                },
            ],
            armatures=[
                {
                    "id": "a1",
                    "bones": [
                        {"id": "root", "parent": "none", "head": [0, 0, 0], "tail": [0, 1, 0]}
                    ],
                },
            ],
            bindings=[
                {
                    "mesh_id": "m1",
                    "armature_id": "a1",
                    "weights": [
                        {
                            "primitive_id": "p1",
                            "bones": [{"bone_id": "root", "weight": 1.5}],
                        }
                    ],
                }
            ],
        )
        with pytest.raises(ValidationError, match="out of range"):
            validate(spec)

    def test_negative_weight(self):
        spec = _make_spec(
            meshes=[
                {
                    "id": "m1",
                    "primitives": [
                        {"type": "box", "id": "p1", "dimensions": {"x": 1, "y": 1, "z": 1}}
                    ],
                },
            ],
            armatures=[
                {
                    "id": "a1",
                    "bones": [
                        {"id": "root", "parent": "none", "head": [0, 0, 0], "tail": [0, 1, 0]}
                    ],
                },
            ],
            bindings=[
                {
                    "mesh_id": "m1",
                    "armature_id": "a1",
                    "weights": [
                        {
                            "primitive_id": "p1",
                            "bones": [{"bone_id": "root", "weight": -0.1}],
                        }
                    ],
                }
            ],
        )
        with pytest.raises(ValidationError, match="out of range"):
            validate(spec)
