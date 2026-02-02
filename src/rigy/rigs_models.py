"""Pydantic v2 schema models for Rigs v0.1 scene composition specs."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from pydantic import BaseModel, ConfigDict, model_validator

from rigy.models import ResolvedAsset


class SlotRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    anchors: list[str] | None = None

    @model_validator(mode="after")
    def _exactly_one(self) -> SlotRef:
        has_name = self.name is not None
        has_anchors = self.anchors is not None
        if has_name == has_anchors:
            raise ValueError("SlotRef must have exactly one of 'name' or 'anchors'")
        if has_anchors and len(self.anchors) != 3:
            raise ValueError("SlotRef 'anchors' must have exactly 3 entries")
        if has_anchors and len(set(self.anchors)) != 3:
            raise ValueError("SlotRef 'anchors' must be 3 distinct IDs")
        return self


class MountRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    anchors: list[str] | None = None

    @model_validator(mode="after")
    def _exactly_one(self) -> MountRef:
        has_name = self.name is not None
        has_anchors = self.anchors is not None
        if has_name == has_anchors:
            raise ValueError("MountRef must have exactly one of 'name' or 'anchors'")
        if has_anchors and len(self.anchors) != 3:
            raise ValueError("MountRef 'anchors' must have exactly 3 entries")
        if has_anchors and len(set(self.anchors)) != 3:
            raise ValueError("MountRef 'anchors' must be 3 distinct IDs")
        return self


class Nudge(BaseModel):
    model_config = ConfigDict(extra="forbid", coerce_numbers_to_str=True)

    north: str = "0"
    east: str = "0"
    up: str = "0"


class Placement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slot: SlotRef
    mount: MountRef
    rotate: str = "0deg"
    nudge: Nudge | None = None


class SceneChild(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    base: str
    place: Placement
    children: list[SceneChild] | None = None


class Scene(BaseModel):
    model_config = ConfigDict(extra="forbid")

    base: str
    children: list[SceneChild] | None = None


class RigsSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rigs_version: str
    imports: dict[str, str]
    scene: Scene


# --- Resolved types ---


@dataclass
class ResolvedRigsAsset:
    """A parsed Rigs spec with all Rigy imports resolved."""

    spec: RigsSpec
    path: Path
    resolved_imports: dict[str, ResolvedAsset] = field(default_factory=dict)
