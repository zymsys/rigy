"""Pydantic v2 schema models for Rigy v0.1/v0.2 specs."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


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


# --- v0.2 models ---


class Anchor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    translation: tuple[float, float, float]
    scope: str | None = None


class ImportDef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str
    contract: str | None = None


class Attach3(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    from_: list[str] = Field(alias="from")
    to: list[str]
    mode: Literal["rigid", "uniform", "affine"]

    @field_validator("from_")
    @classmethod
    def from_must_have_3(cls, v: list[str]) -> list[str]:
        if len(v) != 3:
            raise ValueError("'from' must have exactly 3 entries")
        return v

    @field_validator("to")
    @classmethod
    def to_must_have_3(cls, v: list[str]) -> list[str]:
        if len(v) != 3:
            raise ValueError("'to' must have exactly 3 entries")
        return v


class Instance(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: str
    import_: str = Field(alias="import")
    attach3: Attach3


class RicyContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_version: str
    required_anchors: list[str] = []
    required_frame3_sets: list[str] = []
    frame3_sets: dict[str, list[str]] = {}


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
    # v0.2 fields
    anchors: list[Anchor] = []
    imports: dict[str, ImportDef] = {}
    instances: list[Instance] = []


# --- Resolved asset dataclass (used by import resolution) ---


@dataclass
class ResolvedAsset:
    spec: RigySpec
    path: Path
    contract: RicyContract | None = None
    imported_assets: dict[str, ResolvedAsset] = field(default_factory=dict)
