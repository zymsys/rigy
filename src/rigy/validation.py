"""Semantic validation for parsed Rigy specs."""

from __future__ import annotations

import math
import re
import warnings

from rigy.errors import ValidationError
from rigy.models import UV_ROLE_VOCABULARY, ResolvedAsset, RigySpec


def validate(spec: RigySpec) -> None:
    """Run all semantic validation checks on a parsed spec.

    Raises:
        ValidationError: On any semantic rule violation.
    """
    _check_material_base_color_length(spec)
    _check_material_base_color_range(spec)
    _check_material_refs(spec)
    _check_mesh_material_consistency(spec)
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
    _check_dqs_rigid_bones(spec)
    _check_pose_quaternions(spec)
    _check_pose_bone_refs(spec)
    _check_uv_role_vocabulary(spec)
    _check_uv_set_token_format(spec)
    _check_material_uv_role_vocabulary(spec)
    _check_material_uv_role_refs(spec)
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
    """Check that material, anchor, mesh, armature, and instance IDs are all distinct."""
    all_ids: dict[str, str] = {}  # id -> category

    for mat_id in spec.materials:
        if mat_id in all_ids:
            raise ValidationError(
                f"ID collision: {mat_id!r} used as both material and {all_ids[mat_id]}"
            )
        all_ids[mat_id] = "material"

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


def _check_material_base_color_length(spec: RigySpec) -> None:
    """V39: Each material's base_color must have exactly 4 components."""
    for mat_id, mat in spec.materials.items():
        if len(mat.base_color) != 4:
            raise ValidationError(
                f"Material {mat_id!r}: base_color must have 4 components, got {len(mat.base_color)}"
            )


def _check_material_base_color_range(spec: RigySpec) -> None:
    """V40: Each base_color component must be finite and in [0.0, 1.0]."""
    for mat_id, mat in spec.materials.items():
        for i, c in enumerate(mat.base_color):
            if not math.isfinite(c):
                raise ValidationError(f"Material {mat_id!r}: base_color[{i}] is not finite ({c})")
            if c < 0.0 or c > 1.0:
                raise ValidationError(
                    f"Material {mat_id!r}: base_color[{i}] = {c} is outside [0.0, 1.0]"
                )


def _check_material_refs(spec: RigySpec) -> None:
    """V38: Primitive material references must exist in the materials table."""
    for mesh in spec.meshes:
        for prim in mesh.primitives:
            if prim.material is not None and prim.material not in spec.materials:
                raise ValidationError(
                    f"Primitive {prim.id!r} references unknown material: {prim.material!r}"
                )


def _check_mesh_material_consistency(spec: RigySpec) -> None:
    """V41: All primitives in a mesh must share the same material reference."""
    for mesh in spec.meshes:
        if not mesh.primitives:
            continue
        first_mat = mesh.primitives[0].material
        for prim in mesh.primitives[1:]:
            if prim.material != first_mat:
                raise ValidationError(
                    f"Mesh {mesh.id!r}: inconsistent material references — "
                    f"primitive {mesh.primitives[0].id!r} has material {first_mat!r}, "
                    f"but primitive {prim.id!r} has material {prim.material!r}"
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


def _check_dqs_rigid_bones(spec: RigySpec) -> None:
    """V35: DQS requires rigid bone transforms (no scale/shear).

    The current Bone model has no scale or shear fields, so all bone
    transforms are inherently rigid. This check is a structural guard
    that reserves the validation slot for future extensions.
    """


def _check_pose_quaternions(spec: RigySpec) -> None:
    """V36: Validate pose quaternion components are finite and unit-length."""
    for pose in spec.poses:
        for bone_id, pbt in pose.bones.items():
            if pbt.rotation is not None:
                w, x, y, z = pbt.rotation
                for comp in (w, x, y, z):
                    if not math.isfinite(comp):
                        raise ValidationError(
                            f"Non-finite quaternion component in pose {pose.id!r}, bone {bone_id!r}"
                        )
                norm_sq = w * w + x * x + y * y + z * z
                if abs(norm_sq - 1.0) > 1e-6:
                    raise ValidationError(
                        f"Non-unit quaternion in pose {pose.id!r}, bone {bone_id!r}: "
                        f"‖q‖² = {norm_sq}"
                    )
            if pbt.translation is not None:
                for comp in pbt.translation:
                    if not math.isfinite(comp):
                        raise ValidationError(
                            f"Non-finite translation component in pose {pose.id!r}, "
                            f"bone {bone_id!r}"
                        )


def _check_pose_bone_refs(spec: RigySpec) -> None:
    """Verify every bone_id in every pose exists in at least one armature."""
    all_bone_ids: set[str] = set()
    for arm in spec.armatures:
        for bone in arm.bones:
            all_bone_ids.add(bone.id)

    for pose in spec.poses:
        for bone_id in pose.bones:
            if bone_id not in all_bone_ids:
                raise ValidationError(f"Pose {pose.id!r} references unknown bone: {bone_id!r}")


_UV_SET_PATTERN = re.compile(r"^uv([0-9]+)$")


def _check_uv_role_vocabulary(spec: RigySpec) -> None:
    """V43: Every uv_roles key must be in UV_ROLE_VOCABULARY."""
    for mesh in spec.meshes:
        if mesh.uv_roles is None:
            continue
        for role in mesh.uv_roles:
            if role not in UV_ROLE_VOCABULARY:
                raise ValidationError(
                    f"Mesh {mesh.id!r}: unknown UV role {role!r} "
                    f"(valid: {sorted(UV_ROLE_VOCABULARY)})"
                )


def _check_uv_set_token_format(spec: RigySpec) -> None:
    """V45: Each uv_roles.<role>.set must match 'uv<N>' where N >= 0."""
    for mesh in spec.meshes:
        if mesh.uv_roles is None:
            continue
        for role, entry in mesh.uv_roles.items():
            if not _UV_SET_PATTERN.match(entry.set):
                raise ValidationError(
                    f"Mesh {mesh.id!r}: UV role {role!r} has invalid set token "
                    f"{entry.set!r} (must match 'uv<N>' where N is a non-negative integer)"
                )


def _check_material_uv_role_vocabulary(spec: RigySpec) -> None:
    """V47: Each material uses_uv_roles entry must be in UV_ROLE_VOCABULARY."""
    for mat_id, mat in spec.materials.items():
        if mat.uses_uv_roles is None:
            continue
        for role in mat.uses_uv_roles:
            if role not in UV_ROLE_VOCABULARY:
                raise ValidationError(
                    f"Material {mat_id!r}: uses_uv_roles references unknown UV role {role!r} "
                    f"(valid: {sorted(UV_ROLE_VOCABULARY)})"
                )


def _check_material_uv_role_refs(spec: RigySpec) -> None:
    """V46: For each material with uses_uv_roles, every mesh primitive referencing
    that material must expose all referenced roles in its mesh's uv_roles."""
    # Build material -> set of required roles
    mat_roles: dict[str, list[str]] = {}
    for mat_id, mat in spec.materials.items():
        if mat.uses_uv_roles:
            mat_roles[mat_id] = mat.uses_uv_roles

    if not mat_roles:
        return

    # For each mesh, check that primitives referencing materials with uses_uv_roles
    # have the required roles exposed on their mesh
    for mesh in spec.meshes:
        mesh_uv_roles = set(mesh.uv_roles.keys()) if mesh.uv_roles else set()
        for prim in mesh.primitives:
            if prim.material is None or prim.material not in mat_roles:
                continue
            required_roles = mat_roles[prim.material]
            for role in required_roles:
                if role not in mesh_uv_roles:
                    raise ValidationError(
                        f"Mesh {mesh.id!r}: material {prim.material!r} requires "
                        f"UV role {role!r} but mesh does not expose it in uv_roles"
                    )


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
