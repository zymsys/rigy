"""Tests for Pydantic schema models."""

import pytest
from pydantic import ValidationError

from rigy.models import (
    UV_ROLE_VOCABULARY,
    Anchor,
    Armature,
    Attach3,
    Binding,
    Bone,
    BoneWeight,
    CoordinateSystem,
    ImportDef,
    Instance,
    Material,
    Mesh,
    MirrorX,
    Pose,
    PoseBoneTransform,
    Primitive,
    PrimitiveWeights,
    RicyContract,
    RigySpec,
    Symmetry,
    Transform,
    UvRoleEntry,
    resolve_solver,
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
        assert t.rotation_degrees is None

    def test_translation(self):
        t = Transform(translation=(1.0, 2.0, 3.0))
        assert t.translation == (1.0, 2.0, 3.0)

    def test_both(self):
        t = Transform(translation=(0, 0, 0), rotation_euler=(0.1, 0.2, 0.3))
        assert t.rotation_euler == (0.1, 0.2, 0.3)

    def test_rotation_degrees_converted_to_euler(self):
        t = Transform(rotation_degrees=(0.0, 90.0, 180.0))
        assert t.rotation_euler == (0.0, pytest.approx(1.57079632679), pytest.approx(3.14159265359))

    def test_rotation_fields_mutually_exclusive(self):
        with pytest.raises(ValidationError, match="rotation_euler"):
            Transform(rotation_euler=(0.1, 0.2, 0.3), rotation_degrees=(10.0, 20.0, 30.0))

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
            RigySpec(version="0.1", unknown_field="value")

    def test_full_roundtrip(self, full_humanoid_yaml):
        """Full humanoid spec parses and round-trips through model."""
        import yaml

        data = yaml.safe_load(full_humanoid_yaml)
        spec = RigySpec(**data)
        assert spec.version == "0.6"
        assert len(spec.meshes) == 1
        assert len(spec.armatures) == 1
        assert len(spec.bindings) == 1
        assert spec.symmetry is not None

    def test_v02_fields_optional(self):
        """v0.2 fields default to empty, so v0.1 files still parse."""
        spec = RigySpec(version="0.1")
        assert spec.anchors == []
        assert spec.imports == {}
        assert spec.instances == []

    def test_v02_spec_with_anchors(self):
        spec = RigySpec(
            version="0.2",
            anchors=[Anchor(id="a1", translation=(0, 0, 0))],
        )
        assert len(spec.anchors) == 1
        assert spec.anchors[0].id == "a1"

    def test_geometry_checks_allowed(self):
        spec = RigySpec(
            version="0.11",
            geometry_checks={"checks": [{"id": "c1", "expr": "$missing"}]},
        )
        assert spec.geometry_checks["checks"][0]["expr"] == "$missing"


class TestSkinningSolver:
    def test_lbs_accepted(self):
        spec = RigySpec(version="0.4", skinning_solver="lbs")
        assert spec.skinning_solver == "lbs"

    def test_absent_defaults_to_none(self):
        spec = RigySpec(version="0.4")
        assert spec.skinning_solver is None

    def test_dqs_accepted(self):
        spec = RigySpec(version="0.5", skinning_solver="dqs")
        assert spec.skinning_solver == "dqs"

    def test_invalid_value_rejected(self):
        with pytest.raises(ValidationError):
            RigySpec(version="0.4", skinning_solver="invalid")


class TestAnchor:
    def test_valid(self):
        a = Anchor(id="mount_a", translation=(0, 0, 0))
        assert a.id == "mount_a"
        assert a.scope is None

    def test_with_scope(self):
        a = Anchor(id="mount_a", translation=(0, 0, 0), scope="left_door")
        assert a.scope == "left_door"

    def test_unknown_field_rejected(self):
        with pytest.raises(ValidationError, match="extra"):
            Anchor(id="a", translation=(0, 0, 0), color="red")


class TestAttach3:
    def test_valid(self):
        a = Attach3(from_=["a", "b", "c"], to=["d", "e", "f"], mode="rigid")
        assert a.from_ == ["a", "b", "c"]
        assert a.to == ["d", "e", "f"]
        assert a.mode == "rigid"

    def test_from_alias(self):
        """'from' alias works."""
        import yaml

        data = yaml.safe_load("from: [a, b, c]\nto: [d, e, f]\nmode: rigid\n")
        a = Attach3(**data)
        assert a.from_ == ["a", "b", "c"]

    def test_from_wrong_count(self):
        with pytest.raises(ValidationError, match="exactly 3"):
            Attach3(from_=["a", "b"], to=["d", "e", "f"], mode="rigid")

    def test_to_wrong_count(self):
        with pytest.raises(ValidationError, match="exactly 3"):
            Attach3(from_=["a", "b", "c"], to=["d", "e"], mode="rigid")

    def test_invalid_mode(self):
        with pytest.raises(ValidationError):
            Attach3(from_=["a", "b", "c"], to=["d", "e", "f"], mode="invalid")

    def test_all_modes(self):
        for mode in ["rigid", "uniform", "affine"]:
            a = Attach3(from_=["a", "b", "c"], to=["d", "e", "f"], mode=mode)
            assert a.mode == mode


class TestInstance:
    def test_valid(self):
        inst = Instance(
            id="wheel_fl",
            import_="wheel",
            attach3=Attach3(from_=["a", "b", "c"], to=["d", "e", "f"], mode="rigid"),
        )
        assert inst.id == "wheel_fl"
        assert inst.import_ == "wheel"

    def test_import_alias(self):
        import yaml

        data = yaml.safe_load(
            "id: w1\nimport: wheel\nattach3:\n  from: [a, b, c]\n  to: [d, e, f]\n  mode: rigid\n"
        )
        inst = Instance(**data)
        assert inst.import_ == "wheel"

    def test_local_mesh_instance(self):
        inst = Instance(id="shelf_copy", mesh_id="shelf_mesh")
        assert inst.mesh_id == "shelf_mesh"
        assert inst.import_ is None
        assert inst.attach3 is None

    def test_rejects_both_import_and_mesh_id(self):
        with pytest.raises(ValidationError, match="not both"):
            Instance(
                id="bad",
                import_="wheel",
                mesh_id="shelf",
                attach3=Attach3(from_=["a", "b", "c"], to=["d", "e", "f"], mode="rigid"),
            )

    def test_rejects_neither_import_nor_mesh_id(self):
        with pytest.raises(ValidationError, match="either"):
            Instance(id="bad")

    def test_import_without_attach3_rejected(self):
        with pytest.raises(ValidationError, match="requires 'attach3'"):
            Instance(id="bad", import_="wheel")

    def test_local_mesh_with_attach3(self):
        """Local mesh instances may optionally have attach3."""
        inst = Instance(
            id="shelf_copy",
            mesh_id="shelf_mesh",
            attach3=Attach3(from_=["a", "b", "c"], to=["d", "e", "f"], mode="rigid"),
        )
        assert inst.mesh_id == "shelf_mesh"
        assert inst.attach3 is not None


class TestImportDef:
    def test_valid(self):
        d = ImportDef(source="parts/wheel.rigy.yaml")
        assert d.source == "parts/wheel.rigy.yaml"
        assert d.contract is None

    def test_with_contract(self):
        d = ImportDef(source="parts/wheel.rigy.yaml", contract="parts/wheel.ricy.yaml")
        assert d.contract == "parts/wheel.ricy.yaml"


class TestRicyContract:
    def test_minimal(self):
        c = RicyContract(contract_version="0.1")
        assert c.required_anchors == []
        assert c.frame3_sets == {}

    def test_full(self):
        c = RicyContract(
            contract_version="0.1",
            required_anchors=["a", "b"],
            required_frame3_sets=["mount"],
            frame3_sets={"mount": ["a", "b", "c"]},
        )
        assert len(c.required_anchors) == 2
        assert c.frame3_sets["mount"] == ["a", "b", "c"]

    def test_unknown_field_rejected(self):
        with pytest.raises(ValidationError, match="extra"):
            RicyContract(contract_version="0.1", notes="hello")


class TestBindingSkinningSolver:
    def test_default_none(self):
        b = Binding(
            mesh_id="m", armature_id="a",
            weights=[PrimitiveWeights(primitive_id="p", bones=[BoneWeight(bone_id="b", weight=1.0)])],
        )
        assert b.skinning_solver is None

    def test_lbs(self):
        b = Binding(
            mesh_id="m", armature_id="a",
            weights=[PrimitiveWeights(primitive_id="p", bones=[BoneWeight(bone_id="b", weight=1.0)])],
            skinning_solver="lbs",
        )
        assert b.skinning_solver == "lbs"

    def test_dqs(self):
        b = Binding(
            mesh_id="m", armature_id="a",
            weights=[PrimitiveWeights(primitive_id="p", bones=[BoneWeight(bone_id="b", weight=1.0)])],
            skinning_solver="dqs",
        )
        assert b.skinning_solver == "dqs"

    def test_invalid_rejected(self):
        with pytest.raises(ValidationError):
            Binding(
                mesh_id="m", armature_id="a",
                weights=[PrimitiveWeights(primitive_id="p", bones=[BoneWeight(bone_id="b", weight=1.0)])],
                skinning_solver="invalid",
            )


class TestPoseModel:
    def test_valid(self):
        pose = Pose(
            id="rest",
            bones={"root": PoseBoneTransform(rotation=(1.0, 0.0, 0.0, 0.0))},
        )
        assert pose.id == "rest"
        assert pose.bones["root"].rotation == (1.0, 0.0, 0.0, 0.0)

    def test_translation_only(self):
        pose = Pose(
            id="moved",
            bones={"root": PoseBoneTransform(translation=(1.0, 2.0, 3.0))},
        )
        assert pose.bones["root"].translation == (1.0, 2.0, 3.0)
        assert pose.bones["root"].rotation is None

    def test_empty_bones(self):
        pose = Pose(id="empty", bones={})
        assert pose.bones == {}

    def test_unknown_field_rejected(self):
        with pytest.raises(ValidationError, match="extra"):
            PoseBoneTransform(rotation=(1, 0, 0, 0), scale=(1, 1, 1))


class TestResolveSolver:
    def _spec(self, solver=None):
        return RigySpec(version="0.5", skinning_solver=solver)

    def _binding(self, solver=None):
        return Binding(
            mesh_id="m", armature_id="a",
            weights=[PrimitiveWeights(primitive_id="p", bones=[BoneWeight(bone_id="b", weight=1.0)])],
            skinning_solver=solver,
        )

    def test_default_lbs(self):
        assert resolve_solver(self._spec(), self._binding()) == "lbs"

    def test_toplevel_dqs(self):
        assert resolve_solver(self._spec("dqs"), self._binding()) == "dqs"

    def test_binding_override(self):
        assert resolve_solver(self._spec("dqs"), self._binding("lbs")) == "lbs"

    def test_binding_dqs_over_toplevel_lbs(self):
        assert resolve_solver(self._spec("lbs"), self._binding("dqs")) == "dqs"


class TestUvRoleEntry:
    def test_valid(self):
        entry = UvRoleEntry(set="uv0")
        assert entry.set == "uv0"

    def test_unknown_field_rejected(self):
        with pytest.raises(ValidationError, match="extra"):
            UvRoleEntry(set="uv0", channel=1)


class TestMeshUvRoles:
    def test_default_none(self):
        m = Mesh(
            id="m",
            primitives=[Primitive(type="box", id="p", dimensions={"x": 1, "y": 1, "z": 1})],
        )
        assert m.uv_roles is None

    def test_with_uv_roles(self):
        m = Mesh(
            id="m",
            primitives=[Primitive(type="box", id="p", dimensions={"x": 1, "y": 1, "z": 1})],
            uv_roles={"albedo": UvRoleEntry(set="uv0")},
        )
        assert m.uv_roles["albedo"].set == "uv0"


class TestMaterialUsesUvRoles:
    def test_default_none(self):
        mat = Material(base_color=[1.0, 0.0, 0.0, 1.0])
        assert mat.uses_uv_roles is None

    def test_with_uses_uv_roles(self):
        mat = Material(base_color=[1.0, 0.0, 0.0, 1.0], uses_uv_roles=["albedo", "detail"])
        assert mat.uses_uv_roles == ["albedo", "detail"]


class TestUvRoleVocabulary:
    def test_vocabulary_contents(self):
        assert "albedo" in UV_ROLE_VOCABULARY
        assert "detail" in UV_ROLE_VOCABULARY
        assert "directional" in UV_ROLE_VOCABULARY
        assert "radial" in UV_ROLE_VOCABULARY
        assert "decal" in UV_ROLE_VOCABULARY
        assert "lightmap" in UV_ROLE_VOCABULARY
        assert len(UV_ROLE_VOCABULARY) == 6
