"""Pydantic v2 schema models for Rigy v0.1–v0.13 specs."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

UV_ROLE_VOCABULARY: frozenset[str] = frozenset(
    {
        "albedo",
        "detail",
        "directional",
        "radial",
        "decal",
        "lightmap",
    }
)

UV_GENERATOR_VOCABULARY: frozenset[str] = frozenset(
    {
        "planar_xy@1",
        "box_project@1",
        "sphere_latlong@1",
        "cylindrical@1",
        "capsule_cyl_latlong@1",
    }
)

UV_GENERATOR_APPLICABILITY: dict[str, frozenset[str]] = {
    "planar_xy@1": frozenset({"box", "sphere", "cylinder", "capsule", "wedge"}),
    "box_project@1": frozenset({"box"}),
    "sphere_latlong@1": frozenset({"sphere"}),
    "cylindrical@1": frozenset({"cylinder"}),
    "capsule_cyl_latlong@1": frozenset({"capsule"}),
}

IMPLICIT_FIELD_VOCABULARY: frozenset[str] = frozenset(
    {
        "metaball_sphere@1",
        "metaball_capsule@1",
        "sdf_sphere@1",
        "sdf_capsule@1",
    }
)


class UvRoleEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    set: str


class UvSetEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    generator: str


class CoordinateSystem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    up: Literal["Y"]
    forward: Literal["-Z"]
    handedness: Literal["right"]


class RotationAxisAngle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    axis: tuple[float, float, float]
    degrees: float


class Transform(BaseModel):
    model_config = ConfigDict(extra="forbid")

    translation: tuple[float, float, float] | None = None
    rotation_euler: tuple[float, float, float] | None = None
    rotation_degrees: tuple[float, float, float] | None = None
    rotation_axis_angle: RotationAxisAngle | None = None
    rotation_quat: tuple[float, float, float, float] | None = None  # (x, y, z, w)

    @model_validator(mode="after")
    def _normalize_rotation_fields(self) -> Transform:
        # Count how many rotation forms are set
        forms = [
            self.rotation_euler is not None,
            self.rotation_degrees is not None,
            self.rotation_axis_angle is not None,
            self.rotation_quat is not None,
        ]
        if sum(forms) > 1:
            raise ValueError(
                "V72: Transform must set at most one rotation form "
                "(rotation_euler, rotation_degrees, rotation_axis_angle, rotation_quat)"
            )

        if self.rotation_degrees is not None and self.rotation_euler is None:
            self.rotation_euler = tuple(math.radians(v) for v in self.rotation_degrees)

        return self


class ImplicitAABB(BaseModel):
    model_config = ConfigDict(extra="forbid")

    min: tuple[float, float, float]
    max: tuple[float, float, float]


class ImplicitGrid(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nx: int
    ny: int
    nz: int


class ImplicitDomain(BaseModel):
    model_config = ConfigDict(extra="forbid")

    aabb: ImplicitAABB
    grid: ImplicitGrid


class ImplicitExtraction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    algorithm: str = "marching_cubes@1"


class FieldOperator(BaseModel):
    model_config = ConfigDict(extra="forbid")

    op: Literal["add", "subtract"]
    field: str
    strength: float
    radius: float
    height: float | None = None
    transform: Transform | None = None


class Primitive(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["box", "sphere", "cylinder", "capsule", "wedge", "implicit_surface"]
    id: str
    name: str | None = None
    dimensions: dict[str, float] | None = None
    transform: Transform | None = None
    material: str | None = None
    surface: str | None = None
    tags: list[str] | None = None
    # implicit_surface fields (v0.13+)
    domain: ImplicitDomain | None = None
    iso: float | None = None
    ops: list[FieldOperator] | None = None
    extraction: ImplicitExtraction | None = None

    @model_validator(mode="after")
    def _validate_by_type(self) -> Primitive:
        if self.type == "implicit_surface":
            if self.dimensions is not None:
                raise ValueError("implicit_surface must not have 'dimensions'")
            if self.domain is None:
                raise ValueError("implicit_surface requires 'domain'")
            if self.iso is None:
                raise ValueError("implicit_surface requires 'iso'")
            if self.ops is None or len(self.ops) == 0:
                raise ValueError("implicit_surface requires non-empty 'ops'")
        else:
            if self.dimensions is None or len(self.dimensions) == 0:
                raise ValueError("dimensions must not be empty")
            if self.domain is not None:
                raise ValueError(f"'{self.type}' must not have 'domain'")
            if self.iso is not None:
                raise ValueError(f"'{self.type}' must not have 'iso'")
            if self.ops is not None:
                raise ValueError(f"'{self.type}' must not have 'ops'")
            if self.extraction is not None:
                raise ValueError(f"'{self.type}' must not have 'extraction'")
        return self


class Material(BaseModel):
    model_config = ConfigDict(extra="forbid")

    base_color: list[float]
    uses_uv_roles: list[str] | None = None


class Mesh(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str | None = None
    primitives: list[Primitive]
    material: str | None = None  # v0.12+: default material for primitives
    uv_sets: dict[str, UvSetEntry] | None = None
    uv_roles: dict[str, UvRoleEntry] | None = None


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


class Gradient(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    axis: Literal["x", "y", "z"]
    range: tuple[float, float]
    from_: list[BoneWeight] = Field(alias="from")
    to: list[BoneWeight]

    @field_validator("range")
    @classmethod
    def range_ascending(cls, v: tuple[float, float]) -> tuple[float, float]:
        if v[0] >= v[1]:
            raise ValueError(f"Gradient range[0] must be < range[1], got {v}")
        return v

    @field_validator("from_", mode="before")
    @classmethod
    def normalize_from(cls, v: object) -> list[object]:
        if isinstance(v, dict):
            return [v]
        if isinstance(v, BoneWeight):
            return [v]
        return v

    @field_validator("to", mode="before")
    @classmethod
    def normalize_to(cls, v: object) -> list[object]:
        if isinstance(v, dict):
            return [v]
        if isinstance(v, BoneWeight):
            return [v]
        return v


class VertexOverride(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vertices: list[int]
    bones: list[BoneWeight]

    @field_validator("vertices")
    @classmethod
    def vertices_non_negative(cls, v: list[int]) -> list[int]:
        for idx in v:
            if idx < 0:
                raise ValueError(f"Vertex index must be >= 0, got {idx}")
        return v


class WeightMap(BaseModel):
    model_config = ConfigDict(extra="forbid")

    primitive_id: str
    gradients: list[Gradient] | None = None
    overrides: list[VertexOverride] | None = None
    source: str | None = None

    @model_validator(mode="after")
    def at_least_one_strategy(self) -> WeightMap:
        if not self.gradients and not self.overrides and not self.source:
            raise ValueError("WeightMap must have at least one of: gradients, overrides, source")
        return self


class Binding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mesh_id: str
    armature_id: str
    weights: list[PrimitiveWeights]
    weight_maps: list[WeightMap] | None = None
    skinning_solver: Literal["lbs", "dqs"] | None = None


class PoseBoneTransform(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rotation: tuple[float, float, float, float] | None = None  # [w, x, y, z]
    translation: tuple[float, float, float] | None = None


class Pose(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    bones: dict[str, PoseBoneTransform]


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
    import_: str | None = Field(default=None, alias="import")
    mesh_id: str | None = None
    attach3: Attach3 | None = None

    @model_validator(mode="after")
    def _check_import_or_mesh(self) -> Instance:
        has_import = self.import_ is not None
        has_mesh = self.mesh_id is not None
        if has_import and has_mesh:
            raise ValueError("Instance must set either 'import' or 'mesh_id', not both")
        if not has_import and not has_mesh:
            raise ValueError("Instance must set either 'import' or 'mesh_id'")
        if has_import and self.attach3 is None:
            raise ValueError("Instance with 'import' requires 'attach3'")
        return self


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
    materials: dict[str, Material] = {}
    meshes: list[Mesh] = []
    armatures: list[Armature] = []
    bindings: list[Binding] = []
    symmetry: Symmetry | None = None
    skinning_solver: Literal["lbs", "dqs"] | None = None
    poses: list[Pose] = []
    # v0.2 fields
    anchors: list[Anchor] = []
    imports: dict[str, ImportDef] = {}
    instances: list[Instance] = []
    # Tooling-only block: accepted but semantically ignored by compile/export.
    geometry_checks: Any | None = None


# --- Resolved asset dataclass (used by import resolution) ---


def resolve_solver(spec: RigySpec, binding: Binding) -> str:
    """Return the effective skinning solver for a binding.

    Priority: per-binding override > top-level spec > default ("lbs").
    """
    if binding.skinning_solver is not None:
        return binding.skinning_solver
    if spec.skinning_solver is not None:
        return spec.skinning_solver
    return "lbs"


@dataclass
class ResolvedAsset:
    spec: RigySpec
    path: Path
    contract: RicyContract | None = None
    imported_assets: dict[str, ResolvedAsset] = field(default_factory=dict)
