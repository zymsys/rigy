"""Mirror-X symmetry expansion for Rigy specs."""

from __future__ import annotations

import copy

from rigy.models import (
    Anchor,
    Bone,
    BoneWeight,
    Instance,
    Primitive,
    PrimitiveWeights,
    RigySpec,
    Transform,
)


def expand_symmetry(spec: RigySpec) -> RigySpec:
    """Expand symmetry directives, returning a new spec.

    mirror_x duplicates primitives, bones, and weights with negated X
    and prefix replacement. Runs before validation.
    """
    if spec.symmetry is None or spec.symmetry.mirror_x is None:
        return spec

    mirror = spec.symmetry.mirror_x
    prefix_from = mirror.prefix_from
    prefix_to = mirror.prefix_to

    new_spec = spec.model_copy(deep=True)

    # Expand meshes
    for mesh in new_spec.meshes:
        new_prims: list[Primitive] = []
        for prim in mesh.primitives:
            if prim.id.startswith(prefix_from):
                mirrored = _mirror_primitive(prim, prefix_from, prefix_to)
                new_prims.append(mirrored)
        mesh.primitives.extend(new_prims)

    # Expand armature bones
    for arm in new_spec.armatures:
        new_bones: list[Bone] = []
        for bone in arm.bones:
            if bone.id.startswith(prefix_from):
                mirrored = _mirror_bone(bone, prefix_from, prefix_to)
                new_bones.append(mirrored)
        arm.bones.extend(new_bones)

    # Expand binding weights
    for binding in new_spec.bindings:
        new_weights: list[PrimitiveWeights] = []
        for pw in binding.weights:
            if pw.primitive_id.startswith(prefix_from):
                mirrored = _mirror_primitive_weights(pw, prefix_from, prefix_to)
                new_weights.append(mirrored)
        binding.weights.extend(new_weights)

    # Expand anchors
    new_anchors: list[Anchor] = []
    for anchor in new_spec.anchors:
        if anchor.id.startswith(prefix_from):
            new_anchors.append(_mirror_anchor(anchor, prefix_from, prefix_to))
    new_spec.anchors.extend(new_anchors)

    # Expand instances: mirror to anchors (local), keep from anchors (imported asset space)
    new_instances: list[Instance] = []
    for inst in new_spec.instances:
        if inst.id.startswith(prefix_from):
            new_instances.append(_mirror_instance(inst, prefix_from, prefix_to))
    new_spec.instances.extend(new_instances)

    # Clear symmetry after expansion
    new_spec.symmetry = None

    return new_spec


def _rename(name: str, prefix_from: str, prefix_to: str) -> str:
    """Replace prefix in a name."""
    if name.startswith(prefix_from):
        return prefix_to + name[len(prefix_from) :]
    return name


def _mirror_primitive(prim: Primitive, prefix_from: str, prefix_to: str) -> Primitive:
    """Create a mirrored copy of a primitive with negated X."""
    new_id = _rename(prim.id, prefix_from, prefix_to)
    new_name = _rename(prim.name, prefix_from, prefix_to) if prim.name else None

    new_transform = None
    if prim.transform:
        tx, ty, tz = prim.transform.translation or (0, 0, 0)
        rx, ry, rz = prim.transform.rotation_euler or (0, 0, 0)
        new_transform = Transform(
            translation=(-tx, ty, tz),
            rotation_euler=(-rx, ry, rz) if prim.transform.rotation_euler else None,
        )
    else:
        # Even without a transform, mirroring means creating one with negated X=0
        pass

    return Primitive(
        type=prim.type,
        id=new_id,
        name=new_name,
        dimensions=copy.deepcopy(prim.dimensions),
        transform=new_transform,
        material=prim.material,
    )


def _mirror_bone(bone: Bone, prefix_from: str, prefix_to: str) -> Bone:
    """Create a mirrored copy of a bone with negated X."""
    new_id = _rename(bone.id, prefix_from, prefix_to)
    new_parent = _rename(bone.parent, prefix_from, prefix_to)

    return Bone(
        id=new_id,
        parent=new_parent,
        head=(-bone.head[0], bone.head[1], bone.head[2]),
        tail=(-bone.tail[0], bone.tail[1], bone.tail[2]),
        roll=-bone.roll,
    )


def _mirror_primitive_weights(
    pw: PrimitiveWeights, prefix_from: str, prefix_to: str
) -> PrimitiveWeights:
    """Create a mirrored copy of primitive weights."""
    new_prim_id = _rename(pw.primitive_id, prefix_from, prefix_to)
    new_bones = [
        BoneWeight(
            bone_id=_rename(bw.bone_id, prefix_from, prefix_to),
            weight=bw.weight,
        )
        for bw in pw.bones
    ]
    return PrimitiveWeights(primitive_id=new_prim_id, bones=new_bones)


def _mirror_anchor(anchor: Anchor, prefix_from: str, prefix_to: str) -> Anchor:
    """Create a mirrored copy of an anchor with negated X translation."""
    new_id = _rename(anchor.id, prefix_from, prefix_to)
    tx, ty, tz = anchor.translation
    return Anchor(
        id=new_id,
        translation=(-tx, ty, tz),
        scope=anchor.scope,
    )


def _mirror_instance(inst: Instance, prefix_from: str, prefix_to: str) -> Instance:
    """Create a mirrored copy of an instance.

    - Renames instance ID via prefix substitution
    - Same import ref (imported asset is immutable)
    - from anchors unchanged (imported asset space)
    - to anchors renamed (they reference local anchors that were also mirrored)
    """
    new_id = _rename(inst.id, prefix_from, prefix_to)
    new_to = [_rename(a, prefix_from, prefix_to) for a in inst.attach3.to]
    from rigy.models import Attach3

    return Instance(
        id=new_id,
        import_=inst.import_,
        attach3=Attach3(
            from_=list(inst.attach3.from_),
            to=new_to,
            mode=inst.attach3.mode,
        ),
    )
