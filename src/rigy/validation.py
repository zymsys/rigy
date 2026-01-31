"""Semantic validation for parsed Rigy specs."""

from __future__ import annotations

import math

from rigy.errors import ValidationError
from rigy.models import RigySpec


def validate(spec: RigySpec) -> None:
    """Run all semantic validation checks on a parsed spec.

    Raises:
        ValidationError: On any semantic rule violation.
    """
    _check_unique_mesh_ids(spec)
    _check_unique_primitive_ids(spec)
    _check_unique_armature_ids(spec)
    _check_unique_bone_ids(spec)
    _check_bone_hierarchy_acyclic(spec)
    _check_no_zero_length_bones(spec)
    _check_primitive_dimensions_positive(spec)
    _check_binding_refs(spec)
    _check_mesh_single_binding(spec)
    _check_weights_in_range(spec)


def _check_unique_mesh_ids(spec: RigySpec) -> None:
    seen: set[str] = set()
    for mesh in spec.meshes:
        if mesh.id in seen:
            raise ValidationError(f"Duplicate mesh id: {mesh.id!r}")
        seen.add(mesh.id)


def _check_unique_primitive_ids(spec: RigySpec) -> None:
    for mesh in spec.meshes:
        seen: set[str] = set()
        for prim in mesh.primitives:
            if prim.id in seen:
                raise ValidationError(f"Duplicate primitive id {prim.id!r} in mesh {mesh.id!r}")
            seen.add(prim.id)


def _check_unique_armature_ids(spec: RigySpec) -> None:
    seen: set[str] = set()
    for arm in spec.armatures:
        if arm.id in seen:
            raise ValidationError(f"Duplicate armature id: {arm.id!r}")
        seen.add(arm.id)


def _check_unique_bone_ids(spec: RigySpec) -> None:
    for arm in spec.armatures:
        seen: set[str] = set()
        for bone in arm.bones:
            if bone.id in seen:
                raise ValidationError(f"Duplicate bone id {bone.id!r} in armature {arm.id!r}")
            seen.add(bone.id)


def _check_bone_hierarchy_acyclic(spec: RigySpec) -> None:
    for arm in spec.armatures:
        parent_map: dict[str, str | None] = {}
        for bone in arm.bones:
            parent_map[bone.id] = None if bone.parent == "none" else bone.parent

        for bone_id in parent_map:
            visited: set[str] = set()
            current: str | None = bone_id
            while current is not None:
                if current in visited:
                    raise ValidationError(
                        f"Cycle detected in bone hierarchy of armature {arm.id!r} "
                        f"at bone {current!r}"
                    )
                visited.add(current)
                current = parent_map.get(current)


def _check_no_zero_length_bones(spec: RigySpec) -> None:
    for arm in spec.armatures:
        for bone in arm.bones:
            dx = bone.tail[0] - bone.head[0]
            dy = bone.tail[1] - bone.head[1]
            dz = bone.tail[2] - bone.head[2]
            length = math.sqrt(dx * dx + dy * dy + dz * dz)
            if length < 1e-9:
                raise ValidationError(f"Zero-length bone {bone.id!r} in armature {arm.id!r}")


def _check_primitive_dimensions_positive(spec: RigySpec) -> None:
    for mesh in spec.meshes:
        for prim in mesh.primitives:
            for key, val in prim.dimensions.items():
                if val <= 0:
                    raise ValidationError(
                        f"Primitive {prim.id!r} has non-positive dimension {key}={val}"
                    )


def _check_binding_refs(spec: RigySpec) -> None:
    mesh_ids = {m.id for m in spec.meshes}
    armature_ids = {a.id for a in spec.armatures}

    # Build primitive id sets per mesh
    prim_ids_by_mesh: dict[str, set[str]] = {}
    for mesh in spec.meshes:
        prim_ids_by_mesh[mesh.id] = {p.id for p in mesh.primitives}

    # Build bone id sets per armature
    bone_ids_by_arm: dict[str, set[str]] = {}
    for arm in spec.armatures:
        bone_ids_by_arm[arm.id] = {b.id for b in arm.bones}

    for binding in spec.bindings:
        if binding.mesh_id not in mesh_ids:
            raise ValidationError(f"Binding references unknown mesh: {binding.mesh_id!r}")
        if binding.armature_id not in armature_ids:
            raise ValidationError(f"Binding references unknown armature: {binding.armature_id!r}")

        prim_ids = prim_ids_by_mesh.get(binding.mesh_id, set())
        bone_ids = bone_ids_by_arm.get(binding.armature_id, set())

        for pw in binding.weights:
            if pw.primitive_id not in prim_ids:
                raise ValidationError(f"Binding references unknown primitive: {pw.primitive_id!r}")
            for bw in pw.bones:
                if bw.bone_id not in bone_ids:
                    raise ValidationError(f"Binding references unknown bone: {bw.bone_id!r}")


def _check_mesh_single_binding(spec: RigySpec) -> None:
    seen: set[str] = set()
    for binding in spec.bindings:
        if binding.mesh_id in seen:
            raise ValidationError(f"Mesh {binding.mesh_id!r} appears in multiple bindings")
        seen.add(binding.mesh_id)


def _check_weights_in_range(spec: RigySpec) -> None:
    for binding in spec.bindings:
        for pw in binding.weights:
            for bw in pw.bones:
                if bw.weight < 0.0 or bw.weight > 1.0:
                    raise ValidationError(
                        f"Weight {bw.weight} for bone {bw.bone_id!r} on "
                        f"primitive {pw.primitive_id!r} is out of range [0, 1]"
                    )
