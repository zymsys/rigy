"""Validation for Rigs scene composition specs."""

from __future__ import annotations

from rigy.attach3 import build_frame3
from rigy.errors import CompositionError, ValidationError
from rigy.rigs_models import ResolvedRigsAsset, SceneChild

import numpy as np


def validate_rigs(asset: ResolvedRigsAsset) -> None:
    """Run all Rigs validation checks.

    Checks (per spec Section 11):
    1. scene.base must be a key in imports
    2. Every child.base must be a key in imports
    3. All instance IDs unique across entire tree
    4. Slot anchors resolvable (named or explicit)
    5. Mount anchors resolvable (named or explicit)
    6. frame3 non-degeneracy

    Raises:
        ValidationError: On any semantic violation.
    """
    spec = asset.spec

    # Check 1: scene.base must be an import alias
    if spec.scene.base not in spec.imports:
        raise ValidationError(f"scene.base {spec.scene.base!r} is not a key in imports")

    # Collect all children for checks 2-6
    all_children: list[tuple[SceneChild, str]] = []  # (child, parent_alias)
    if spec.scene.children:
        for child in spec.scene.children:
            _collect_children(child, spec.scene.base, all_children)

    # Check 2: every child.base must be an import alias
    for child, _parent in all_children:
        if child.base not in spec.imports:
            raise ValidationError(
                f"Instance {child.id!r}: base {child.base!r} is not a key in imports"
            )

    # Check 3: unique instance IDs
    ids = [child.id for child, _ in all_children]
    seen: set[str] = set()
    for id_ in ids:
        if id_ in seen:
            raise ValidationError(f"Duplicate instance ID: {id_!r}")
        seen.add(id_)

    # Checks 4-6: anchor resolution and frame3 validity
    for child, parent_alias in all_children:
        parent_asset = asset.resolved_imports.get(parent_alias)
        child_asset = asset.resolved_imports.get(child.base)

        if parent_asset is None:
            raise ValidationError(
                f"Instance {child.id!r}: parent asset {parent_alias!r} not resolved"
            )
        if child_asset is None:
            raise ValidationError(f"Instance {child.id!r}: child asset {child.base!r} not resolved")

        # Resolve slot anchors (on parent asset)
        slot_ids = _resolve_ref_anchors(
            child.place.slot.name,
            child.place.slot.anchors,
            parent_asset,
            "slot",
            child.id,
        )

        # Resolve mount anchors (on child asset)
        mount_ids = _resolve_ref_anchors(
            child.place.mount.name,
            child.place.mount.anchors,
            child_asset,
            "mount",
            child.id,
        )

        # Check 6: frame3 non-degeneracy
        parent_anchor_map = {
            a.id: np.array(a.translation, dtype=np.float64) for a in parent_asset.spec.anchors
        }
        child_anchor_map = {
            a.id: np.array(a.translation, dtype=np.float64) for a in child_asset.spec.anchors
        }

        slot_points = [parent_anchor_map[aid] for aid in slot_ids]
        mount_points = [child_anchor_map[aid] for aid in mount_ids]

        try:
            build_frame3(slot_points[0], slot_points[1], slot_points[2])
        except CompositionError as e:
            raise ValidationError(f"Instance {child.id!r}: slot frame3 degenerate: {e}") from e

        try:
            build_frame3(mount_points[0], mount_points[1], mount_points[2])
        except CompositionError as e:
            raise ValidationError(f"Instance {child.id!r}: mount frame3 degenerate: {e}") from e


def _collect_children(
    child: SceneChild,
    parent_alias: str,
    out: list[tuple[SceneChild, str]],
) -> None:
    """Recursively collect all children with their parent alias."""
    out.append((child, parent_alias))
    if child.children:
        for grandchild in child.children:
            _collect_children(grandchild, child.base, out)


def _resolve_ref_anchors(
    name: str | None,
    explicit_anchors: list[str] | None,
    resolved_asset,
    ref_type: str,
    instance_id: str,
) -> list[str]:
    """Resolve a slot/mount reference to 3 anchor IDs.

    Args:
        name: Named reference (from contract frame3_sets).
        explicit_anchors: Explicit anchor triple.
        resolved_asset: The ResolvedAsset to resolve against.
        ref_type: "slot" or "mount" for error messages.
        instance_id: Instance ID for error messages.

    Returns:
        List of 3 anchor IDs.

    Raises:
        ValidationError: If anchors can't be resolved.
    """
    asset_anchor_ids = {a.id for a in resolved_asset.spec.anchors}

    if name is not None:
        # Named reference: resolve from contract frame3_sets
        contract = resolved_asset.contract
        if contract is None:
            raise ValidationError(
                f"Instance {instance_id!r}: {ref_type} uses named reference "
                f"{name!r} but asset has no contract"
            )

        # Look in frame3_sets for both "slots.<name>" and "mounts.<name>" patterns
        # and also direct name lookup
        anchor_ids = None
        for key_pattern in [f"{ref_type}s.{name}", name]:
            if key_pattern in contract.frame3_sets:
                anchor_ids = contract.frame3_sets[key_pattern]
                break

        if anchor_ids is None:
            raise ValidationError(
                f"Instance {instance_id!r}: {ref_type} name {name!r} not found "
                f"in contract frame3_sets"
            )

        if len(anchor_ids) != 3:
            raise ValidationError(
                f"Instance {instance_id!r}: {ref_type} name {name!r} resolves to "
                f"{len(anchor_ids)} anchors (expected 3)"
            )

        # Verify anchor IDs exist in the asset
        for aid in anchor_ids:
            if aid not in asset_anchor_ids:
                raise ValidationError(
                    f"Instance {instance_id!r}: {ref_type} name {name!r} references "
                    f"anchor {aid!r} not found in asset"
                )

        return anchor_ids

    # Explicit anchors
    assert explicit_anchors is not None
    for aid in explicit_anchors:
        if aid not in asset_anchor_ids:
            raise ValidationError(
                f"Instance {instance_id!r}: {ref_type} anchor {aid!r} not found in asset"
            )
    return explicit_anchors
