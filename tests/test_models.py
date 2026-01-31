"""Tests for Pydantic schema models."""

import pytest
from pydantic import ValidationError

from rigy.models import (
    Armature,
    Binding,
    Bone,
    BoneWeight,
    CoordinateSystem,
    Mesh,
    MirrorX,
    Primitive,
    PrimitiveWeights,
    RigySpec,
    Symmetry,
    Transform,
)


class TestCoordinateSystem:
    def test_valid(self):
        cs = CoordinateSystem(up="Y", forward="-Z", handedness="right")
        assert cs.up == "Y"
        assert cs.forward == "-Z"
        assert cs.handedness == "right"

    def test_invalid_up(self):
        with pytest.raises(ValidationError):
            CoordinateSystem(up="Z", forward="-Z", handedness="right")

    def test_unknown_field_rejected(self):
        with pytest.raises(ValidationError, match="extra"):
            CoordinateSystem(up="Y", forward="-Z", handedness="right", extra_field="x")


class TestTransform:
    def test_empty(self):
        t = Transform()
        assert t.translation is None
        assert t.rotation_euler is None

    def test_translation(self):
        t = Transform(translation=(1.0, 2.0, 3.0))
        assert t.translation == (1.0, 2.0, 3.0)

    def test_both(self):
        t = Transform(translation=(0, 0, 0), rotation_euler=(0.1, 0.2, 0.3))
        assert t.rotation_euler == (0.1, 0.2, 0.3)

    def test_wrong_length(self):
        with pytest.raises(ValidationError):
            Transform(translation=(1.0, 2.0))

    def test_unknown_field_rejected(self):
        with pytest.raises(ValidationError, match="extra"):
            Transform(translation=(0, 0, 0), scale=(1, 1, 1))


class TestPrimitive:
    def test_box(self):
        p = Primitive(type="box", id="torso", dimensions={"x": 1.0, "y": 2.0, "z": 0.5})
        assert p.type == "box"
        assert p.dimensions["x"] == 1.0

    def test_sphere(self):
        p = Primitive(type="sphere", id="head", dimensions={"radius": 0.5})
        assert p.type == "sphere"

    def test_cylinder(self):
        p = Primitive(type="cylinder", id="leg", dimensions={"radius": 0.1, "height": 0.5})
        assert p.type == "cylinder"

    def test_capsule(self):
        p = Primitive(type="capsule", id="arm", dimensions={"radius": 0.1, "height": 0.5})
        assert p.type == "capsule"

    def test_invalid_type(self):
        with pytest.raises(ValidationError):
            Primitive(type="cone", id="x", dimensions={"r": 1})

    def test_empty_dimensions_rejected(self):
        with pytest.raises(ValidationError, match="dimensions must not be empty"):
            Primitive(type="box", id="x", dimensions={})

    def test_unknown_field_rejected(self):
        with pytest.raises(ValidationError, match="extra"):
            Primitive(type="box", id="x", dimensions={"x": 1}, color="red")


class TestMesh:
    def test_valid(self):
        m = Mesh(
            id="body",
            name="Body",
            primitives=[Primitive(type="box", id="torso", dimensions={"x": 1, "y": 1, "z": 1})],
        )
        assert m.id == "body"
        assert len(m.primitives) == 1

    def test_unknown_field_rejected(self):
        with pytest.raises(ValidationError, match="extra"):
            Mesh(
                id="body",
                primitives=[],
                unknown="value",
            )


class TestBone:
    def test_valid(self):
        b = Bone(id="root", parent="none", head=(0, 0, 0), tail=(0, 1, 0), roll=0.0)
        assert b.id == "root"
        assert b.parent == "none"

    def test_default_roll(self):
        b = Bone(id="root", parent="none", head=(0, 0, 0), tail=(0, 1, 0))
        assert b.roll == 0.0


class TestArmature:
    def test_valid(self):
        a = Armature(
            id="arm1",
            name="Armature",
            bones=[Bone(id="root", parent="none", head=(0, 0, 0), tail=(0, 1, 0))],
        )
        assert a.id == "arm1"
        assert len(a.bones) == 1


class TestBinding:
    def test_valid(self):
        b = Binding(
            mesh_id="mesh1",
            armature_id="arm1",
            weights=[
                PrimitiveWeights(
                    primitive_id="torso",
                    bones=[BoneWeight(bone_id="spine", weight=1.0)],
                )
            ],
        )
        assert b.mesh_id == "mesh1"


class TestSymmetry:
    def test_empty(self):
        s = Symmetry()
        assert s.mirror_x is None

    def test_mirror_x(self):
        s = Symmetry(mirror_x=MirrorX(prefix_from="legL_", prefix_to="legR_"))
        assert s.mirror_x.prefix_from == "legL_"


class TestRigySpec:
    def test_minimal(self):
        spec = RigySpec(version="0.1")
        assert spec.version == "0.1"
        assert spec.units == "meters"
        assert spec.meshes == []

    def test_version_required(self):
        with pytest.raises(ValidationError):
            RigySpec()

    def test_unknown_field_rejected(self):
        with pytest.raises(ValidationError, match="extra"):
            RigySpec(version="0.1", imports={"wheel": {}})

    def test_full_roundtrip(self, full_humanoid_yaml):
        """Full humanoid spec parses and round-trips through model."""
        import yaml

        data = yaml.safe_load(full_humanoid_yaml)
        spec = RigySpec(**data)
        assert spec.version == "0.1"
        assert len(spec.meshes) == 1
        assert len(spec.armatures) == 1
        assert len(spec.bindings) == 1
        assert spec.symmetry is not None
