"""Tests for semantic validation."""

import warnings

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

    # --- v0.2 validation tests ---

    def test_duplicate_anchor_id(self):
        from rigy.models import Anchor

        spec = _make_spec(
            anchors=[
                Anchor(id="a1", translation=(0, 0, 0)),
                Anchor(id="a1", translation=(1, 0, 0)),
            ],
        )
        with pytest.raises(ValidationError, match="Duplicate anchor id"):
            validate(spec)

    def test_unique_anchors_pass(self):
        from rigy.models import Anchor

        spec = _make_spec(
            anchors=[
                Anchor(id="a1", translation=(0, 0, 0)),
                Anchor(id="a2", translation=(1, 0, 0)),
            ],
        )
        validate(spec)  # should not raise

    def test_duplicate_instance_id(self):
        from rigy.models import Attach3, ImportDef, Instance

        spec = _make_spec(
            imports={"w": ImportDef(source="w.rigy.yaml")},
            instances=[
                Instance(
                    id="i1",
                    import_="w",
                    attach3=Attach3(from_=["a", "b", "c"], to=["d", "e", "f"], mode="rigid"),
                ),
                Instance(
                    id="i1",
                    import_="w",
                    attach3=Attach3(from_=["a", "b", "c"], to=["d", "e", "f"], mode="rigid"),
                ),
            ],
        )
        with pytest.raises(ValidationError, match="Duplicate instance id"):
            validate(spec)

    def test_instance_unknown_import(self):
        from rigy.models import Attach3, Instance

        spec = _make_spec(
            instances=[
                Instance(
                    id="i1",
                    import_="nonexistent",
                    attach3=Attach3(from_=["a", "b", "c"], to=["d", "e", "f"], mode="rigid"),
                ),
            ],
        )
        with pytest.raises(ValidationError, match="unknown import"):
            validate(spec)

    def test_id_collision_mesh_anchor(self):
        from rigy.models import Anchor

        spec = _make_spec(
            meshes=[
                {
                    "id": "shared_id",
                    "primitives": [
                        {"type": "box", "id": "p1", "dimensions": {"x": 1, "y": 1, "z": 1}}
                    ],
                }
            ],
            anchors=[Anchor(id="shared_id", translation=(0, 0, 0))],
        )
        with pytest.raises(ValidationError, match="ID collision"):
            validate(spec)

    def test_no_collision_when_ids_distinct(self):
        from rigy.models import Anchor

        spec = _make_spec(
            meshes=[
                {
                    "id": "mesh1",
                    "primitives": [
                        {"type": "box", "id": "p1", "dimensions": {"x": 1, "y": 1, "z": 1}}
                    ],
                }
            ],
            anchors=[Anchor(id="anchor1", translation=(0, 0, 0))],
        )
        validate(spec)  # should not raise

    # --- Local mesh instance validation ---

    def test_local_mesh_instance_valid(self):
        from rigy.models import Instance

        spec = _make_spec(
            meshes=[
                {
                    "id": "shelf",
                    "primitives": [
                        {"type": "box", "id": "p1", "dimensions": {"x": 1, "y": 1, "z": 1}}
                    ],
                }
            ],
            instances=[Instance(id="shelf_copy", mesh_id="shelf")],
        )
        validate(spec)  # should not raise

    def test_local_mesh_instance_unknown_mesh(self):
        from rigy.models import Instance

        spec = _make_spec(
            instances=[Instance(id="bad_copy", mesh_id="nonexistent")],
        )
        with pytest.raises(ValidationError, match="unknown mesh"):
            validate(spec)

    def test_local_mesh_instance_no_import_check(self):
        """Local mesh instances should not trigger import ref check."""
        from rigy.models import Instance

        spec = _make_spec(
            meshes=[
                {
                    "id": "shelf",
                    "primitives": [
                        {"type": "box", "id": "p1", "dimensions": {"x": 1, "y": 1, "z": 1}}
                    ],
                }
            ],
            instances=[Instance(id="shelf_copy", mesh_id="shelf")],
        )
        validate(spec)  # should not raise (no import check for local mesh)

    # --- Armature root warning ---

    def test_armature_root_at_origin_no_warning(self):
        spec = _make_spec(
            armatures=[
                {
                    "id": "a1",
                    "bones": [
                        {"id": "root", "parent": "none", "head": [0, 0, 0], "tail": [0, 1, 0]}
                    ],
                }
            ]
        )
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            validate(spec)
            armature_warnings = [x for x in w if "armature root" in str(x.message).lower()]
            assert len(armature_warnings) == 0

    # --- v0.3 weight map validation tests ---

    def test_weight_map_unknown_primitive(self):
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
                    "weights": [],
                    "weight_maps": [
                        {
                            "primitive_id": "nonexistent",
                            "overrides": [
                                {"vertices": [0], "bones": [{"bone_id": "root", "weight": 1.0}]}
                            ],
                        }
                    ],
                }
            ],
        )
        with pytest.raises(ValidationError, match="unknown primitive"):
            validate(spec)

    def test_weight_map_unknown_bone_in_gradient(self):
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
                    "weights": [],
                    "weight_maps": [
                        {
                            "primitive_id": "p1",
                            "gradients": [
                                {
                                    "axis": "y",
                                    "range": [0, 1],
                                    "from": [{"bone_id": "bad_bone", "weight": 1.0}],
                                    "to": [{"bone_id": "root", "weight": 1.0}],
                                }
                            ],
                        }
                    ],
                }
            ],
        )
        with pytest.raises(ValidationError, match="unknown bone"):
            validate(spec)

    def test_weight_map_unknown_bone_in_override(self):
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
                    "weights": [],
                    "weight_maps": [
                        {
                            "primitive_id": "p1",
                            "overrides": [
                                {
                                    "vertices": [0],
                                    "bones": [{"bone_id": "nonexistent", "weight": 1.0}],
                                }
                            ],
                        }
                    ],
                }
            ],
        )
        with pytest.raises(ValidationError, match="unknown bone"):
            validate(spec)

    def test_weight_map_negative_weight_in_gradient(self):
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
                    "weights": [],
                    "weight_maps": [
                        {
                            "primitive_id": "p1",
                            "gradients": [
                                {
                                    "axis": "y",
                                    "range": [0, 1],
                                    "from": [{"bone_id": "root", "weight": -0.5}],
                                    "to": [{"bone_id": "root", "weight": 1.0}],
                                }
                            ],
                        }
                    ],
                }
            ],
        )
        with pytest.raises(ValidationError, match="out of range"):
            validate(spec)

    def test_weight_map_valid_passes(self):
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
                        {"id": "root", "parent": "none", "head": [0, 0, 0], "tail": [0, 1, 0]},
                        {"id": "child", "parent": "root", "head": [0, 1, 0], "tail": [0, 2, 0]},
                    ],
                }
            ],
            bindings=[
                {
                    "mesh_id": "m1",
                    "armature_id": "a1",
                    "weights": [],
                    "weight_maps": [
                        {
                            "primitive_id": "p1",
                            "gradients": [
                                {
                                    "axis": "y",
                                    "range": [0, 1],
                                    "from": [{"bone_id": "root", "weight": 1.0}],
                                    "to": [{"bone_id": "child", "weight": 1.0}],
                                }
                            ],
                        }
                    ],
                }
            ],
        )
        validate(spec)  # should not raise

    def test_armature_root_not_at_origin_warns(self):
        spec = _make_spec(
            armatures=[
                {
                    "id": "a1",
                    "bones": [
                        {"id": "root", "parent": "none", "head": [0, 0.9, 0], "tail": [0, 1.0, 0]}
                    ],
                }
            ]
        )
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            validate(spec)
            armature_warnings = [x for x in w if "root bone" in str(x.message)]
            assert len(armature_warnings) == 1
            assert "a1" in str(armature_warnings[0].message)

    # --- V32: NaN / ±Infinity check ---

    def test_nan_in_primitive_dimensions(self):
        spec = _make_spec(
            meshes=[
                {
                    "id": "m1",
                    "primitives": [
                        {"type": "sphere", "id": "p1", "dimensions": {"radius": float("nan")}}
                    ],
                }
            ]
        )
        with pytest.raises(ValidationError, match="Non-finite"):
            validate(spec)

    def test_infinity_in_bone_head(self):
        spec = _make_spec(
            armatures=[
                {
                    "id": "a1",
                    "bones": [
                        {
                            "id": "root",
                            "parent": "none",
                            "head": [float("inf"), 0, 0],
                            "tail": [0, 1, 0],
                        }
                    ],
                }
            ]
        )
        with pytest.raises(ValidationError, match="Non-finite"):
            validate(spec)

    def test_neg_infinity_in_translation(self):
        spec = _make_spec(
            meshes=[
                {
                    "id": "m1",
                    "primitives": [
                        {
                            "type": "box",
                            "id": "p1",
                            "dimensions": {"x": 1, "y": 1, "z": 1},
                            "transform": {"translation": [0, float("-inf"), 0]},
                        }
                    ],
                }
            ]
        )
        with pytest.raises(ValidationError, match="Non-finite"):
            validate(spec)

    def test_nan_in_bone_weight(self):
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
                        {
                            "primitive_id": "p1",
                            "bones": [{"bone_id": "root", "weight": float("nan")}],
                        }
                    ],
                }
            ],
        )
        with pytest.raises(ValidationError, match="Non-finite"):
            validate(spec)

    def test_finite_values_pass(self):
        """All finite values should pass V32."""
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


class TestV35:
    def test_dqs_rigid_bones_trivially_passes(self):
        """V35 is a structural guard — passes trivially with current Bone model."""
        spec = _make_spec(
            skinning_solver="dqs",
            armatures=[
                {
                    "id": "a1",
                    "bones": [
                        {"id": "root", "parent": "none", "head": [0, 0, 0], "tail": [0, 1, 0]}
                    ],
                }
            ],
        )
        validate(spec)  # should not raise


class TestV36:
    def test_nan_quaternion_rejected(self):
        from rigy.models import Pose, PoseBoneTransform

        spec = _make_spec(
            armatures=[
                {
                    "id": "a1",
                    "bones": [
                        {"id": "root", "parent": "none", "head": [0, 0, 0], "tail": [0, 1, 0]}
                    ],
                }
            ],
            poses=[Pose(id="p1", bones={"root": PoseBoneTransform(rotation=(float("nan"), 0, 0, 0))})],
        )
        with pytest.raises(ValidationError, match="Non-finite quaternion"):
            validate(spec)

    def test_non_unit_quaternion_rejected(self):
        from rigy.models import Pose, PoseBoneTransform

        spec = _make_spec(
            armatures=[
                {
                    "id": "a1",
                    "bones": [
                        {"id": "root", "parent": "none", "head": [0, 0, 0], "tail": [0, 1, 0]}
                    ],
                }
            ],
            poses=[Pose(id="p1", bones={"root": PoseBoneTransform(rotation=(2.0, 0, 0, 0))})],
        )
        with pytest.raises(ValidationError, match="Non-unit quaternion"):
            validate(spec)

    def test_infinity_quaternion_rejected(self):
        from rigy.models import Pose, PoseBoneTransform

        spec = _make_spec(
            armatures=[
                {
                    "id": "a1",
                    "bones": [
                        {"id": "root", "parent": "none", "head": [0, 0, 0], "tail": [0, 1, 0]}
                    ],
                }
            ],
            poses=[Pose(id="p1", bones={"root": PoseBoneTransform(rotation=(float("inf"), 0, 0, 0))})],
        )
        with pytest.raises(ValidationError, match="Non-finite quaternion"):
            validate(spec)

    def test_non_finite_translation_rejected(self):
        from rigy.models import Pose, PoseBoneTransform

        spec = _make_spec(
            armatures=[
                {
                    "id": "a1",
                    "bones": [
                        {"id": "root", "parent": "none", "head": [0, 0, 0], "tail": [0, 1, 0]}
                    ],
                }
            ],
            poses=[Pose(id="p1", bones={"root": PoseBoneTransform(translation=(0, float("inf"), 0))})],
        )
        with pytest.raises(ValidationError, match="Non-finite translation"):
            validate(spec)

    def test_valid_quaternion_passes(self):
        from rigy.models import Pose, PoseBoneTransform

        spec = _make_spec(
            armatures=[
                {
                    "id": "a1",
                    "bones": [
                        {"id": "root", "parent": "none", "head": [0, 0, 0], "tail": [0, 1, 0]}
                    ],
                }
            ],
            poses=[Pose(id="p1", bones={"root": PoseBoneTransform(rotation=(1.0, 0, 0, 0))})],
        )
        validate(spec)  # should not raise


class TestPoseBoneRefs:
    def test_invalid_bone_ref(self):
        from rigy.models import Pose, PoseBoneTransform

        spec = _make_spec(
            armatures=[
                {
                    "id": "a1",
                    "bones": [
                        {"id": "root", "parent": "none", "head": [0, 0, 0], "tail": [0, 1, 0]}
                    ],
                }
            ],
            poses=[Pose(id="p1", bones={"nonexistent": PoseBoneTransform(rotation=(1.0, 0, 0, 0))})],
        )
        with pytest.raises(ValidationError, match="unknown bone"):
            validate(spec)

    def test_valid_bone_ref(self):
        from rigy.models import Pose, PoseBoneTransform

        spec = _make_spec(
            armatures=[
                {
                    "id": "a1",
                    "bones": [
                        {"id": "root", "parent": "none", "head": [0, 0, 0], "tail": [0, 1, 0]}
                    ],
                }
            ],
            poses=[Pose(id="p1", bones={"root": PoseBoneTransform(rotation=(1.0, 0, 0, 0))})],
        )
        validate(spec)  # should not raise
