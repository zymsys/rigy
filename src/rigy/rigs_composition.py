"""Composition: tree walk and world transform accumulation for Rigs scenes."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from rigy.models import ResolvedAsset
from rigy.rigs_models import ResolvedRigsAsset, SceneChild
from rigy.rigs_placement import compute_placement_transform, parse_distance
from rigy.rigs_validation import _resolve_ref_anchors


@dataclass
class RigsInstance:
    """A resolved instance in the composed scene."""

    id: str
    asset_alias: str
    resolved_asset: ResolvedAsset
    local_transform: np.ndarray  # 4x4
    world_transform: np.ndarray  # 4x4
    children: list[RigsInstance] = field(default_factory=list)


@dataclass
class ComposedRigsScene:
    """The fully composed Rigs scene."""

    root_alias: str
    root_asset: ResolvedAsset
    instances: list[RigsInstance] = field(default_factory=list)


def compose_rigs(asset: ResolvedRigsAsset) -> ComposedRigsScene:
    """Compose a Rigs scene by resolving all placements.

    Args:
        asset: Validated ResolvedRigsAsset.

    Returns:
        ComposedRigsScene with world transforms for all instances.
    """
    root_alias = asset.spec.scene.base
    root_asset = asset.resolved_imports[root_alias]

    instances: list[RigsInstance] = []
    if asset.spec.scene.children:
        parent_world = np.eye(4, dtype=np.float64)
        for child in asset.spec.scene.children:
            inst = _resolve_child(child, root_alias, parent_world, asset)
            instances.append(inst)

    return ComposedRigsScene(
        root_alias=root_alias,
        root_asset=root_asset,
        instances=instances,
    )


def _resolve_child(
    child: SceneChild,
    parent_alias: str,
    parent_world: np.ndarray,
    asset: ResolvedRigsAsset,
) -> RigsInstance:
    """Resolve a single child instance and its descendants."""
    parent_asset = asset.resolved_imports[parent_alias]
    child_asset = asset.resolved_imports[child.base]

    # Resolve anchor IDs
    slot_ids = _resolve_ref_anchors(
        child.place.slot.name,
        child.place.slot.anchors,
        parent_asset,
        "slot",
        child.id,
    )
    mount_ids = _resolve_ref_anchors(
        child.place.mount.name,
        child.place.mount.anchors,
        child_asset,
        "mount",
        child.id,
    )

    # Get anchor positions
    parent_anchors = {
        a.id: np.array(a.translation, dtype=np.float64) for a in parent_asset.spec.anchors
    }
    child_anchors = {
        a.id: np.array(a.translation, dtype=np.float64) for a in child_asset.spec.anchors
    }

    slot_points = tuple(parent_anchors[aid] for aid in slot_ids)
    mount_points = tuple(child_anchors[aid] for aid in mount_ids)

    # Parse rotate
    rotate_str = child.place.rotate
    rotate_deg = int(rotate_str.replace("deg", ""))

    # Parse nudge
    if child.place.nudge is not None:
        east = parse_distance(child.place.nudge.east)
        up = parse_distance(child.place.nudge.up)
        north = parse_distance(child.place.nudge.north)
    else:
        east = up = north = 0.0

    # Compute local transform
    local_transform = compute_placement_transform(
        slot_points, mount_points, rotate_deg, (east, up, north)
    )

    # Accumulate world transform
    world_transform = parent_world @ local_transform

    # Recurse into children
    child_instances: list[RigsInstance] = []
    if child.children:
        for grandchild in child.children:
            inst = _resolve_child(grandchild, child.base, world_transform, asset)
            child_instances.append(inst)

    return RigsInstance(
        id=child.id,
        asset_alias=child.base,
        resolved_asset=child_asset,
        local_transform=local_transform,
        world_transform=world_transform,
        children=child_instances,
    )
