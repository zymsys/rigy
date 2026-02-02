"""Tests for Rigs composition (tree walk + world transforms)."""

from pathlib import Path

import numpy as np
from numpy.testing import assert_allclose

from rigy.rigs_composition import compose_rigs
from rigy.rigs_parser import parse_rigs
from rigy.rigs_validation import validate_rigs

FIXTURES = Path(__file__).parent / "rigs_fixtures"


class TestComposeSimple:
    def test_single_child(self):
        asset = parse_rigs(FIXTURES / "simple_scene.rigs.yaml")
        validate_rigs(asset)
        composed = compose_rigs(asset)

        assert composed.root_alias == "plate"
        assert len(composed.instances) == 1

        inst = composed.instances[0]
        assert inst.id == "cube1"
        assert inst.asset_alias == "cube"
        # Slot frame origin: [0.0, 0.1, 0.0] (plate top_a)
        # Mount frame origin: [0.0, 0.0, 0.0] (cube bottom_a)
        # Both frames have the same rotation (identity axes)
        # So R=I, T = Os - Om = [0, 0.1, 0]
        assert_allclose(inst.local_transform[:3, :3], np.eye(3), atol=1e-10)
        assert_allclose(inst.local_transform[:3, 3], [0.0, 0.1, 0.0], atol=1e-10)


class TestComposeNested:
    def test_nested_children(self):
        asset = parse_rigs(FIXTURES / "nested_scene.rigs.yaml")
        validate_rigs(asset)
        composed = compose_rigs(asset)

        assert len(composed.instances) == 1
        cube1 = composed.instances[0]
        assert cube1.id == "cube1"
        assert len(cube1.children) == 1

        cube2 = cube1.children[0]
        assert cube2.id == "cube2"
        # cube2's slot is on cube (top_a/b/c at y=0.3)
        # cube2's mount is on cube (bottom_a/b/c at y=0)
        # So cube2 should be offset by Y=0.3 relative to cube1
        assert_allclose(cube2.local_transform[:3, 3], [0.0, 0.3, 0.0], atol=1e-10)

    def test_world_transform_accumulation(self):
        asset = parse_rigs(FIXTURES / "nested_scene.rigs.yaml")
        validate_rigs(asset)
        composed = compose_rigs(asset)

        cube1 = composed.instances[0]
        cube2 = cube1.children[0]

        # cube1 world = parent_world (identity) @ local
        # cube2 world = cube1_world @ cube2_local
        expected_world = cube1.world_transform @ cube2.local_transform
        assert_allclose(cube2.world_transform, expected_world, atol=1e-10)


class TestComposeRotatedNudge:
    def test_rotated_with_nudge(self):
        asset = parse_rigs(FIXTURES / "rotated_scene.rigs.yaml")
        validate_rigs(asset)
        composed = compose_rigs(asset)

        inst = composed.instances[0]
        assert inst.id == "cube1"

        T = inst.local_transform
        # Rotation part should be 90deg Y rotation
        expected_R = np.array(
            [
                [0.0, 0.0, 1.0],
                [0.0, 1.0, 0.0],
                [-1.0, 0.0, 0.0],
            ]
        )
        assert_allclose(T[:3, :3], expected_R, atol=1e-10)

        # Slot frame at top_a=[0,0.1,0] with axes X=[1,0,0], Y=[0,1,0], Z=[0,0,1]
        # Nudge: east=0.1m, up=0, north=0.2m
        # Tnudge = 0.1*[1,0,0] + 0*[0,1,0] + 0.2*[0,0,1] = [0.1, 0, 0.2]
        # T = (Os + Tnudge) - R @ Om
        # Os = [0, 0.1, 0], Om = [0, 0, 0]
        # T = [0.1, 0.1, 0.2] - R @ [0,0,0] = [0.1, 0.1, 0.2]
        assert_allclose(T[:3, 3], [0.1, 0.1, 0.2], atol=1e-10)
