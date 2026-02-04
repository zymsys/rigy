"""glTF/GLB assembly via pygltflib."""

from __future__ import annotations

import re
import struct
from pathlib import Path

import numpy as np
import pygltflib

from rigy.composition import ComposedAsset, ResolvedInstance
from rigy.dqs import evaluate_pose
from rigy.errors import ExportError
from rigy.models import Mesh, Pose, Primitive, RigySpec
from rigy.skinning import SkinData, compute_skinning
from rigy.tessellation import MeshData, tessellate_mesh, tessellate_primitive
from rigy.uv import generate_uv_sets
from rigy.warning_policy import WarningPolicy


def _spec_version(spec: RigySpec) -> tuple[int, int]:
    """Parse spec version string to (major, minor) tuple."""
    parts = spec.version.split(".")
    if len(parts) == 2:
        try:
            return (int(parts[0]), int(parts[1]))
        except ValueError:
            pass
    return (0, 1)


def _resolve_material(prim: Primitive, mesh: Mesh) -> str | None:
    """Resolve material for a primitive: primitive.material ?? mesh.material."""
    return prim.material or mesh.material


def export_gltf(
    spec_or_composed: RigySpec | ComposedAsset,
    output_path: Path,
    *,
    yaml_dir: Path | None = None,
    warning_policy: WarningPolicy | None = None,
) -> None:
    """Export a validated Rigy spec or composed asset to a GLB file.

    Pipeline: tessellate -> skin -> build glTF scene -> write GLB.
    """
    try:
        if isinstance(spec_or_composed, ComposedAsset):
            gltf = _build_gltf_composed(
                spec_or_composed, yaml_dir=yaml_dir, warning_policy=warning_policy
            )
        else:
            gltf = _build_gltf(spec_or_composed, yaml_dir=yaml_dir, warning_policy=warning_policy)
        _save_glb_deterministic(gltf, output_path)
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
    warning_policy: WarningPolicy | None = None,
) -> None:
    """Export a baked (pose-evaluated) GLB with skinning removed.

    Tessellates meshes, evaluates the pose via DQS or LBS, writes deformed
    geometry without JOINTS_0/WEIGHTS_0/Skin/IBM data.
    """
    try:
        gltf = _build_gltf_baked(spec, pose, yaml_dir=yaml_dir, warning_policy=warning_policy)
        _save_glb_deterministic(gltf, output_path)
    except Exception as e:
        if isinstance(e, ExportError):
            raise
        raise ExportError(f"Failed to export baked glTF: {e}") from e


def _build_material(mat_id: str, spec: RigySpec) -> pygltflib.Material:
    """Build a glTF Material from a Rigy material definition."""
    mat = spec.materials[mat_id]
    base_color = [float(np.float32(c)) for c in mat.base_color]
    alpha = base_color[3]
    return pygltflib.Material(
        name=mat_id,
        pbrMetallicRoughness=pygltflib.PbrMetallicRoughness(
            baseColorFactor=base_color,
            metallicFactor=0.0,
            roughnessFactor=1.0,
        ),
        alphaMode="OPAQUE" if alpha == 1.0 else "BLEND",
        doubleSided=False,
    )


def _save_glb_deterministic(gltf: pygltflib.GLTF2, output_path: Path) -> None:
    """Save GLB with deterministic baseColorFactor serialization (6 decimal places)."""
    glb_bytes = b"".join(gltf.save_to_bytes())

    # Parse GLB structure: 12-byte header + chunks
    _magic, _version, _length = struct.unpack_from("<III", glb_bytes, 0)
    json_chunk_length = struct.unpack_from("<I", glb_bytes, 12)[0]
    json_chunk_type = struct.unpack_from("<I", glb_bytes, 16)[0]
    assert json_chunk_type == 0x4E4F534A  # "JSON"

    json_bytes = glb_bytes[20 : 20 + json_chunk_length]
    json_str = json_bytes.decode("utf-8").rstrip("\x20")  # strip padding spaces

    # Replace baseColorFactor arrays with 6-decimal formatting
    def _format_base_color(m: re.Match) -> str:
        # Parse the array values
        inner = m.group(1)
        values = [float(v) for v in inner.split(",")]
        formatted = ",".join(f"{v:.6f}" for v in values)
        return f'"baseColorFactor":[{formatted}]'

    json_str = re.sub(
        r'"baseColorFactor":\[([^\]]+)\]',
        _format_base_color,
        json_str,
    )

    # Re-encode and pad to 4-byte alignment
    new_json_bytes = json_str.encode("utf-8")
    padding_needed = (4 - len(new_json_bytes) % 4) % 4
    new_json_bytes += b"\x20" * padding_needed  # space padding for JSON chunk

    # Rebuild GLB
    rest_of_glb = glb_bytes[20 + json_chunk_length :]  # BIN chunk(s)
    total_length = 12 + 8 + len(new_json_bytes) + len(rest_of_glb)

    out = bytearray()
    out += struct.pack("<III", 0x46546C67, 2, total_length)  # GLB header
    out += struct.pack("<II", len(new_json_bytes), 0x4E4F534A)  # JSON chunk header
    out += new_json_bytes
    out += rest_of_glb

    output_path.write_bytes(bytes(out))


def _build_gltf_baked(
    spec: RigySpec,
    pose: Pose,
    *,
    yaml_dir: Path | None = None,
    warning_policy: WarningPolicy | None = None,
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
                if prim.material in spec.materials:
                    gltf.materials.append(_build_material(prim.material, spec))
                else:
                    gltf.materials.append(
                        pygltflib.Material(
                            name=prim.material,
                            pbrMetallicRoughness=pygltflib.PbrMetallicRoughness(),
                        )
                    )
                material_map[prim.material] = mat_idx

        # Generate UV sets on rest-pose positions (before deformation)
        uv_arrays_baked = generate_uv_sets(mesh_def, mesh_data.positions, prim_ranges)

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
                warning_policy=warning_policy,
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

        # Write UV buffers for baked path
        uv_acc_indices_baked: list[int] = []
        for uv_arr in uv_arrays_baked:
            uv_offset = len(blob_data)
            uv_bytes = uv_arr.astype(np.float32).tobytes()
            blob_data.extend(uv_bytes)

            uv_bv_idx = len(gltf.bufferViews)
            gltf.bufferViews.append(
                pygltflib.BufferView(
                    buffer=0,
                    byteOffset=uv_offset,
                    byteLength=len(uv_bytes),
                    target=pygltflib.ARRAY_BUFFER,
                )
            )

            uv_acc_idx = len(gltf.accessors)
            gltf.accessors.append(
                pygltflib.Accessor(
                    bufferView=uv_bv_idx,
                    byteOffset=0,
                    componentType=pygltflib.FLOAT,
                    count=len(uv_arr),
                    type=pygltflib.VEC2,
                )
            )
            uv_acc_indices_baked.append(uv_acc_idx)

        # No JOINTS_0/WEIGHTS_0 — baked export omits skin data
        attributes = pygltflib.Attributes(
            POSITION=pos_acc_idx,
            NORMAL=norm_acc_idx,
        )

        # Set TEXCOORD_N attributes for baked path
        for i, acc_idx in enumerate(uv_acc_indices_baked):
            setattr(attributes, f"TEXCOORD_{i}", acc_idx)

        mat_idx = None
        if mesh_def.primitives and mesh_def.primitives[0].material:
            mat_idx = material_map.get(mesh_def.primitives[0].material)

        gltf_prim = pygltflib.Primitive(
            attributes=attributes,
            indices=idx_acc_idx,
            material=mat_idx,
        )

        # Export rigy_tags as glTF extras (baked path)
        all_tags_baked: list[str] = []
        seen_tags_baked: set[str] = set()
        for prim in mesh_def.primitives:
            if prim.tags:
                for tag in prim.tags:
                    if tag not in seen_tags_baked:
                        all_tags_baked.append(tag)
                        seen_tags_baked.add(tag)
        if all_tags_baked:
            gltf_prim.extras = {"rigy_tags": all_tags_baked}

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
    composed: ComposedAsset,
    *,
    yaml_dir: Path | None = None,
    warning_policy: WarningPolicy | None = None,
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
        gltf,
        composed.root_spec,
        blob_data,
        material_map,
        scene_nodes,
        yaml_dir=yaml_dir,
        warning_policy=warning_policy,
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


def _build_gltf(
    spec: RigySpec,
    *,
    yaml_dir: Path | None = None,
    warning_policy: WarningPolicy | None = None,
) -> pygltflib.GLTF2:
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

    _build_spec_meshes(
        gltf,
        spec,
        blob_data,
        material_map,
        scene_nodes,
        yaml_dir=yaml_dir,
        warning_policy=warning_policy,
    )

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
    warning_policy: WarningPolicy | None = None,
) -> None:
    """Build mesh/bone/skin nodes for a spec and append to scene_nodes."""
    version = _spec_version(spec)
    if version >= (0, 12):
        _build_spec_meshes_v012(
            gltf,
            spec,
            blob_data,
            material_map,
            scene_nodes,
            name_prefix=name_prefix,
            yaml_dir=yaml_dir,
            warning_policy=warning_policy,
        )
        return

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
        _collect_materials(gltf, spec, mesh_def, material_map)

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

        # Generate UV sets on rest-pose positions
        uv_arrays = generate_uv_sets(mesh_def, mesh_data.positions, prim_ranges)
        uv_acc_indices: list[int] = []
        for uv_arr in uv_arrays:
            uv_offset = len(blob_data)
            uv_bytes = uv_arr.astype(np.float32).tobytes()
            blob_data.extend(uv_bytes)

            uv_bv_idx = len(gltf.bufferViews)
            gltf.bufferViews.append(
                pygltflib.BufferView(
                    buffer=0,
                    byteOffset=uv_offset,
                    byteLength=len(uv_bytes),
                    target=pygltflib.ARRAY_BUFFER,
                )
            )

            uv_acc_idx = len(gltf.accessors)
            gltf.accessors.append(
                pygltflib.Accessor(
                    bufferView=uv_bv_idx,
                    byteOffset=0,
                    componentType=pygltflib.FLOAT,
                    count=len(uv_arr),
                    type=pygltflib.VEC2,
                )
            )
            uv_acc_indices.append(uv_acc_idx)

        # Build glTF primitives (one per mesh for now, all merged)
        attributes = pygltflib.Attributes(
            POSITION=pos_acc_idx,
            NORMAL=norm_acc_idx,
        )

        # Set TEXCOORD_N attributes
        for i, acc_idx in enumerate(uv_acc_indices):
            setattr(attributes, f"TEXCOORD_{i}", acc_idx)

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
                warning_policy=warning_policy,
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

        # Export rigy_tags as glTF extras
        all_tags: list[str] = []
        seen_tags: set[str] = set()
        for prim in mesh_def.primitives:
            if prim.tags:
                for tag in prim.tags:
                    if tag not in seen_tags:
                        all_tags.append(tag)
                        seen_tags.add(tag)
        if all_tags:
            gltf_prim.extras = {"rigy_tags": all_tags}

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


def _collect_materials(
    gltf: pygltflib.GLTF2,
    spec: RigySpec,
    mesh_def: Mesh,
    material_map: dict[str, int],
) -> None:
    """Collect and register materials for a mesh (both mesh-level and primitive-level)."""
    # Mesh-level material (v0.12+)
    if mesh_def.material and mesh_def.material not in material_map:
        _register_material(gltf, spec, mesh_def.material, material_map)

    # Primitive-level materials
    for prim in mesh_def.primitives:
        if prim.material and prim.material not in material_map:
            _register_material(gltf, spec, prim.material, material_map)


def _register_material(
    gltf: pygltflib.GLTF2,
    spec: RigySpec,
    mat_id: str,
    material_map: dict[str, int],
) -> None:
    """Register a single material in the glTF and material_map."""
    mat_idx = len(gltf.materials)
    if mat_id in spec.materials:
        gltf.materials.append(_build_material(mat_id, spec))
    else:
        gltf.materials.append(
            pygltflib.Material(
                name=mat_id,
                pbrMetallicRoughness=pygltflib.PbrMetallicRoughness(),
            )
        )
    material_map[mat_id] = mat_idx


def _write_buffer_view_and_accessor(
    gltf: pygltflib.GLTF2,
    blob_data: bytearray,
    data_array: np.ndarray,
    component_type: int,
    accessor_type: str,
    target: int | None = None,
    *,
    include_min_max: bool = False,
) -> int:
    """Write a buffer view and accessor, returning the accessor index."""
    offset = len(blob_data)
    data_bytes = data_array.tobytes()
    blob_data.extend(data_bytes)

    bv_idx = len(gltf.bufferViews)
    bv = pygltflib.BufferView(
        buffer=0,
        byteOffset=offset,
        byteLength=len(data_bytes),
    )
    if target is not None:
        bv.target = target
    gltf.bufferViews.append(bv)

    acc_kwargs: dict = {
        "bufferView": bv_idx,
        "byteOffset": 0,
        "componentType": component_type,
        "count": len(data_array),
        "type": accessor_type,
    }
    if include_min_max:
        acc_kwargs["min"] = data_array.min(axis=0).tolist()
        acc_kwargs["max"] = data_array.max(axis=0).tolist()

    acc_idx = len(gltf.accessors)
    gltf.accessors.append(pygltflib.Accessor(**acc_kwargs))
    return acc_idx


def _build_spec_meshes_v012(
    gltf: pygltflib.GLTF2,
    spec: RigySpec,
    blob_data: bytearray,
    material_map: dict[str, int],
    scene_nodes: list[int],
    name_prefix: str = "",
    *,
    yaml_dir: Path | None = None,
    warning_policy: WarningPolicy | None = None,
) -> None:
    """Build mesh/bone/skin nodes for a v0.12+ spec — one glTF primitive per Rigy primitive."""
    # Build binding lookup
    binding_map: dict[str, tuple] = {}  # mesh_id -> (binding, armature)
    for binding in spec.bindings:
        arm = next((a for a in spec.armatures if a.id == binding.armature_id), None)
        if arm:
            binding_map[binding.mesh_id] = (binding, arm)

    for mesh_def in spec.meshes:
        # Tessellate each primitive individually
        per_prim_data: list[tuple[Primitive, MeshData]] = []
        for prim in mesh_def.primitives:
            md = tessellate_primitive(prim, spec.tessellation_profile)
            per_prim_data.append((prim, md))

        if not per_prim_data:
            continue

        # Also compute merged data + prim_ranges for skinning and UV
        mesh_data, prim_ranges = tessellate_mesh(mesh_def, spec.tessellation_profile)
        if len(mesh_data.positions) == 0:
            continue

        # Collect materials (mesh-level + primitive-level)
        _collect_materials(gltf, spec, mesh_def, material_map)

        # Generate UV sets on merged positions
        uv_arrays = generate_uv_sets(mesh_def, mesh_data.positions, prim_ranges)

        # Compute skinning on merged data (if bound)
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
                warning_policy=warning_policy,
            )

        # Build one glTF primitive per Rigy primitive
        gltf_prims: list[pygltflib.Primitive] = []
        for prim, prim_md in per_prim_data:
            v_start, v_end = prim_ranges[prim.id]

            # Position accessor (per-primitive)
            pos_f32 = prim_md.positions.astype(np.float32)
            pos_acc_idx = _write_buffer_view_and_accessor(
                gltf,
                blob_data,
                pos_f32,
                pygltflib.FLOAT,
                pygltflib.VEC3,
                pygltflib.ARRAY_BUFFER,
                include_min_max=True,
            )

            # Normal accessor (per-primitive)
            norm_f32 = prim_md.normals.astype(np.float32)
            norm_acc_idx = _write_buffer_view_and_accessor(
                gltf,
                blob_data,
                norm_f32,
                pygltflib.FLOAT,
                pygltflib.VEC3,
                pygltflib.ARRAY_BUFFER,
            )

            # Index accessor (per-primitive, 0-based indices)
            idx_u32 = prim_md.indices.astype(np.uint32)
            idx_acc_idx = _write_buffer_view_and_accessor(
                gltf,
                blob_data,
                idx_u32,
                pygltflib.UNSIGNED_INT,
                pygltflib.SCALAR,
                pygltflib.ELEMENT_ARRAY_BUFFER,
            )

            attributes = pygltflib.Attributes(
                POSITION=pos_acc_idx,
                NORMAL=norm_acc_idx,
            )

            # UV accessors (slice from merged UV arrays)
            for uv_idx, uv_arr in enumerate(uv_arrays):
                uv_slice = uv_arr[v_start:v_end].astype(np.float32)
                uv_acc_idx = _write_buffer_view_and_accessor(
                    gltf,
                    blob_data,
                    uv_slice,
                    pygltflib.FLOAT,
                    pygltflib.VEC2,
                    pygltflib.ARRAY_BUFFER,
                )
                setattr(attributes, f"TEXCOORD_{uv_idx}", uv_acc_idx)

            # Skinning data (slice from merged)
            if skin_data is not None:
                joints_slice = skin_data.joints[v_start:v_end].astype(np.uint16)
                joints_acc_idx = _write_buffer_view_and_accessor(
                    gltf,
                    blob_data,
                    joints_slice,
                    pygltflib.UNSIGNED_SHORT,
                    pygltflib.VEC4,
                    pygltflib.ARRAY_BUFFER,
                )
                weights_slice = skin_data.weights[v_start:v_end].astype(np.float32)
                weights_acc_idx = _write_buffer_view_and_accessor(
                    gltf,
                    blob_data,
                    weights_slice,
                    pygltflib.FLOAT,
                    pygltflib.VEC4,
                    pygltflib.ARRAY_BUFFER,
                )
                attributes.JOINTS_0 = joints_acc_idx
                attributes.WEIGHTS_0 = weights_acc_idx

            # Resolve material: primitive.material ?? mesh.material
            resolved_mat = _resolve_material(prim, mesh_def)
            mat_idx = material_map.get(resolved_mat) if resolved_mat else None

            gltf_prim = pygltflib.Primitive(
                attributes=attributes,
                indices=idx_acc_idx,
                material=mat_idx,
            )

            # extras: rigy_id + rigy_tags
            extras: dict = {"rigy_id": prim.id}
            if prim.tags:
                extras["rigy_tags"] = list(prim.tags)
            gltf_prim.extras = extras

            gltf_prims.append(gltf_prim)

        # Create glTF mesh with all primitives
        mesh_idx = len(gltf.meshes)
        mesh_name = name_prefix + (mesh_def.name or mesh_def.id)
        gltf.meshes.append(pygltflib.Mesh(name=mesh_name, primitives=gltf_prims))

        # Create mesh node
        mesh_node_idx = len(gltf.nodes)
        gltf.nodes.append(pygltflib.Node(name=mesh_name, mesh=mesh_idx))
        scene_nodes.append(mesh_node_idx)

        # Build armature nodes and skin (same as pre-0.12)
        if skin_data is not None:
            binding, armature = binding_map[mesh_def.id]

            bone_head_map = {bone.id: bone.head for bone in armature.bones}
            bone_parent_map = {
                bone.id: bone.parent if bone.parent != "none" else None for bone in armature.bones
            }

            bone_node_indices: dict[str, int] = {}
            for bone in armature.bones:
                bone_node_idx = len(gltf.nodes)
                bone_node_indices[bone.id] = bone_node_idx

                parent_id = bone_parent_map[bone.id]
                if parent_id is not None and parent_id in bone_head_map:
                    ph = bone_head_map[parent_id]
                    translation = [
                        float(bone.head[0] - ph[0]),
                        float(bone.head[1] - ph[1]),
                        float(bone.head[2] - ph[2]),
                    ]
                else:
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

            gltf.nodes[mesh_node_idx].skin = skin_idx
