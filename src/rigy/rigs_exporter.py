"""glTF/GLB export for composed Rigs scenes."""

from __future__ import annotations

from pathlib import Path

import pygltflib

from rigy.errors import ExportError
from rigy.exporter import _build_spec_meshes, _save_glb_deterministic
from rigy.rigs_composition import ComposedRigsScene, RigsInstance


def export_rigs_gltf(composed: ComposedRigsScene, output_path: Path) -> None:
    """Export a composed Rigs scene to a GLB file.

    Each unique import alias is compiled once (tessellate + skin + materials).
    Instances sharing the same alias share the same glTF mesh index.

    Args:
        composed: Fully composed scene with world transforms.
        output_path: Output .glb path.
    """
    try:
        gltf = _build_rigs_gltf(composed)
        _save_glb_deterministic(gltf, output_path)
    except Exception as e:
        if isinstance(e, ExportError):
            raise
        raise ExportError(f"Failed to export Rigs glTF: {e}") from e


def _build_rigs_gltf(composed: ComposedRigsScene) -> pygltflib.GLTF2:
    """Build the glTF2 structure for a Rigs scene."""
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

    # Build meshes for each unique asset alias, tracking which glTF mesh indices
    # correspond to each alias
    alias_mesh_indices: dict[str, list[int]] = {}

    # Collect all unique aliases we need to compile
    needed_aliases: dict[str, object] = {}  # alias -> ResolvedAsset
    needed_aliases[composed.root_alias] = composed.root_asset
    _collect_aliases(composed.instances, needed_aliases)

    for alias, resolved_asset in needed_aliases.items():
        pre_count = len(gltf.meshes)
        dummy_nodes: list[int] = []
        _build_spec_meshes(
            gltf,
            resolved_asset.spec,
            blob_data,
            material_map,
            dummy_nodes,
        )
        post_count = len(gltf.meshes)
        alias_mesh_indices[alias] = list(range(pre_count, post_count))

    # Build scene node tree
    scene_nodes: list[int] = []

    # Root node: identity transform, references root asset meshes
    root_node_idx = len(gltf.nodes)
    gltf.nodes.append(pygltflib.Node(name="scene"))
    scene_nodes.append(root_node_idx)

    root_children: list[int] = []

    # Add root asset mesh nodes as children of root
    for mesh_idx in alias_mesh_indices.get(composed.root_alias, []):
        mesh_node_idx = len(gltf.nodes)
        gltf.nodes.append(
            pygltflib.Node(
                name=gltf.meshes[mesh_idx].name,
                mesh=mesh_idx,
            )
        )
        root_children.append(mesh_node_idx)

    # Add instance nodes
    for inst in composed.instances:
        inst_node_idx = _build_instance_node(gltf, inst, alias_mesh_indices)
        root_children.append(inst_node_idx)

    gltf.nodes[root_node_idx].children = root_children if root_children else None

    gltf.scenes[0].nodes = scene_nodes

    # Finalize binary blob
    gltf.buffers = [pygltflib.Buffer(byteLength=len(blob_data))]
    gltf.set_binary_blob(bytes(blob_data))

    return gltf


def _build_instance_node(
    gltf: pygltflib.GLTF2,
    inst: RigsInstance,
    alias_mesh_indices: dict[str, list[int]],
) -> int:
    """Build a glTF node for a Rigs instance, returning its node index."""
    # Use world_transform as the node matrix (column-major for glTF)
    mat_col_major = inst.world_transform.T.flatten().tolist()

    node_idx = len(gltf.nodes)
    gltf.nodes.append(
        pygltflib.Node(
            name=inst.id,
            matrix=mat_col_major,
        )
    )

    children: list[int] = []

    # Add mesh nodes for this instance's asset
    for mesh_idx in alias_mesh_indices.get(inst.asset_alias, []):
        mesh_node_idx = len(gltf.nodes)
        gltf.nodes.append(
            pygltflib.Node(
                name=f"{inst.id}.{gltf.meshes[mesh_idx].name}",
                mesh=mesh_idx,
            )
        )
        children.append(mesh_node_idx)

    # Add child instance nodes
    for child_inst in inst.children:
        child_node_idx = _build_instance_node(gltf, child_inst, alias_mesh_indices)
        children.append(child_node_idx)

    gltf.nodes[node_idx].children = children if children else None

    return node_idx


def _collect_aliases(instances: list[RigsInstance], out: dict) -> None:
    """Recursively collect all unique asset aliases."""
    for inst in instances:
        if inst.asset_alias not in out:
            out[inst.asset_alias] = inst.resolved_asset
        _collect_aliases(inst.children, out)
