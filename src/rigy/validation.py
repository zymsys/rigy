"""Semantic validation for parsed Rigy specs."""

from __future__ import annotations

import math
import warnings

from rigy.errors import ValidationError
from rigy.models import ResolvedAsset, RigySpec


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
    _check_weight_map_refs(spec)
    _check_mesh_single_binding(spec)
    _check_weights_in_range(spec)
    _check_unique_anchor_ids(spec)
    _check_unique_instance_ids(spec)
    _check_instance_import_refs(spec)
    _check_instance_mesh_refs(spec)
    _check_no_id_collisions(spec)
    _check_no_nan_infinity(spec)
    _warn_armature_root_not_at_origin(spec)


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


def _check_weight_map_refs(spec: RigySpec) -> None:
    """Validate weight_maps references: primitive_id, bone_ids, weight ranges."""
    # Build primitive id sets per mesh
    prim_ids_by_mesh: dict[str, set[str]] = {}
    for mesh in spec.meshes:
        prim_ids_by_mesh[mesh.id] = {p.id for p in mesh.primitives}

    # Build bone id sets per armature
    bone_ids_by_arm: dict[str, set[str]] = {}
    for arm in spec.armatures:
        bone_ids_by_arm[arm.id] = {b.id for b in arm.bones}

    for binding in spec.bindings:
        if not binding.weight_maps:
            continue

        prim_ids = prim_ids_by_mesh.get(binding.mesh_id, set())
        bone_ids = bone_ids_by_arm.get(binding.armature_id, set())

        # Check for pw + wm overlap and warn
        pw_prim_ids = {pw.primitive_id for pw in binding.weights}

        for wm in binding.weight_maps:
            if wm.primitive_id not in prim_ids:
                raise ValidationError(
                    f"Weight map references unknown primitive: {wm.primitive_id!r}"
                )

            if wm.primitive_id in pw_prim_ids:
                warnings.warn(
                    f"Primitive {wm.primitive_id!r} has both per-primitive weights "
                    f"and a weight map; weight map layers will override",
                    stacklevel=2,
                )

            if wm.gradients:
                for grad in wm.gradients:
                    for bw in grad.from_:
                        if bw.bone_id not in bone_ids:
                            raise ValidationError(
                                f"Weight map gradient references unknown bone: {bw.bone_id!r}"
                            )
                        if bw.weight < 0.0 or bw.weight > 1.0:
                            raise ValidationError(
                                f"Weight {bw.weight} for bone {bw.bone_id!r} in gradient "
                                f"is out of range [0, 1]"
                            )
                    for bw in grad.to:
                        if bw.bone_id not in bone_ids:
                            raise ValidationError(
                                f"Weight map gradient references unknown bone: {bw.bone_id!r}"
                            )
                        if bw.weight < 0.0 or bw.weight > 1.0:
                            raise ValidationError(
                                f"Weight {bw.weight} for bone {bw.bone_id!r} in gradient "
                                f"is out of range [0, 1]"
                            )

            if wm.overrides:
                for ov in wm.overrides:
                    for bw in ov.bones:
                        if bw.bone_id not in bone_ids:
                            raise ValidationError(
                                f"Weight map override references unknown bone: {bw.bone_id!r}"
                            )
                        if bw.weight < 0.0 or bw.weight > 1.0:
                            raise ValidationError(
                                f"Weight {bw.weight} for bone {bw.bone_id!r} in override "
                                f"is out of range [0, 1]"
                            )


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


def _check_unique_anchor_ids(spec: RigySpec) -> None:
    seen: set[str] = set()
    for anchor in spec.anchors:
        if anchor.id in seen:
            raise ValidationError(f"Duplicate anchor id: {anchor.id!r}")
        seen.add(anchor.id)


def _check_unique_instance_ids(spec: RigySpec) -> None:
    seen: set[str] = set()
    for inst in spec.instances:
        if inst.id in seen:
            raise ValidationError(f"Duplicate instance id: {inst.id!r}")
        seen.add(inst.id)


def _check_instance_import_refs(spec: RigySpec) -> None:
    for inst in spec.instances:
        if inst.import_ is None:
            continue  # local mesh instance
        if inst.import_ not in spec.imports:
            raise ValidationError(
                f"Instance {inst.id!r} references unknown import: {inst.import_!r}"
            )


def _check_instance_mesh_refs(spec: RigySpec) -> None:
    mesh_ids = {m.id for m in spec.meshes}
    for inst in spec.instances:
        if inst.mesh_id is None:
            continue
        if inst.mesh_id not in mesh_ids:
            raise ValidationError(f"Instance {inst.id!r} references unknown mesh: {inst.mesh_id!r}")


def _check_no_id_collisions(spec: RigySpec) -> None:
    """Check that anchor, mesh, armature, and instance IDs are all distinct."""
    all_ids: dict[str, str] = {}  # id -> category

    for mesh in spec.meshes:
        if mesh.id in all_ids:
            raise ValidationError(
                f"ID collision: {mesh.id!r} used as both mesh and {all_ids[mesh.id]}"
            )
        all_ids[mesh.id] = "mesh"

    for arm in spec.armatures:
        if arm.id in all_ids:
            raise ValidationError(
                f"ID collision: {arm.id!r} used as both armature and {all_ids[arm.id]}"
            )
        all_ids[arm.id] = "armature"

    for anchor in spec.anchors:
        if anchor.id in all_ids:
            raise ValidationError(
                f"ID collision: {anchor.id!r} used as both anchor and {all_ids[anchor.id]}"
            )
        all_ids[anchor.id] = "anchor"

    for inst in spec.instances:
        if inst.id in all_ids:
            raise ValidationError(
                f"ID collision: {inst.id!r} used as both instance and {all_ids[inst.id]}"
            )
        all_ids[inst.id] = "instance"


def validate_composition(asset: ResolvedAsset) -> None:
    """Cross-asset validation for composition.

    Checks that all anchor references in instances can be resolved:
    - 'from' anchors exist in the imported asset
    - 'to' anchors exist in the root spec

    Raises:
        ValidationError: On any cross-asset validation failure.
    """
    spec = asset.spec
    local_anchor_ids = {a.id for a in spec.anchors}

    for inst in spec.instances:
        if inst.import_ is None:
            continue  # local mesh instance, no cross-asset validation needed
        imported = asset.imported_assets.get(inst.import_)
        if imported is None:
            raise ValidationError(
                f"Instance {inst.id!r}: imported asset {inst.import_!r} not resolved"
            )

        imported_anchor_ids = {a.id for a in imported.spec.anchors}

        # Validate 'from' anchor refs
        for ref in inst.attach3.from_:
            if "." in ref:
                _ns, anchor_id = ref.split(".", 1)
            else:
                anchor_id = ref
            if anchor_id not in imported_anchor_ids:
                raise ValidationError(
                    f"Instance {inst.id!r}: from anchor {ref!r} not found in "
                    f"imported asset {inst.import_!r}"
                )

        # Validate 'to' anchor refs
        for ref in inst.attach3.to:
            if ref not in local_anchor_ids:
                raise ValidationError(
                    f"Instance {inst.id!r}: to anchor {ref!r} not found in local anchors"
                )


def _check_no_nan_infinity(spec: RigySpec) -> None:
    """V32: Reject NaN or ±Infinity in any numeric field."""

    def _check_floats(values: tuple[float, ...] | list[float], context: str) -> None:
        for v in values:
            if not math.isfinite(v):
                raise ValidationError(f"Non-finite value {v} in {context}")

    def _check_float(value: float, context: str) -> None:
        if not math.isfinite(value):
            raise ValidationError(f"Non-finite value {value} in {context}")

    for mesh in spec.meshes:
        for prim in mesh.primitives:
            for key, val in prim.dimensions.items():
                _check_float(val, f"primitive {prim.id!r} dimension {key}")
            if prim.transform:
                if prim.transform.translation:
                    _check_floats(prim.transform.translation, f"primitive {prim.id!r} translation")
                if prim.transform.rotation_euler:
                    _check_floats(prim.transform.rotation_euler, f"primitive {prim.id!r} rotation")

    for arm in spec.armatures:
        for bone in arm.bones:
            _check_floats(bone.head, f"bone {bone.id!r} head")
            _check_floats(bone.tail, f"bone {bone.id!r} tail")
            _check_float(bone.roll, f"bone {bone.id!r} roll")

    for binding in spec.bindings:
        for pw in binding.weights:
            for bw in pw.bones:
                _check_float(bw.weight, f"bone weight for {bw.bone_id!r}")
        if binding.weight_maps:
            for wm in binding.weight_maps:
                if wm.gradients:
                    for grad in wm.gradients:
                        _check_floats(grad.range, "gradient range")
                        for bw in grad.from_:
                            _check_float(bw.weight, f"gradient from weight for {bw.bone_id!r}")
                        for bw in grad.to:
                            _check_float(bw.weight, f"gradient to weight for {bw.bone_id!r}")
                if wm.overrides:
                    for ov in wm.overrides:
                        for bw in ov.bones:
                            _check_float(bw.weight, f"override weight for {bw.bone_id!r}")

    for anchor in spec.anchors:
        _check_floats(anchor.translation, f"anchor {anchor.id!r} translation")


def _warn_armature_root_not_at_origin(spec: RigySpec) -> None:
    """Emit a warning if any armature's root bone has head != (0,0,0)."""
    for arm in spec.armatures:
        for bone in arm.bones:
            if bone.parent == "none":
                hx, hy, hz = bone.head
                if abs(hx) > 1e-9 or abs(hy) > 1e-9 or abs(hz) > 1e-9:
                    warnings.warn(
                        f"Armature {arm.id!r}: root bone {bone.id!r} head is "
                        f"({hx}, {hy}, {hz}), not at origin. Convention is to "
                        f"place the armature root at (0, 0, 0).",
                        stacklevel=2,
                    )
