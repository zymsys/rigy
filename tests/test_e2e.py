"""End-to-end integration tests."""

from pathlib import Path

import pygltflib

from rigy.composition import resolve_composition
from rigy.exporter import export_gltf
from rigy.parser import parse_with_imports, parse_yaml
from rigy.symmetry import expand_symmetry
from rigy.validation import validate, validate_composition


def _compile(yaml_str: str, output_path: Path) -> pygltflib.GLTF2:
    """Full compile pipeline: parse -> expand -> validate -> export -> reload."""
    spec = parse_yaml(yaml_str)
    spec = expand_symmetry(spec)
    validate(spec)
    export_gltf(spec, output_path)
    return pygltflib.GLTF2().load(str(output_path))


def _compile_file(input_path: Path, output_path: Path) -> pygltflib.GLTF2:
    """Full v0.2 compile pipeline from file: parse_with_imports -> expand -> validate -> compose -> export."""
    asset = parse_with_imports(input_path)
    asset.spec = expand_symmetry(asset.spec)
    validate(asset.spec)
    for _ns, imported in asset.imported_assets.items():
        imported.spec = expand_symmetry(imported.spec)
    if asset.spec.instances:
        validate_composition(asset)
    composed = resolve_composition(asset)
    export_gltf(composed, output_path)
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


class TestWheelV02:
    """wheel.rigy.yaml in composition/parts is now valid v0.2."""

    def test_wheel_parses(self):
        wheel_path = Path(__file__).parent / "composition" / "parts" / "wheel.rigy.yaml"
        if not wheel_path.exists():
            return
        spec = parse_yaml(wheel_path)
        assert spec.version == "0.2"
        assert len(spec.anchors) == 3


class TestUnknownFieldsRejected:
    """Strict parsing rejects YAML with unknown top-level fields."""

    def test_unknown_name_field_rejected(self):
        import pytest
        from rigy.errors import ParseError

        yaml_str = """\
rigy_version: "0.1"
name: BasicWheel
meshes:
  - id: wheel_mesh
    primitives:
      - type: cylinder
        id: wheel_geo
        dimensions:
          radius: 0.25
          height: 0.15
"""
        with pytest.raises(ParseError):
            parse_yaml(yaml_str)

    def test_unknown_metadata_field_rejected(self):
        import pytest
        from rigy.errors import ParseError

        yaml_str = """\
rigy_version: "0.1"
metadata:
  description: "A car with wheels"
meshes:
  - id: car_body
    primitives:
      - type: box
        id: body
        dimensions: { x: 2.0, y: 0.4, z: 1.2 }
"""
        with pytest.raises(ParseError):
            parse_yaml(yaml_str)


class TestCompositionE2E:
    def test_car_compiles(self, tmp_path):
        fixture = Path(__file__).parent / "composition" / "car.rigy.yaml"
        if not fixture.exists():
            return
        out = tmp_path / "car.glb"
        gltf = _compile_file(fixture, out)
        assert out.exists()
        # 1 car body mesh + 4 wheel meshes
        assert len(gltf.meshes) == 5

    def test_car_has_instance_nodes(self, tmp_path):
        fixture = Path(__file__).parent / "composition" / "car.rigy.yaml"
        if not fixture.exists():
            return
        out = tmp_path / "car.glb"
        gltf = _compile_file(fixture, out)
        node_names = [n.name for n in gltf.nodes]
        assert "wheel_fl" in node_names
        assert "wheel_fr" in node_names
        assert "wheel_rl" in node_names
        assert "wheel_rr" in node_names

    def test_instance_has_matrix(self, tmp_path):
        fixture = Path(__file__).parent / "composition" / "car.rigy.yaml"
        if not fixture.exists():
            return
        out = tmp_path / "car.glb"
        gltf = _compile_file(fixture, out)
        instance_names = {"wheel_fl", "wheel_fr", "wheel_rl", "wheel_rr"}
        for node in gltf.nodes:
            if node.name in instance_names:
                # Instance nodes have matrix set
                assert node.matrix is not None


class TestLocalMeshInstanceE2E:
    def test_local_mesh_instance_compile(self, tmp_path):
        """Compile a spec with local mesh instances to GLB."""
        yaml_str = """\
version: "0.2"
meshes:
  - id: shelf
    primitives:
      - type: box
        id: shelf_box
        dimensions: { x: 1.0, y: 0.1, z: 0.5 }
        transform:
          translation: [0, 1.0, 0]
instances:
  - id: shelf_copy
    mesh_id: shelf
"""
        spec = parse_yaml(yaml_str)
        validate(spec)
        from rigy.models import ResolvedAsset

        asset = ResolvedAsset(spec=spec, path=tmp_path / "test.rigy.yaml")
        composed = resolve_composition(asset)
        out = tmp_path / "local_mesh.glb"
        export_gltf(composed, out)
        gltf = pygltflib.GLTF2().load(str(out))
        assert len(gltf.meshes) == 1
        # Root mesh node + local instance node
        assert len(gltf.nodes) == 2
        node_names = [n.name for n in gltf.nodes]
        assert "shelf_copy" in node_names


class TestBakeTransformsE2E:
    def test_bake_transforms_car(self, tmp_path):
        fixture = Path(__file__).parent / "composition" / "car.rigy.yaml"
        if not fixture.exists():
            return
        from rigy.composition import bake_transforms

        asset = parse_with_imports(fixture)
        asset.spec = expand_symmetry(asset.spec)
        validate(asset.spec)
        for _ns, imported in asset.imported_assets.items():
            imported.spec = expand_symmetry(imported.spec)
        if asset.spec.instances:
            validate_composition(asset)
        composed = resolve_composition(asset)
        baked = bake_transforms(composed)

        out = tmp_path / "car_baked.glb"
        export_gltf(baked, out)
        gltf = pygltflib.GLTF2().load(str(out))
        assert len(gltf.meshes) == 5

        # Instance nodes should have identity matrix after baking
        import numpy as np
        from numpy.testing import assert_allclose

        identity = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]
        instance_names = {"wheel_fl", "wheel_fr", "wheel_rl", "wheel_rr"}
        for node in gltf.nodes:
            if node.name in instance_names:
                assert_allclose(node.matrix, identity, atol=1e-6)


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

    def test_geometry_checks_do_not_affect_export_bytes(self, minimal_mesh_yaml, tmp_path):
        with_checks_yaml = (
            minimal_mesh_yaml
            + """
geometry_checks:
  checks:
    - id: c1
      expr: $missing
    - id: c2
      expr: ${leftover}
"""
        )
        out1 = tmp_path / "no_checks.glb"
        out2 = tmp_path / "with_checks.glb"
        _compile(minimal_mesh_yaml, out1)
        _compile(with_checks_yaml, out2)
        assert out1.read_bytes() == out2.read_bytes()
