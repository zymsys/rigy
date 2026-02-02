"""Tests for glTF/GLB export."""

import json
import struct

import yaml
import pygltflib

from rigy.exporter import export_gltf
from rigy.models import Material, RigySpec
from rigy.symmetry import expand_symmetry
from rigy.validation import validate


class TestExporter:
    def test_glb_magic_bytes(self, minimal_mesh_yaml, tmp_path):
        spec = RigySpec(**yaml.safe_load(minimal_mesh_yaml))
        validate(spec)
        out = tmp_path / "test.glb"
        export_gltf(spec, out)
        data = out.read_bytes()
        assert data[:4] == b"glTF"  # GLB magic

    def test_reloadable_by_pygltflib(self, minimal_mesh_yaml, tmp_path):
        spec = RigySpec(**yaml.safe_load(minimal_mesh_yaml))
        validate(spec)
        out = tmp_path / "test.glb"
        export_gltf(spec, out)
        gltf = pygltflib.GLTF2().load(str(out))
        assert len(gltf.meshes) == 1

    def test_mesh_nodes_present(self, minimal_mesh_yaml, tmp_path):
        spec = RigySpec(**yaml.safe_load(minimal_mesh_yaml))
        validate(spec)
        out = tmp_path / "test.glb"
        export_gltf(spec, out)
        gltf = pygltflib.GLTF2().load(str(out))
        assert any(n.mesh is not None for n in gltf.nodes)

    def test_skin_present_with_binding(self, full_humanoid_yaml, tmp_path):
        spec = RigySpec(**yaml.safe_load(full_humanoid_yaml))
        spec = expand_symmetry(spec)
        validate(spec)
        out = tmp_path / "test.glb"
        export_gltf(spec, out)
        gltf = pygltflib.GLTF2().load(str(out))
        assert len(gltf.skins) >= 1

    def test_bone_nodes_present(self, full_humanoid_yaml, tmp_path):
        spec = RigySpec(**yaml.safe_load(full_humanoid_yaml))
        spec = expand_symmetry(spec)
        validate(spec)
        out = tmp_path / "test.glb"
        export_gltf(spec, out)
        gltf = pygltflib.GLTF2().load(str(out))
        bone_names = {n.name for n in gltf.nodes if n.mesh is None}
        assert "root" in bone_names
        assert "spine" in bone_names

    def test_accessor_types_correct(self, minimal_mesh_yaml, tmp_path):
        spec = RigySpec(**yaml.safe_load(minimal_mesh_yaml))
        validate(spec)
        out = tmp_path / "test.glb"
        export_gltf(spec, out)
        gltf = pygltflib.GLTF2().load(str(out))
        # Position accessor should be VEC3/FLOAT
        pos_acc = gltf.accessors[0]
        assert pos_acc.type == "VEC3"
        assert pos_acc.componentType == pygltflib.FLOAT

    def test_material_names_preserved(self, full_humanoid_yaml, tmp_path):
        spec = RigySpec(**yaml.safe_load(full_humanoid_yaml))
        spec = expand_symmetry(spec)
        validate(spec)
        out = tmp_path / "test.glb"
        export_gltf(spec, out)
        gltf = pygltflib.GLTF2().load(str(out))
        mat_names = [m.name for m in gltf.materials]
        assert "skin" in mat_names

    def test_ibm_column_major_layout(self, full_humanoid_yaml, tmp_path):
        """glTF IBMs must be column-major: translation in elements 12,13,14."""
        import numpy as np

        spec = RigySpec(**yaml.safe_load(full_humanoid_yaml))
        spec = expand_symmetry(spec)
        validate(spec)
        out = tmp_path / "test.glb"
        export_gltf(spec, out)
        gltf = pygltflib.GLTF2().load(str(out))

        # Read IBM accessor
        ibm_acc = gltf.accessors[gltf.skins[0].inverseBindMatrices]
        ibm_bv = gltf.bufferViews[ibm_acc.bufferView]
        blob = gltf.binary_blob()
        ibm_data = np.frombuffer(
            blob[ibm_bv.byteOffset : ibm_bv.byteOffset + ibm_bv.byteLength],
            dtype=np.float32,
        ).reshape(-1, 16)

        for i, row in enumerate(ibm_data):
            # In column-major, indices 3, 7, 11 must be 0 (not translation)
            assert row[3] == 0.0, f"IBM[{i}] index 3 should be 0, got {row[3]}"
            assert row[7] == 0.0, f"IBM[{i}] index 7 should be 0, got {row[7]}"
            assert row[11] == 0.0, f"IBM[{i}] index 11 should be 0, got {row[11]}"
            # index 15 must be 1.0
            assert row[15] == 1.0, f"IBM[{i}] index 15 should be 1, got {row[15]}"

    def test_bone_translations_parent_relative(self, full_humanoid_yaml, tmp_path):
        """Bone nodes must use parent-relative translations, not absolute."""
        spec = RigySpec(**yaml.safe_load(full_humanoid_yaml))
        spec = expand_symmetry(spec)
        validate(spec)
        out = tmp_path / "test.glb"
        export_gltf(spec, out)
        gltf = pygltflib.GLTF2().load(str(out))

        # Find spine node — parent is root at (0,0.90,0), spine head at (0,0.95,0)
        # so spine's translation should be (0, 0.05, 0), not (0, 0.95, 0)
        node_map = {n.name: n for n in gltf.nodes}
        spine = node_map["spine"]
        assert abs(spine.translation[1] - 0.05) < 0.01, (
            f"Spine translation should be parent-relative (0,0.05,0), got {spine.translation}"
        )

    def test_deterministic_output(self, minimal_mesh_yaml, tmp_path):
        spec = RigySpec(**yaml.safe_load(minimal_mesh_yaml))
        validate(spec)
        out1 = tmp_path / "test1.glb"
        out2 = tmp_path / "test2.glb"
        export_gltf(spec, out1)
        export_gltf(spec, out2)
        assert out1.read_bytes() == out2.read_bytes()


class TestUvExport:
    def test_texcoord_0_present(self, tmp_path):
        from rigy.models import UvSetEntry

        spec = RigySpec(
            version="0.8",
            meshes=[
                {
                    "id": "m1",
                    "primitives": [
                        {"type": "box", "id": "p1", "dimensions": {"x": 1, "y": 1, "z": 1}}
                    ],
                    "uv_sets": {"uv0": UvSetEntry(generator="planar_xy@1")},
                }
            ],
        )
        validate(spec)
        out = tmp_path / "test.glb"
        export_gltf(spec, out)
        gltf = pygltflib.GLTF2().load(str(out))
        prim = gltf.meshes[0].primitives[0]
        assert prim.attributes.TEXCOORD_0 is not None
        acc = gltf.accessors[prim.attributes.TEXCOORD_0]
        assert acc.type == "VEC2"
        assert acc.componentType == pygltflib.FLOAT
        assert acc.count == 24  # box has 24 verts

    def test_multiple_texcoords(self, tmp_path):
        from rigy.models import UvSetEntry

        spec = RigySpec(
            version="0.8",
            meshes=[
                {
                    "id": "m1",
                    "primitives": [
                        {"type": "box", "id": "p1", "dimensions": {"x": 1, "y": 1, "z": 1}}
                    ],
                    "uv_sets": {
                        "uv0": UvSetEntry(generator="planar_xy@1"),
                        "uv1": UvSetEntry(generator="box_project@1"),
                    },
                }
            ],
        )
        validate(spec)
        out = tmp_path / "test.glb"
        export_gltf(spec, out)
        gltf = pygltflib.GLTF2().load(str(out))
        prim = gltf.meshes[0].primitives[0]
        assert prim.attributes.TEXCOORD_0 is not None
        assert prim.attributes.TEXCOORD_1 is not None

    def test_no_uv_sets_no_texcoord(self, minimal_mesh_yaml, tmp_path):
        spec = RigySpec(**yaml.safe_load(minimal_mesh_yaml))
        validate(spec)
        out = tmp_path / "test.glb"
        export_gltf(spec, out)
        gltf = pygltflib.GLTF2().load(str(out))
        prim = gltf.meshes[0].primitives[0]
        assert prim.attributes.TEXCOORD_0 is None


def _make_material_spec(**overrides):
    base = {
        "version": "0.6",
        "units": "meters",
        "coordinate_system": {"up": "Y", "forward": "-Z", "handedness": "right"},
        "tessellation_profile": "v0_1_default",
        "materials": {"red": Material(base_color=[0.8, 0.2, 0.1, 1.0])},
        "meshes": [
            {
                "id": "m1",
                "primitives": [
                    {
                        "type": "box",
                        "id": "p1",
                        "dimensions": {"x": 1, "y": 1, "z": 1},
                        "material": "red",
                    }
                ],
            }
        ],
    }
    base.update(overrides)
    return RigySpec(**base)


def _extract_glb_json(glb_path) -> dict:
    """Extract the JSON chunk from a GLB file."""
    data = glb_path.read_bytes()
    json_chunk_length = struct.unpack_from("<I", data, 12)[0]
    json_bytes = data[20 : 20 + json_chunk_length]
    return json.loads(json_bytes.decode("utf-8"))


class TestMaterialExport:
    def test_material_base_color_exported(self, tmp_path):
        spec = _make_material_spec()
        validate(spec)
        out = tmp_path / "test.glb"
        export_gltf(spec, out)
        gltf = pygltflib.GLTF2().load(str(out))
        assert len(gltf.materials) == 1
        mat = gltf.materials[0]
        assert mat.name == "red"
        assert mat.pbrMetallicRoughness.metallicFactor == 0.0
        assert mat.pbrMetallicRoughness.roughnessFactor == 1.0
        bcf = mat.pbrMetallicRoughness.baseColorFactor
        assert len(bcf) == 4
        assert abs(bcf[0] - 0.8) < 1e-5
        assert abs(bcf[1] - 0.2) < 1e-5
        assert abs(bcf[2] - 0.1) < 1e-5
        assert abs(bcf[3] - 1.0) < 1e-5

    def test_alpha_opaque_mode(self, tmp_path):
        spec = _make_material_spec()
        validate(spec)
        out = tmp_path / "test.glb"
        export_gltf(spec, out)
        gltf = pygltflib.GLTF2().load(str(out))
        assert gltf.materials[0].alphaMode == "OPAQUE"

    def test_alpha_blend_mode(self, tmp_path):
        spec = _make_material_spec(
            materials={"glass": Material(base_color=[0.7, 0.8, 0.9, 0.3])},
            meshes=[
                {
                    "id": "m1",
                    "primitives": [
                        {
                            "type": "box",
                            "id": "p1",
                            "dimensions": {"x": 1, "y": 1, "z": 1},
                            "material": "glass",
                        }
                    ],
                }
            ],
        )
        validate(spec)
        out = tmp_path / "test.glb"
        export_gltf(spec, out)
        gltf = pygltflib.GLTF2().load(str(out))
        assert gltf.materials[0].alphaMode == "BLEND"

    def test_deterministic_base_color_serialization(self, tmp_path):
        spec = _make_material_spec()
        validate(spec)
        out = tmp_path / "test.glb"
        export_gltf(spec, out)
        glb_json = _extract_glb_json(out)
        mat = glb_json["materials"][0]
        bcf = mat["pbrMetallicRoughness"]["baseColorFactor"]
        # Check 6 decimal places in the raw JSON text
        raw = out.read_bytes()
        json_len = struct.unpack_from("<I", raw, 12)[0]
        json_str = raw[20 : 20 + json_len].decode("utf-8")
        assert '"baseColorFactor":[0.800000,0.200000,0.100000,1.000000]' in json_str

    def test_material_determinism(self, tmp_path):
        spec = _make_material_spec()
        validate(spec)
        out1 = tmp_path / "test1.glb"
        out2 = tmp_path / "test2.glb"
        export_gltf(spec, out1)
        export_gltf(spec, out2)
        assert out1.read_bytes() == out2.read_bytes()

    def test_no_material_no_gltf_material(self, tmp_path):
        spec = RigySpec(
            version="0.6",
            meshes=[
                {
                    "id": "m1",
                    "primitives": [
                        {"type": "box", "id": "p1", "dimensions": {"x": 1, "y": 1, "z": 1}}
                    ],
                }
            ],
        )
        validate(spec)
        out = tmp_path / "test.glb"
        export_gltf(spec, out)
        gltf = pygltflib.GLTF2().load(str(out))
        assert len(gltf.materials) == 0
