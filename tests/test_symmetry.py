"""Tests for symmetry expansion."""

import yaml

from rigy.models import RigySpec
from rigy.symmetry import expand_symmetry
from rigy.validation import validate


class TestSymmetryExpansion:
    def test_no_symmetry_unchanged(self, minimal_mesh_yaml):
        spec = RigySpec(**yaml.safe_load(minimal_mesh_yaml))
        result = expand_symmetry(spec)
        assert len(result.meshes) == len(spec.meshes)
        assert len(result.meshes[0].primitives) == 1

    def test_empty_symmetry_unchanged(self, minimal_mesh_yaml):
        data = yaml.safe_load(minimal_mesh_yaml)
        data["symmetry"] = {}
        spec = RigySpec(**data)
        result = expand_symmetry(spec)
        assert len(result.meshes[0].primitives) == 1

    def test_mirror_duplicates_primitives(self, full_humanoid_yaml):
        spec = RigySpec(**yaml.safe_load(full_humanoid_yaml))
        result = expand_symmetry(spec)
        # Original has 4 primitives (torso, head, legL_upper, legL_lower)
        # Mirror adds 2 more (legR_upper, legR_lower)
        assert len(result.meshes[0].primitives) == 6

    def test_mirror_duplicates_bones(self, full_humanoid_yaml):
        spec = RigySpec(**yaml.safe_load(full_humanoid_yaml))
        result = expand_symmetry(spec)
        # Original has 5 bones, mirror adds 2 (legR_upper, legR_lower)
        assert len(result.armatures[0].bones) == 7

    def test_mirror_duplicates_weights(self, full_humanoid_yaml):
        spec = RigySpec(**yaml.safe_load(full_humanoid_yaml))
        result = expand_symmetry(spec)
        # Original has 4 weight entries, mirror adds 2
        assert len(result.bindings[0].weights) == 6

    def test_originals_preserved(self, full_humanoid_yaml):
        spec = RigySpec(**yaml.safe_load(full_humanoid_yaml))
        result = expand_symmetry(spec)
        prim_ids = [p.id for p in result.meshes[0].primitives]
        assert "legL_upper" in prim_ids
        assert "legL_lower" in prim_ids

    def test_mirrored_ids_correct(self, full_humanoid_yaml):
        spec = RigySpec(**yaml.safe_load(full_humanoid_yaml))
        result = expand_symmetry(spec)
        prim_ids = [p.id for p in result.meshes[0].primitives]
        assert "legR_upper" in prim_ids
        assert "legR_lower" in prim_ids

    def test_mirrored_x_negated(self, full_humanoid_yaml):
        spec = RigySpec(**yaml.safe_load(full_humanoid_yaml))
        result = expand_symmetry(spec)
        prims = {p.id: p for p in result.meshes[0].primitives}
        left = prims["legL_upper"]
        right = prims["legR_upper"]
        assert left.transform.translation[0] == -right.transform.translation[0]
        assert left.transform.translation[1] == right.transform.translation[1]
        assert left.transform.translation[2] == right.transform.translation[2]

    def test_expanded_spec_passes_validation(self, full_humanoid_yaml):
        spec = RigySpec(**yaml.safe_load(full_humanoid_yaml))
        result = expand_symmetry(spec)
        validate(result)  # should not raise

    def test_symmetry_cleared_after_expansion(self, full_humanoid_yaml):
        spec = RigySpec(**yaml.safe_load(full_humanoid_yaml))
        result = expand_symmetry(spec)
        assert result.symmetry is None

    def test_deterministic(self, full_humanoid_yaml):
        spec = RigySpec(**yaml.safe_load(full_humanoid_yaml))
        result1 = expand_symmetry(spec)
        result2 = expand_symmetry(spec)
        ids1 = [p.id for p in result1.meshes[0].primitives]
        ids2 = [p.id for p in result2.meshes[0].primitives]
        assert ids1 == ids2


class TestAnchorSymmetry:
    def test_anchors_mirrored(self):
        from rigy.models import Anchor, MirrorX, Symmetry

        spec = RigySpec(
            version="0.2",
            anchors=[
                Anchor(id="legL_mount", translation=(0.5, 1.0, 0.0)),
            ],
            symmetry=Symmetry(mirror_x=MirrorX(prefix_from="legL_", prefix_to="legR_")),
        )
        result = expand_symmetry(spec)
        anchor_ids = {a.id for a in result.anchors}
        assert "legL_mount" in anchor_ids
        assert "legR_mount" in anchor_ids

    def test_anchor_x_negated(self):
        from rigy.models import Anchor, MirrorX, Symmetry

        spec = RigySpec(
            version="0.2",
            anchors=[
                Anchor(id="legL_mount", translation=(0.5, 1.0, 0.2)),
            ],
            symmetry=Symmetry(mirror_x=MirrorX(prefix_from="legL_", prefix_to="legR_")),
        )
        result = expand_symmetry(spec)
        anchors = {a.id: a for a in result.anchors}
        left = anchors["legL_mount"]
        right = anchors["legR_mount"]
        assert left.translation[0] == -right.translation[0]
        assert left.translation[1] == right.translation[1]
        assert left.translation[2] == right.translation[2]

    def test_no_matching_anchors_unchanged(self):
        from rigy.models import Anchor, MirrorX, Symmetry

        spec = RigySpec(
            version="0.2",
            anchors=[Anchor(id="center", translation=(0, 0, 0))],
            symmetry=Symmetry(mirror_x=MirrorX(prefix_from="legL_", prefix_to="legR_")),
        )
        result = expand_symmetry(spec)
        assert len(result.anchors) == 1


class TestInstanceSymmetry:
    def test_instances_mirrored(self):
        from rigy.models import Anchor, Attach3, ImportDef, Instance, MirrorX, Symmetry

        spec = RigySpec(
            version="0.2",
            anchors=[
                Anchor(id="legL_a", translation=(0.5, 0, 0)),
                Anchor(id="legL_b", translation=(1.5, 0, 0)),
                Anchor(id="legL_c", translation=(0.5, 0, 1)),
            ],
            imports={"part": ImportDef(source="part.rigy.yaml")},
            instances=[
                Instance(
                    id="legL_inst",
                    import_="part",
                    attach3=Attach3(
                        from_=["part.a", "part.b", "part.c"],
                        to=["legL_a", "legL_b", "legL_c"],
                        mode="rigid",
                    ),
                ),
            ],
            symmetry=Symmetry(mirror_x=MirrorX(prefix_from="legL_", prefix_to="legR_")),
        )
        result = expand_symmetry(spec)
        inst_ids = {i.id for i in result.instances}
        assert "legL_inst" in inst_ids
        assert "legR_inst" in inst_ids

    def test_instance_from_unchanged_to_renamed(self):
        from rigy.models import Anchor, Attach3, ImportDef, Instance, MirrorX, Symmetry

        spec = RigySpec(
            version="0.2",
            anchors=[
                Anchor(id="legL_a", translation=(0.5, 0, 0)),
                Anchor(id="legL_b", translation=(1.5, 0, 0)),
                Anchor(id="legL_c", translation=(0.5, 0, 1)),
            ],
            imports={"part": ImportDef(source="part.rigy.yaml")},
            instances=[
                Instance(
                    id="legL_inst",
                    import_="part",
                    attach3=Attach3(
                        from_=["part.a", "part.b", "part.c"],
                        to=["legL_a", "legL_b", "legL_c"],
                        mode="rigid",
                    ),
                ),
            ],
            symmetry=Symmetry(mirror_x=MirrorX(prefix_from="legL_", prefix_to="legR_")),
        )
        result = expand_symmetry(spec)
        mirrored = next(i for i in result.instances if i.id == "legR_inst")

        # from anchors are unchanged (imported asset space)
        assert mirrored.attach3.from_ == ["part.a", "part.b", "part.c"]
        # to anchors are renamed
        assert mirrored.attach3.to == ["legR_a", "legR_b", "legR_c"]
        # Same import ref
        assert mirrored.import_ == "part"
