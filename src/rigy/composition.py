"""Composition: resolve instances and compute attach3 transforms."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from rigy.attach3 import compute_attach3_transform
from rigy.contracts import validate_contract
from rigy.errors import CompositionError
from rigy.models import ResolvedAsset, RigySpec, Transform


@dataclass
class ResolvedInstance:
    id: str
    source_spec: RigySpec | None
    transform: np.ndarray  # 4x4
    namespace: str
    mesh_id: str | None = None


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
        # Local mesh instance (no import, references a mesh in the same spec)
        if inst.import_ is None:
            transform = np.eye(4, dtype=np.float64)
            if inst.attach3 is not None:
                # Local mesh instance with attach3: resolve anchor-based transform
                from_points = _resolve_local_anchors(inst.attach3.from_, local_anchors, inst.id)
                to_points = _resolve_local_anchors(inst.attach3.to, local_anchors, inst.id)
                transform = compute_attach3_transform(
                    (from_points[0], from_points[1], from_points[2]),
                    (to_points[0], to_points[1], to_points[2]),
                    inst.attach3.mode,
                )
            resolved_instances.append(
                ResolvedInstance(
                    id=inst.id,
                    source_spec=None,
                    transform=transform,
                    namespace=inst.id,
                    mesh_id=inst.mesh_id,
                )
            )
            continue

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


def bake_transforms(composed: ComposedAsset) -> ComposedAsset:
    """Bake instance transforms into geometry and bones.

    For each instance with a source_spec, deep-copies the spec, applies the
    4x4 transform to all primitive translations/rotations and bone head/tail
    positions, then sets the instance transform to identity.

    Returns a new ComposedAsset (does not mutate the input).
    """
    new_instances = []
    for inst in composed.instances:
        if inst.source_spec is None:
            # Local mesh instance — no spec to bake, just keep as-is
            new_instances.append(inst)
            continue

        # Check if transform is already identity
        if np.allclose(inst.transform, np.eye(4), atol=1e-12):
            new_instances.append(inst)
            continue

        baked_spec = inst.source_spec.model_copy(deep=True)
        T = inst.transform
        R3 = T[:3, :3]  # upper-left 3x3 rotation/scale

        # Bake mesh primitive transforms
        for mesh in baked_spec.meshes:
            for prim in mesh.primitives:
                _bake_primitive_transform(prim, T, R3)

        # Bake bone positions
        for arm in baked_spec.armatures:
            for bone in arm.bones:
                head = np.array(bone.head, dtype=np.float64)
                tail = np.array(bone.tail, dtype=np.float64)
                new_head = (T @ np.append(head, 1.0))[:3]
                new_tail = (T @ np.append(tail, 1.0))[:3]
                bone.head = tuple(float(x) for x in new_head)
                bone.tail = tuple(float(x) for x in new_tail)

        new_instances.append(
            ResolvedInstance(
                id=inst.id,
                source_spec=baked_spec,
                transform=np.eye(4, dtype=np.float64),
                namespace=inst.namespace,
                mesh_id=inst.mesh_id,
            )
        )

    return ComposedAsset(root_spec=composed.root_spec, instances=new_instances)


def _bake_primitive_transform(prim, T: np.ndarray, R3: np.ndarray) -> None:
    """Apply a 4x4 transform to a primitive's translation and rotation."""
    # Get current translation
    tx, ty, tz = (
        prim.transform.translation if prim.transform and prim.transform.translation else (0, 0, 0)
    )
    pos = np.array([tx, ty, tz, 1.0], dtype=np.float64)
    new_pos = (T @ pos)[:3]

    # Get current rotation (Euler XYZ in radians)
    rx, ry, rz = (
        prim.transform.rotation_euler
        if prim.transform and prim.transform.rotation_euler
        else (0, 0, 0)
    )

    # Build local rotation matrix from Euler XYZ
    local_R = _euler_xyz_to_matrix(rx, ry, rz)

    # Combined rotation = instance_R @ local_R
    combined_R = R3 @ local_R

    # Extract Euler XYZ from combined rotation
    new_rx, new_ry, new_rz = _matrix_to_euler_xyz(combined_R)

    new_translation = (float(new_pos[0]), float(new_pos[1]), float(new_pos[2]))

    has_rotation = abs(new_rx) > 1e-12 or abs(new_ry) > 1e-12 or abs(new_rz) > 1e-12
    new_rotation = (float(new_rx), float(new_ry), float(new_rz)) if has_rotation else None

    prim.transform = Transform(
        translation=new_translation,
        rotation_euler=new_rotation,
    )


def _euler_xyz_to_matrix(rx: float, ry: float, rz: float) -> np.ndarray:
    """Convert Euler XYZ angles (radians) to a 3x3 rotation matrix."""
    cx, sx = math.cos(rx), math.sin(rx)
    cy, sy = math.cos(ry), math.sin(ry)
    cz, sz = math.cos(rz), math.sin(rz)

    Rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    Ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    Rz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])

    return Rz @ Ry @ Rx


def _matrix_to_euler_xyz(R: np.ndarray) -> tuple[float, float, float]:
    """Extract Euler XYZ angles (radians) from a 3x3 rotation matrix."""
    # R = Rz @ Ry @ Rx
    # R[2,0] = -sin(ry)
    sy = -R[2, 0]
    sy = max(-1.0, min(1.0, sy))
    ry = math.asin(sy)

    if abs(abs(sy) - 1.0) < 1e-9:
        # Gimbal lock
        rx = math.atan2(-R[1, 2], R[1, 1])
        rz = 0.0
    else:
        cy = math.cos(ry)
        rx = math.atan2(R[2, 1] / cy, R[2, 2] / cy)
        rz = math.atan2(R[1, 0] / cy, R[0, 0] / cy)

    return rx, ry, rz
