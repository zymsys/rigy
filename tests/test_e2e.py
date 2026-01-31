"""End-to-end integration tests."""

from pathlib import Path

import pygltflib

from rigy.exporter import export_gltf
from rigy.parser import parse_yaml
from rigy.symmetry import expand_symmetry
from rigy.validation import validate


def _compile(yaml_str: str, output_path: Path) -> pygltflib.GLTF2:
    """Full compile pipeline: parse -> expand -> validate -> export -> reload."""
    spec = parse_yaml(yaml_str)
    spec = expand_symmetry(spec)
    validate(spec)
    export_gltf(spec, output_path)
    return pygltflib.GLTF2().load(str(output_path))


class TestMinimalMeshOnly:
    def test_compile_and_reload(self, minimal_mesh_yaml, tmp_path):
        out = tmp_path / "minimal.glb"
        gltf = _compile(minimal_mesh_yaml, out)
        assert len(gltf.meshes) == 1
        assert len(gltf.skins) == 0

    def test_mesh_has_vertices(self, minimal_mesh_yaml, tmp_path):
        out = tmp_path / "minimal.glb"
        gltf = _compile(minimal_mesh_yaml, out)
        pos_acc = gltf.accessors[0]
        assert pos_acc.count == 24  # box: 24 verts


class TestFullHumanoid:
    def test_compile_and_reload(self, full_humanoid_yaml, tmp_path):
        out = tmp_path / "humanoid.glb"
        gltf = _compile(full_humanoid_yaml, out)
        assert len(gltf.meshes) == 1
        assert len(gltf.skins) == 1

    def test_bone_count(self, full_humanoid_yaml, tmp_path):
        out = tmp_path / "humanoid.glb"
        gltf = _compile(full_humanoid_yaml, out)
        # After symmetry: 5 original + 2 mirrored = 7 bones
        assert len(gltf.skins[0].joints) == 7

    def test_mirrored_elements(self, full_humanoid_yaml, tmp_path):
        out = tmp_path / "humanoid.glb"
        gltf = _compile(full_humanoid_yaml, out)
        bone_names = {gltf.nodes[j].name for j in gltf.skins[0].joints}
        assert "legL_upper" in bone_names
        assert "legR_upper" in bone_names
        assert "legL_lower" in bone_names
        assert "legR_lower" in bone_names


class TestHumanoidFixture:
    def test_fixture_compiles(self, tmp_path):
        fixture = Path(__file__).parent / "fixtures" / "humanoid.rigy.yaml"
        if not fixture.exists():
            return  # skip if fixture not yet created
        out = tmp_path / "humanoid.glb"
        gltf = _compile(fixture.read_text(), out)
        assert len(gltf.meshes) >= 1


class TestWheelV01Subset:
    """wheel.rigy.yaml contains v0.2 fields (anchors, name, metadata) — test strict rejection."""

    def test_wheel_rejected_with_v02_fields(self):
        """Wheel has anchors/metadata/name which are v0.2 fields not in RigySpec."""
        wheel_path = Path(__file__).parent.parent / "composition" / "parts" / "wheel.rigy.yaml"
        if not wheel_path.exists():
            return
        import pytest
        from rigy.errors import ParseError

        with pytest.raises(ParseError):
            parse_yaml(wheel_path)


class TestCarRejectedStrict:
    """car.rigy.yaml uses v0.2 fields (imports, instances, anchors) — must be rejected."""

    def test_car_rejected(self):
        car_path = Path(__file__).parent.parent / "composition" / "car.rigy.yaml"
        if not car_path.exists():
            return
        import pytest
        from rigy.errors import ParseError

        with pytest.raises(ParseError):
            parse_yaml(car_path)


class TestDeterminism:
    def test_identical_bytes(self, minimal_mesh_yaml, tmp_path):
        out1 = tmp_path / "a.glb"
        out2 = tmp_path / "b.glb"
        _compile(minimal_mesh_yaml, out1)
        _compile(minimal_mesh_yaml, out2)
        assert out1.read_bytes() == out2.read_bytes()

    def test_humanoid_determinism(self, full_humanoid_yaml, tmp_path):
        out1 = tmp_path / "h1.glb"
        out2 = tmp_path / "h2.glb"
        _compile(full_humanoid_yaml, out1)
        _compile(full_humanoid_yaml, out2)
        assert out1.read_bytes() == out2.read_bytes()
