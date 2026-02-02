"""End-to-end tests for the Rigs pipeline."""

from pathlib import Path


from rigy.rigs_composition import compose_rigs
from rigy.rigs_exporter import export_rigs_gltf
from rigy.rigs_parser import parse_rigs
from rigy.rigs_validation import validate_rigs

FIXTURES = Path(__file__).parent / "rigs_fixtures"


class TestE2EPipeline:
    def test_simple_scene_export(self, tmp_path):
        """Full pipeline: parse -> validate -> compose -> export."""
        asset = parse_rigs(FIXTURES / "simple_scene.rigs.yaml")
        validate_rigs(asset)
        composed = compose_rigs(asset)
        output = tmp_path / "simple.glb"
        export_rigs_gltf(composed, output)

        assert output.exists()
        assert output.stat().st_size > 0

        # Verify GLB magic bytes
        data = output.read_bytes()
        assert data[:4] == b"glTF"

    def test_nested_scene_export(self, tmp_path):
        asset = parse_rigs(FIXTURES / "nested_scene.rigs.yaml")
        validate_rigs(asset)
        composed = compose_rigs(asset)
        output = tmp_path / "nested.glb"
        export_rigs_gltf(composed, output)

        assert output.exists()
        assert output.stat().st_size > 0

    def test_rotated_scene_export(self, tmp_path):
        asset = parse_rigs(FIXTURES / "rotated_scene.rigs.yaml")
        validate_rigs(asset)
        composed = compose_rigs(asset)
        output = tmp_path / "rotated.glb"
        export_rigs_gltf(composed, output)

        assert output.exists()
        assert output.stat().st_size > 0


class TestDeterminism:
    def test_byte_identical_output(self, tmp_path):
        """Same input must produce byte-identical GLB."""
        out1 = tmp_path / "run1.glb"
        out2 = tmp_path / "run2.glb"

        for output in [out1, out2]:
            asset = parse_rigs(FIXTURES / "simple_scene.rigs.yaml")
            validate_rigs(asset)
            composed = compose_rigs(asset)
            export_rigs_gltf(composed, output)

        assert out1.read_bytes() == out2.read_bytes()


class TestNodeNames:
    def test_node_names_match_ids(self, tmp_path):
        """Instance IDs must appear as glTF node names."""
        import json
        import struct

        asset = parse_rigs(FIXTURES / "nested_scene.rigs.yaml")
        validate_rigs(asset)
        composed = compose_rigs(asset)
        output = tmp_path / "test.glb"
        export_rigs_gltf(composed, output)

        # Parse GLB to get JSON chunk
        data = output.read_bytes()
        json_len = struct.unpack_from("<I", data, 12)[0]
        json_str = data[20 : 20 + json_len].decode("utf-8").rstrip()
        gltf_json = json.loads(json_str)

        node_names = [n.get("name", "") for n in gltf_json["nodes"]]

        # Root node named "scene"
        assert "scene" in node_names
        # Instance IDs
        assert "cube1" in node_names
        assert "cube2" in node_names
