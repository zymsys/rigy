"""Pydantic v2 schema models for Rigy v0.1 specs."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator


class CoordinateSystem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    up: Literal["Y"]
    forward: Literal["-Z"]
    handedness: Literal["right"]


class Transform(BaseModel):
    model_config = ConfigDict(extra="forbid")

    translation: tuple[float, float, float] | None = None
    rotation_euler: tuple[float, float, float] | None = None


class Primitive(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["box", "sphere", "cylinder", "capsule"]
    id: str
    name: str | None = None
    dimensions: dict[str, float]
    transform: Transform | None = None
    material: str | None = None

    @field_validator("dimensions")
    @classmethod
    def dimensions_not_empty(cls, v: dict[str, float]) -> dict[str, float]:
        if not v:
            raise ValueError("dimensions must not be empty")
        return v


class Mesh(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str | None = None
    primitives: list[Primitive]


class Bone(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    parent: str
    head: tuple[float, float, float]
    tail: tuple[float, float, float]
    roll: float = 0.0


class Armature(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str | None = None
    bones: list[Bone]


class BoneWeight(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bone_id: str
    weight: float


class PrimitiveWeights(BaseModel):
    model_config = ConfigDict(extra="forbid")

    primitive_id: str
    bones: list[BoneWeight]


class Binding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mesh_id: str
    armature_id: str
    weights: list[PrimitiveWeights]


class MirrorX(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prefix_from: str
    prefix_to: str


class Symmetry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mirror_x: MirrorX | None = None


class RigySpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str
    units: Literal["meters"] = "meters"
    coordinate_system: CoordinateSystem = CoordinateSystem(up="Y", forward="-Z", handedness="right")
    tessellation_profile: str = "v0_1_default"
    meshes: list[Mesh] = []
    armatures: list[Armature] = []
    bindings: list[Binding] = []
    symmetry: Symmetry | None = None
