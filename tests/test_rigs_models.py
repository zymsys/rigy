"""Tests for Rigs Pydantic models."""

import pytest
from pydantic import ValidationError as PydanticValidationError

from rigy.rigs_models import (
    MountRef,
    Nudge,
    Placement,
    RigsSpec,
    Scene,
    SceneChild,
    SlotRef,
)


class TestSlotRef:
    def test_name_only(self):
        ref = SlotRef(name="floor_center")
        assert ref.name == "floor_center"
        assert ref.anchors is None

    def test_anchors_only(self):
        ref = SlotRef(anchors=["a", "b", "c"])
        assert ref.name is None
        assert ref.anchors == ["a", "b", "c"]

    def test_neither_raises(self):
        with pytest.raises(PydanticValidationError, match="exactly one"):
            SlotRef()

    def test_both_raises(self):
        with pytest.raises(PydanticValidationError, match="exactly one"):
            SlotRef(name="x", anchors=["a", "b", "c"])

    def test_wrong_anchor_count(self):
        with pytest.raises(PydanticValidationError, match="exactly 3"):
            SlotRef(anchors=["a", "b"])

    def test_duplicate_anchors(self):
        with pytest.raises(PydanticValidationError, match="distinct"):
            SlotRef(anchors=["a", "a", "b"])

    def test_extra_field_rejected(self):
        with pytest.raises(PydanticValidationError):
            SlotRef(name="x", bogus="y")


class TestMountRef:
    def test_name_only(self):
        ref = MountRef(name="base_mount")
        assert ref.name == "base_mount"

    def test_anchors_only(self):
        ref = MountRef(anchors=["x", "y", "z"])
        assert ref.anchors == ["x", "y", "z"]

    def test_neither_raises(self):
        with pytest.raises(PydanticValidationError, match="exactly one"):
            MountRef()

    def test_duplicate_anchors(self):
        with pytest.raises(PydanticValidationError, match="distinct"):
            MountRef(anchors=["a", "b", "a"])


class TestPlacement:
    def test_defaults(self):
        p = Placement(
            slot=SlotRef(anchors=["a", "b", "c"]),
            mount=MountRef(anchors=["x", "y", "z"]),
        )
        assert p.rotate == "0deg"
        assert p.nudge is None

    def test_with_nudge(self):
        p = Placement(
            slot=SlotRef(name="s"),
            mount=MountRef(name="m"),
            rotate="90deg",
            nudge=Nudge(north="10cm", east="5cm", up="0"),
        )
        assert p.nudge.north == "10cm"


class TestSceneChild:
    def test_recursive_children(self):
        inner = SceneChild(
            id="inner",
            base="b",
            place=Placement(
                slot=SlotRef(anchors=["a", "b", "c"]),
                mount=MountRef(anchors=["x", "y", "z"]),
            ),
        )
        outer = SceneChild(
            id="outer",
            base="a",
            place=Placement(
                slot=SlotRef(anchors=["a", "b", "c"]),
                mount=MountRef(anchors=["x", "y", "z"]),
            ),
            children=[inner],
        )
        assert len(outer.children) == 1
        assert outer.children[0].id == "inner"

    def test_extra_field_rejected(self):
        with pytest.raises(PydanticValidationError):
            SceneChild(
                id="x",
                base="b",
                place=Placement(
                    slot=SlotRef(anchors=["a", "b", "c"]),
                    mount=MountRef(anchors=["x", "y", "z"]),
                ),
                unknown_field="bad",
            )


class TestRigsSpec:
    def test_minimal(self):
        spec = RigsSpec(
            rigs_version="0.1",
            imports={"room": "parts/room.rigy.yaml"},
            scene=Scene(base="room"),
        )
        assert spec.rigs_version == "0.1"
        assert spec.scene.base == "room"

    def test_extra_field_rejected(self):
        with pytest.raises(PydanticValidationError):
            RigsSpec(
                rigs_version="0.1",
                imports={},
                scene=Scene(base="x"),
                bogus="y",
            )
