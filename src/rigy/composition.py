"""Composition: resolve instances and compute attach3 transforms."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from rigy.attach3 import compute_attach3_transform
from rigy.contracts import validate_contract
from rigy.errors import CompositionError
from rigy.models import ResolvedAsset, RigySpec


@dataclass
class ResolvedInstance:
    id: str
    source_spec: RigySpec
    transform: np.ndarray  # 4x4
    namespace: str


@dataclass
class ComposedAsset:
    root_spec: RigySpec
    instances: list[ResolvedInstance] = field(default_factory=list)


def resolve_composition(asset: ResolvedAsset) -> ComposedAsset:
    """Resolve all instances in the asset, computing attach3 transforms.

    For v0.1 specs (no instances), returns a ComposedAsset with empty instances.

    Args:
        asset: Fully resolved asset tree (from parse_with_imports).

    Returns:
        ComposedAsset with computed transforms for each instance.

    Raises:
        CompositionError: On anchor resolution failures, frame3 constraint
            violations, or contract violations.
    """
    # Validate contracts for all imports
    for namespace, imported in asset.imported_assets.items():
        if imported.contract is not None:
            validate_contract(imported.spec, imported.contract)

    if not asset.spec.instances:
        return ComposedAsset(root_spec=asset.spec)

    # Build local anchor lookup
    local_anchors = {a.id: np.array(a.translation, dtype=np.float64) for a in asset.spec.anchors}

    resolved_instances: list[ResolvedInstance] = []

    for inst in asset.spec.instances:
        imported_asset = asset.imported_assets.get(inst.import_)
        if imported_asset is None:
            raise CompositionError(
                f"Instance {inst.id!r}: import {inst.import_!r} not found in resolved assets"
            )

        imported_spec = imported_asset.spec
        imported_anchors = {
            a.id: np.array(a.translation, dtype=np.float64) for a in imported_spec.anchors
        }

        # Resolve "from" anchors (namespace.anchor_id format)
        from_points = _resolve_anchor_refs(
            inst.attach3.from_, inst.import_, imported_anchors, "from", inst.id
        )

        # Resolve "to" anchors (local)
        to_points = _resolve_local_anchors(inst.attach3.to, local_anchors, inst.id)

        # Compute transform from anchor point triplets
        transform = compute_attach3_transform(
            (from_points[0], from_points[1], from_points[2]),
            (to_points[0], to_points[1], to_points[2]),
            inst.attach3.mode,
        )

        resolved_instances.append(
            ResolvedInstance(
                id=inst.id,
                source_spec=imported_spec,
                transform=transform,
                namespace=inst.import_,
            )
        )

    return ComposedAsset(root_spec=asset.spec, instances=resolved_instances)


def _resolve_anchor_refs(
    refs: list[str],
    default_namespace: str,
    anchor_map: dict[str, np.ndarray],
    label: str,
    instance_id: str,
) -> list[np.ndarray]:
    """Resolve anchor references like 'namespace.anchor_id' or 'anchor_id'.

    If the reference contains a dot, the part before the dot is the namespace
    and must match the expected namespace. The part after is the anchor ID.
    If no dot, the entire string is the anchor ID in the default namespace.
    """
    points = []
    for ref in refs:
        if "." in ref:
            ns, anchor_id = ref.split(".", 1)
            if ns != default_namespace:
                raise CompositionError(
                    f"Instance {instance_id!r} {label}: anchor ref {ref!r} has namespace "
                    f"{ns!r}, expected {default_namespace!r}"
                )
        else:
            anchor_id = ref

        if anchor_id not in anchor_map:
            raise CompositionError(
                f"Instance {instance_id!r} {label}: anchor {anchor_id!r} not found "
                f"in imported asset"
            )
        points.append(anchor_map[anchor_id])

    return points


def _resolve_local_anchors(
    refs: list[str],
    anchor_map: dict[str, np.ndarray],
    instance_id: str,
) -> list[np.ndarray]:
    """Resolve local anchor references."""
    points = []
    for ref in refs:
        if ref not in anchor_map:
            raise CompositionError(f"Instance {instance_id!r} to: local anchor {ref!r} not found")
        points.append(anchor_map[ref])
    return points
