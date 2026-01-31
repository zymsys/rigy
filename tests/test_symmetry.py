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
