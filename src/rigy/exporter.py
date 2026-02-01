"""glTF/GLB assembly via pygltflib."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pygltflib

from rigy.composition import ComposedAsset, ResolvedInstance
from rigy.dqs import evaluate_pose
from rigy.errors import ExportError
from rigy.models import Pose, RigySpec
from rigy.skinning import SkinData, compute_skinning
from rigy.tessellation import tessellate_mesh


def export_gltf(
    spec_or_composed: RigySpec | ComposedAsset,
    output_path: Path,
    *,
    yaml_dir: Path | None = None,
) -> None:
    """Export a validated Rigy spec or composed asset to a GLB file.

    Pipeline: tessellate -> skin -> build glTF scene -> write GLB.
    """
    try:
        if isinstance(spec_or_composed, ComposedAsset):
            gltf = _build_gltf_composed(spec_or_composed, yaml_dir=yaml_dir)
        else:
            gltf = _build_gltf(spec_or_composed, yaml_dir=yaml_dir)
        gltf.save(str(output_path))
    except Exception as e:
        if isinstance(e, ExportError):
            raise
        raise ExportError(f"Failed to export glTF: {e}") from e


def export_baked_gltf(
    spec: RigySpec,
    pose: Pose,
    output_path: Path,
    *,
    yaml_dir: Path | None = None,
) -> None:
    """Export a baked (pose-evaluated) GLB with skinning removed.

    Tessellates meshes, evaluates the pose via DQS or LBS, writes deformed
    geometry without JOINTS_0/WEIGHTS_0/Skin/IBM data.
    """
    try:
        gltf = _build_gltf_baked(spec, pose, yaml_dir=yaml_dir)
        gltf.save(str(output_path))
    except Exception as e:
        if isinstance(e, ExportError):
            raise
        raise ExportError(f"Failed to export baked glTF: {e}") from e


def _build_gltf_baked(
    spec: RigySpec,
    pose: Pose,
    *,
    yaml_dir: Path | None = None,
) -> pygltflib.GLTF2:
    """Build baked glTF2 structure — deformed geometry, no skin."""
    gltf = pygltflib.GLTF2(
        scene=0,
        scenes=[pygltflib.Scene(nodes=[])],
        nodes=[],
        meshes=[],
        accessors=[],
        bufferViews=[],
        buffers=[],
        materials=[],
        skins=[],
    )

    blob_data = bytearray()
    material_map: dict[str, int] = {}
    scene_nodes: list[int] = []

    # Build binding lookup
    binding_map: dict[str, tuple] = {}
    for binding in spec.bindings:
        arm = next((a for a in spec.armatures if a.id == binding.armature_id), None)
        if arm:
            binding_map[binding.mesh_id] = (binding, arm)

    for mesh_def in spec.meshes:
        mesh_data, prim_ranges = tessellate_mesh(mesh_def, spec.tessellation_profile)

        if len(mesh_data.positions) == 0:
            continue

        # Collect materials
        for prim in mesh_def.primitives:
            if prim.material and prim.material not in material_map:
                mat_idx = len(gltf.materials)
                gltf.materials.append(
                    pygltflib.Material(
                        name=prim.material,
                        pbrMetallicRoughness=pygltflib.PbrMetallicRoughness(),
                    )
                )
                material_map[prim.material] = mat_idx

        # Get deformed positions/normals if bound
        positions = mesh_data.positions
        mesh_normals = mesh_data.normals
        if mesh_def.id in binding_map:
            binding, armature = binding_map[mesh_def.id]
            skin_data = compute_skinning(
                binding,
                armature,
                prim_ranges,
                len(positions),
                positions=positions,
                yaml_dir=yaml_dir,
            )
            positions, mesh_normals = evaluate_pose(
                spec,
                skin_data,
                armature,
                binding,
                pose,
                positions,
                mesh_normals,
            )

        # Write position data
        pos_offset = len(blob_data)
        pos_bytes = positions.astype(np.float32).tobytes()
        blob_data.extend(pos_bytes)

        pos_bv_idx = len(gltf.bufferViews)
        gltf.bufferViews.append(
            pygltflib.BufferView(
                buffer=0,
                byteOffset=pos_offset,
                byteLength=len(pos_bytes),
                target=pygltflib.ARRAY_BUFFER,
            )
        )

        pos_f32 = positions.astype(np.float32)
        pos_min = pos_f32.min(axis=0).tolist()
        pos_max = pos_f32.max(axis=0).tolist()
        pos_acc_idx = len(gltf.accessors)
        gltf.accessors.append(
            pygltflib.Accessor(
                bufferView=pos_bv_idx,
                byteOffset=0,
                componentType=pygltflib.FLOAT,
                count=len(positions),
                type=pygltflib.VEC3,
                max=pos_max,
                min=pos_min,
            )
        )

        # Write normal data
        norm_offset = len(blob_data)
        norm_bytes = mesh_normals.astype(np.float32).tobytes()
        blob_data.extend(norm_bytes)

        norm_bv_idx = len(gltf.bufferViews)
        gltf.bufferViews.append(
            pygltflib.BufferView(
                buffer=0,
                byteOffset=norm_offset,
                byteLength=len(norm_bytes),
                target=pygltflib.ARRAY_BUFFER,
            )
        )

        norm_acc_idx = len(gltf.accessors)
        gltf.accessors.append(
            pygltflib.Accessor(
                bufferView=norm_bv_idx,
                byteOffset=0,
                componentType=pygltflib.FLOAT,
                count=len(mesh_normals),
                type=pygltflib.VEC3,
            )
        )

        # Write index data
        idx_offset = len(blob_data)
        idx_bytes = mesh_data.indices.astype(np.uint32).tobytes()
        blob_data.extend(idx_bytes)

        idx_bv_idx = len(gltf.bufferViews)
        gltf.bufferViews.append(
            pygltflib.BufferView(
                buffer=0,
                byteOffset=idx_offset,
                byteLength=len(idx_bytes),
                target=pygltflib.ELEMENT_ARRAY_BUFFER,
            )
        )

        idx_acc_idx = len(gltf.accessors)
        gltf.accessors.append(
            pygltflib.Accessor(
                bufferView=idx_bv_idx,
                byteOffset=0,
                componentType=pygltflib.UNSIGNED_INT,
                count=len(mesh_data.indices),
                type=pygltflib.SCALAR,
            )
        )

        # No JOINTS_0/WEIGHTS_0 — baked export omits skin data
        attributes = pygltflib.Attributes(
            POSITION=pos_acc_idx,
            NORMAL=norm_acc_idx,
        )

        mat_idx = None
        if mesh_def.primitives and mesh_def.primitives[0].material:
            mat_idx = material_map.get(mesh_def.primitives[0].material)

        gltf_prim = pygltflib.Primitive(
            attributes=attributes,
            indices=idx_acc_idx,
            material=mat_idx,
        )

        mesh_idx = len(gltf.meshes)
        mesh_name = mesh_def.name or mesh_def.id
        gltf.meshes.append(pygltflib.Mesh(name=mesh_name, primitives=[gltf_prim]))

        mesh_node_idx = len(gltf.nodes)
        gltf.nodes.append(pygltflib.Node(name=mesh_name, mesh=mesh_idx))
        scene_nodes.append(mesh_node_idx)

        # Bone nodes with identity transforms (no skin)
        if mesh_def.id in binding_map:
            _, armature = binding_map[mesh_def.id]
            bone_node_indices: dict[str, int] = {}

            for bone in armature.bones:
                bone_node_idx = len(gltf.nodes)
                bone_node_indices[bone.id] = bone_node_idx
                gltf.nodes.append(pygltflib.Node(name=bone.id))

            root_bone_nodes = []
            for bone in armature.bones:
                bone_idx = bone_node_indices[bone.id]
                if bone.parent == "none":
                    root_bone_nodes.append(bone_idx)
                else:
                    parent_idx = bone_node_indices.get(bone.parent)
                    if parent_idx is not None:
                        if gltf.nodes[parent_idx].children is None:
                            gltf.nodes[parent_idx].children = []
                        gltf.nodes[parent_idx].children.append(bone_idx)

            for rbn in root_bone_nodes:
                scene_nodes.append(rbn)

    gltf.scenes[0].nodes = scene_nodes
    gltf.buffers = [pygltflib.Buffer(byteLength=len(blob_data))]
    gltf.set_binary_blob(bytes(blob_data))

    return gltf


def _build_gltf_composed(
    composed: ComposedAsset, *, yaml_dir: Path | None = None
) -> pygltflib.GLTF2:
    """Build the complete glTF2 structure for a composed asset."""
    gltf = pygltflib.GLTF2(
        scene=0,
        scenes=[pygltflib.Scene(nodes=[])],
        nodes=[],
        meshes=[],
        accessors=[],
        bufferViews=[],
        buffers=[],
        materials=[],
        skins=[],
    )

    blob_data = bytearray()
    material_map: dict[str, int] = {}
    scene_nodes: list[int] = []

    # Build root asset meshes (same as v0.1) and track mesh_id -> glTF mesh index
    mesh_id_to_gltf_idx: dict[str, int] = {}
    pre_count = len(gltf.meshes)
    _build_spec_meshes(
        gltf, composed.root_spec, blob_data, material_map, scene_nodes, yaml_dir=yaml_dir
    )
    for i, mesh_def in enumerate(composed.root_spec.meshes):
        mesh_id_to_gltf_idx[mesh_def.id] = pre_count + i

    # Build instance nodes
    for inst in composed.instances:
        if inst.mesh_id is not None:
            _build_local_mesh_instance(
                gltf,
                inst,
                mesh_id_to_gltf_idx,
                scene_nodes,
            )
        else:
            _build_instance(gltf, inst, blob_data, material_map, scene_nodes)

    gltf.scenes[0].nodes = scene_nodes

    # Set binary blob
    gltf.buffers = [pygltflib.Buffer(byteLength=len(blob_data))]
    gltf.set_binary_blob(bytes(blob_data))

    return gltf


def _build_instance(
    gltf: pygltflib.GLTF2,
    inst: ResolvedInstance,
    blob_data: bytearray,
    material_map: dict[str, int],
    scene_nodes: list[int],
) -> None:
    """Build an instance node with its transform and children."""
    # Create instance node with attach3 transform matrix (column-major for glTF)
    mat_col_major = inst.transform.T.flatten().tolist()

    instance_node_idx = len(gltf.nodes)
    gltf.nodes.append(
        pygltflib.Node(
            name=inst.id,
            matrix=mat_col_major,
        )
    )
    scene_nodes.append(instance_node_idx)

    # Build child nodes for the imported spec
    child_nodes: list[int] = []
    _build_spec_meshes(
        gltf,
        inst.source_spec,
        blob_data,
        material_map,
        child_nodes,
        name_prefix=f"{inst.id}.",
    )

    gltf.nodes[instance_node_idx].children = child_nodes if child_nodes else None


def _build_local_mesh_instance(
    gltf: pygltflib.GLTF2,
    inst: ResolvedInstance,
    mesh_id_to_gltf_idx: dict[str, int],
    scene_nodes: list[int],
) -> None:
    """Build a node for a local mesh instance referencing an already-built mesh."""
    gltf_mesh_idx = mesh_id_to_gltf_idx.get(inst.mesh_id)
    if gltf_mesh_idx is None:
        raise ExportError(f"Local mesh instance {inst.id!r}: mesh {inst.mesh_id!r} not found")

    mat_col_major = inst.transform.T.flatten().tolist()
    node_idx = len(gltf.nodes)
    gltf.nodes.append(
        pygltflib.Node(
            name=inst.id,
            mesh=gltf_mesh_idx,
            matrix=mat_col_major,
        )
    )
    scene_nodes.append(node_idx)


def _build_gltf(spec: RigySpec, *, yaml_dir: Path | None = None) -> pygltflib.GLTF2:
    """Build the complete glTF2 structure (v0.1 path)."""
    gltf = pygltflib.GLTF2(
        scene=0,
        scenes=[pygltflib.Scene(nodes=[])],
        nodes=[],
        meshes=[],
        accessors=[],
        bufferViews=[],
        buffers=[],
        materials=[],
        skins=[],
    )

    blob_data = bytearray()
    material_map: dict[str, int] = {}
    scene_nodes: list[int] = []

    _build_spec_meshes(gltf, spec, blob_data, material_map, scene_nodes, yaml_dir=yaml_dir)

    gltf.scenes[0].nodes = scene_nodes

    # Set binary blob
    gltf.buffers = [pygltflib.Buffer(byteLength=len(blob_data))]
    gltf.set_binary_blob(bytes(blob_data))

    return gltf


def _build_spec_meshes(
    gltf: pygltflib.GLTF2,
    spec: RigySpec,
    blob_data: bytearray,
    material_map: dict[str, int],
    scene_nodes: list[int],
    name_prefix: str = "",
    *,
    yaml_dir: Path | None = None,
) -> None:
    """Build mesh/bone/skin nodes for a spec and append to scene_nodes."""
    # Build binding lookup
    binding_map: dict[str, tuple] = {}  # mesh_id -> (binding, armature)
    for binding in spec.bindings:
        arm = next((a for a in spec.armatures if a.id == binding.armature_id), None)
        if arm:
            binding_map[binding.mesh_id] = (binding, arm)

    for mesh_def in spec.meshes:
        mesh_data, prim_ranges = tessellate_mesh(mesh_def, spec.tessellation_profile)

        if len(mesh_data.positions) == 0:
            continue

        # Collect materials
        for prim in mesh_def.primitives:
            if prim.material and prim.material not in material_map:
                mat_idx = len(gltf.materials)
                gltf.materials.append(
                    pygltflib.Material(
                        name=prim.material,
                        pbrMetallicRoughness=pygltflib.PbrMetallicRoughness(),
                    )
                )
                material_map[prim.material] = mat_idx

        # Write position data
        pos_offset = len(blob_data)
        pos_bytes = mesh_data.positions.astype(np.float32).tobytes()
        blob_data.extend(pos_bytes)

        pos_bv_idx = len(gltf.bufferViews)
        gltf.bufferViews.append(
            pygltflib.BufferView(
                buffer=0,
                byteOffset=pos_offset,
                byteLength=len(pos_bytes),
                target=pygltflib.ARRAY_BUFFER,
            )
        )

        pos_min = mesh_data.positions.min(axis=0).tolist()
        pos_max = mesh_data.positions.max(axis=0).tolist()
        pos_acc_idx = len(gltf.accessors)
        gltf.accessors.append(
            pygltflib.Accessor(
                bufferView=pos_bv_idx,
                byteOffset=0,
                componentType=pygltflib.FLOAT,
                count=len(mesh_data.positions),
                type=pygltflib.VEC3,
                max=pos_max,
                min=pos_min,
            )
        )

        # Write normal data
        norm_offset = len(blob_data)
        norm_bytes = mesh_data.normals.astype(np.float32).tobytes()
        blob_data.extend(norm_bytes)

        norm_bv_idx = len(gltf.bufferViews)
        gltf.bufferViews.append(
            pygltflib.BufferView(
                buffer=0,
                byteOffset=norm_offset,
                byteLength=len(norm_bytes),
                target=pygltflib.ARRAY_BUFFER,
            )
        )

        norm_acc_idx = len(gltf.accessors)
        gltf.accessors.append(
            pygltflib.Accessor(
                bufferView=norm_bv_idx,
                byteOffset=0,
                componentType=pygltflib.FLOAT,
                count=len(mesh_data.normals),
                type=pygltflib.VEC3,
            )
        )

        # Write index data
        idx_offset = len(blob_data)
        idx_bytes = mesh_data.indices.astype(np.uint32).tobytes()
        blob_data.extend(idx_bytes)

        idx_bv_idx = len(gltf.bufferViews)
        gltf.bufferViews.append(
            pygltflib.BufferView(
                buffer=0,
                byteOffset=idx_offset,
                byteLength=len(idx_bytes),
                target=pygltflib.ELEMENT_ARRAY_BUFFER,
            )
        )

        idx_acc_idx = len(gltf.accessors)
        gltf.accessors.append(
            pygltflib.Accessor(
                bufferView=idx_bv_idx,
                byteOffset=0,
                componentType=pygltflib.UNSIGNED_INT,
                count=len(mesh_data.indices),
                type=pygltflib.SCALAR,
            )
        )

        # Build glTF primitives (one per mesh for now, all merged)
        attributes = pygltflib.Attributes(
            POSITION=pos_acc_idx,
            NORMAL=norm_acc_idx,
        )

        # Skinning data
        skin_data: SkinData | None = None
        if mesh_def.id in binding_map:
            binding, armature = binding_map[mesh_def.id]
            skin_data = compute_skinning(
                binding,
                armature,
                prim_ranges,
                len(mesh_data.positions),
                positions=mesh_data.positions,
                yaml_dir=yaml_dir,
            )

            # Write joints
            joints_offset = len(blob_data)
            joints_bytes = skin_data.joints.astype(np.uint16).tobytes()
            blob_data.extend(joints_bytes)

            joints_bv_idx = len(gltf.bufferViews)
            gltf.bufferViews.append(
                pygltflib.BufferView(
                    buffer=0,
                    byteOffset=joints_offset,
                    byteLength=len(joints_bytes),
                    target=pygltflib.ARRAY_BUFFER,
                )
            )

            joints_acc_idx = len(gltf.accessors)
            gltf.accessors.append(
                pygltflib.Accessor(
                    bufferView=joints_bv_idx,
                    byteOffset=0,
                    componentType=pygltflib.UNSIGNED_SHORT,
                    count=len(skin_data.joints),
                    type=pygltflib.VEC4,
                )
            )

            # Write weights
            weights_offset = len(blob_data)
            weights_bytes = skin_data.weights.astype(np.float32).tobytes()
            blob_data.extend(weights_bytes)

            weights_bv_idx = len(gltf.bufferViews)
            gltf.bufferViews.append(
                pygltflib.BufferView(
                    buffer=0,
                    byteOffset=weights_offset,
                    byteLength=len(weights_bytes),
                    target=pygltflib.ARRAY_BUFFER,
                )
            )

            weights_acc_idx = len(gltf.accessors)
            gltf.accessors.append(
                pygltflib.Accessor(
                    bufferView=weights_bv_idx,
                    byteOffset=0,
                    componentType=pygltflib.FLOAT,
                    count=len(skin_data.weights),
                    type=pygltflib.VEC4,
                )
            )

            attributes.JOINTS_0 = joints_acc_idx
            attributes.WEIGHTS_0 = weights_acc_idx

        # Determine material for the first primitive (simple approach)
        mat_idx = None
        if mesh_def.primitives and mesh_def.primitives[0].material:
            mat_idx = material_map.get(mesh_def.primitives[0].material)

        gltf_prim = pygltflib.Primitive(
            attributes=attributes,
            indices=idx_acc_idx,
            material=mat_idx,
        )

        mesh_idx = len(gltf.meshes)
        mesh_name = name_prefix + (mesh_def.name or mesh_def.id)
        gltf.meshes.append(
            pygltflib.Mesh(
                name=mesh_name,
                primitives=[gltf_prim],
            )
        )

        # Create mesh node
        mesh_node_idx = len(gltf.nodes)
        gltf.nodes.append(
            pygltflib.Node(
                name=mesh_name,
                mesh=mesh_idx,
            )
        )
        scene_nodes.append(mesh_node_idx)

        # Build armature nodes and skin if we have skinning
        if skin_data is not None:
            binding, armature = binding_map[mesh_def.id]

            # Build parent lookup for relative transforms
            bone_head_map = {bone.id: bone.head for bone in armature.bones}
            bone_parent_map = {
                bone.id: bone.parent if bone.parent != "none" else None for bone in armature.bones
            }

            # Create bone nodes with parent-relative translations
            bone_node_indices: dict[str, int] = {}
            for bone in armature.bones:
                bone_node_idx = len(gltf.nodes)
                bone_node_indices[bone.id] = bone_node_idx

                parent_id = bone_parent_map[bone.id]
                if parent_id is not None and parent_id in bone_head_map:
                    # Child bone: translation relative to parent head
                    ph = bone_head_map[parent_id]
                    translation = [
                        float(bone.head[0] - ph[0]),
                        float(bone.head[1] - ph[1]),
                        float(bone.head[2] - ph[2]),
                    ]
                else:
                    # Root bone: absolute translation
                    translation = [
                        float(bone.head[0]),
                        float(bone.head[1]),
                        float(bone.head[2]),
                    ]

                gltf.nodes.append(
                    pygltflib.Node(
                        name=name_prefix + bone.id,
                        translation=translation,
                    )
                )

            # Set up parent-child relationships
            root_bone_nodes = []
            for bone in armature.bones:
                bone_idx = bone_node_indices[bone.id]
                if bone.parent == "none":
                    root_bone_nodes.append(bone_idx)
                else:
                    parent_idx = bone_node_indices.get(bone.parent)
                    if parent_idx is not None:
                        if gltf.nodes[parent_idx].children is None:
                            gltf.nodes[parent_idx].children = []
                        gltf.nodes[parent_idx].children.append(bone_idx)

            # Add root bone nodes to scene
            for rbn in root_bone_nodes:
                scene_nodes.append(rbn)

            # Write IBM data (glTF uses column-major matrices; numpy is row-major)
            ibm_offset = len(blob_data)
            ibm_col_major = np.ascontiguousarray(skin_data.inverse_bind_matrices.transpose(0, 2, 1))
            ibm_bytes = ibm_col_major.astype(np.float32).tobytes()
            blob_data.extend(ibm_bytes)

            ibm_bv_idx = len(gltf.bufferViews)
            gltf.bufferViews.append(
                pygltflib.BufferView(
                    buffer=0,
                    byteOffset=ibm_offset,
                    byteLength=len(ibm_bytes),
                )
            )

            ibm_acc_idx = len(gltf.accessors)
            gltf.accessors.append(
                pygltflib.Accessor(
                    bufferView=ibm_bv_idx,
                    byteOffset=0,
                    componentType=pygltflib.FLOAT,
                    count=len(skin_data.inverse_bind_matrices),
                    type=pygltflib.MAT4,
                )
            )

            # Create skin
            joint_node_list = [bone_node_indices[name] for name in skin_data.joint_names]
            skeleton_root = root_bone_nodes[0] if root_bone_nodes else None

            skin_idx = len(gltf.skins)
            gltf.skins.append(
                pygltflib.Skin(
                    name=name_prefix + (armature.name or armature.id),
                    joints=joint_node_list,
                    skeleton=skeleton_root,
                    inverseBindMatrices=ibm_acc_idx,
                )
            )

            # Assign skin to mesh node
            gltf.nodes[mesh_node_idx].skin = skin_idx
