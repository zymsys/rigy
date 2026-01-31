"""Tests for composition: instance resolution, namespace handling, circular imports."""

from pathlib import Path

import numpy as np
import pytest
from numpy.testing import assert_allclose

from rigy.composition import ComposedAsset, bake_transforms, resolve_composition
from rigy.errors import CompositionError, ParseError
from rigy.models import (
    Anchor,
    Attach3,
    ImportDef,
    Instance,
    ResolvedAsset,
    RigySpec,
)
from rigy.parser import parse_with_imports


def _make_wheel_spec() -> RigySpec:
    return RigySpec(
        version="0.2",
        meshes=[
            {
                "id": "wheel_mesh",
                "primitives": [
                    {
                        "type": "cylinder",
                        "id": "wheel_geo",
                        "dimensions": {"radius": 0.25, "height": 0.15},
                    }
                ],
            }
        ],
        anchors=[
            Anchor(id="mount_a", translation=(0, 0, 0)),
            Anchor(id="mount_b", translation=(1, 0, 0)),
            Anchor(id="mount_c", translation=(0, 0, 1)),
        ],
    )


def _make_car_spec_with_one_wheel() -> RigySpec:
    return RigySpec(
        version="0.2",
        meshes=[
            {
                "id": "body_mesh",
                "primitives": [
                    {
                        "type": "box",
                        "id": "body",
                        "dimensions": {"x": 2, "y": 0.5, "z": 1},
                    }
                ],
            }
        ],
        anchors=[
            Anchor(id="fl_a", translation=(1, 0, 0.5)),
            Anchor(id="fl_b", translation=(2, 0, 0.5)),
            Anchor(id="fl_c", translation=(1, 0, 1.5)),
        ],
        imports={"wheel": ImportDef(source="parts/wheel.rigy.yaml")},
        instances=[
            Instance(
                id="wheel_fl",
                import_="wheel",
                attach3=Attach3(
                    from_=["wheel.mount_a", "wheel.mount_b", "wheel.mount_c"],
                    to=["fl_a", "fl_b", "fl_c"],
                    mode="rigid",
                ),
            )
        ],
    )


class TestResolveComposition:
    def test_no_instances_returns_empty(self):
        spec = RigySpec(version="0.2")
        asset = ResolvedAsset(spec=spec, path=Path("/fake"))
        composed = resolve_composition(asset)
        assert isinstance(composed, ComposedAsset)
        assert composed.instances == []
        assert composed.root_spec is spec

    def test_single_instance_resolved(self):
        wheel_spec = _make_wheel_spec()
        car_spec = _make_car_spec_with_one_wheel()
        wheel_asset = ResolvedAsset(spec=wheel_spec, path=Path("/fake/wheel.rigy.yaml"))
        car_asset = ResolvedAsset(
            spec=car_spec,
            path=Path("/fake/car.rigy.yaml"),
            imported_assets={"wheel": wheel_asset},
        )
        composed = resolve_composition(car_asset)
        assert len(composed.instances) == 1
        assert composed.instances[0].id == "wheel_fl"
        assert composed.instances[0].namespace == "wheel"
        assert composed.instances[0].source_spec is wheel_spec
        assert composed.instances[0].transform.shape == (4, 4)

    def test_transform_translates_origin(self):
        """Wheel origin should map to fl_a position."""
        wheel_spec = _make_wheel_spec()
        car_spec = _make_car_spec_with_one_wheel()
        wheel_asset = ResolvedAsset(spec=wheel_spec, path=Path("/fake/wheel.rigy.yaml"))
        car_asset = ResolvedAsset(
            spec=car_spec,
            path=Path("/fake/car.rigy.yaml"),
            imported_assets={"wheel": wheel_asset},
        )
        composed = resolve_composition(car_asset)
        T = composed.instances[0].transform

        # Origin of wheel (0,0,0) should map to fl_a (1, 0, 0.5)
        origin = np.array([0, 0, 0, 1])
        result = T @ origin
        assert_allclose(result[:3], [1, 0, 0.5], atol=1e-10)

    def test_missing_import_raises(self):
        car_spec = _make_car_spec_with_one_wheel()
        car_asset = ResolvedAsset(
            spec=car_spec,
            path=Path("/fake/car.rigy.yaml"),
            imported_assets={},  # no wheel imported
        )
        with pytest.raises(CompositionError, match="not found"):
            resolve_composition(car_asset)

    def test_missing_from_anchor_raises(self):
        wheel_spec = RigySpec(
            version="0.2",
            anchors=[Anchor(id="mount_a", translation=(0, 0, 0))],
        )
        car_spec = _make_car_spec_with_one_wheel()
        wheel_asset = ResolvedAsset(spec=wheel_spec, path=Path("/fake/wheel.rigy.yaml"))
        car_asset = ResolvedAsset(
            spec=car_spec,
            path=Path("/fake/car.rigy.yaml"),
            imported_assets={"wheel": wheel_asset},
        )
        with pytest.raises(CompositionError, match="mount_b"):
            resolve_composition(car_asset)

    def test_missing_to_anchor_raises(self):
        wheel_spec = _make_wheel_spec()
        car_spec = RigySpec(
            version="0.2",
            anchors=[
                Anchor(id="fl_a", translation=(1, 0, 0.5)),
                # missing fl_b, fl_c
            ],
            imports={"wheel": ImportDef(source="parts/wheel.rigy.yaml")},
            instances=[
                Instance(
                    id="wheel_fl",
                    import_="wheel",
                    attach3=Attach3(
                        from_=["wheel.mount_a", "wheel.mount_b", "wheel.mount_c"],
                        to=["fl_a", "fl_b", "fl_c"],
                        mode="rigid",
                    ),
                )
            ],
        )
        wheel_asset = ResolvedAsset(spec=wheel_spec, path=Path("/fake/wheel.rigy.yaml"))
        car_asset = ResolvedAsset(
            spec=car_spec,
            path=Path("/fake/car.rigy.yaml"),
            imported_assets={"wheel": wheel_asset},
        )
        with pytest.raises(CompositionError, match="fl_b"):
            resolve_composition(car_asset)


class TestCircularImports:
    def test_circular_import_detected(self, tmp_path):
        # a.rigy.yaml imports b.rigy.yaml which imports a.rigy.yaml
        a = tmp_path / "a.rigy.yaml"
        b = tmp_path / "b.rigy.yaml"
        a.write_text('version: "0.2"\nimports:\n  b:\n    source: b.rigy.yaml\n')
        b.write_text('version: "0.2"\nimports:\n  a:\n    source: a.rigy.yaml\n')
        with pytest.raises(ParseError, match="Circular"):
            parse_with_imports(a)

    def test_self_import_detected(self, tmp_path):
        a = tmp_path / "a.rigy.yaml"
        a.write_text('version: "0.2"\nimports:\n  self:\n    source: a.rigy.yaml\n')
        with pytest.raises(ParseError, match="Circular"):
            parse_with_imports(a)

    def test_missing_import_source(self, tmp_path):
        a = tmp_path / "a.rigy.yaml"
        a.write_text('version: "0.2"\nimports:\n  missing:\n    source: nonexistent.rigy.yaml\n')
        with pytest.raises(ParseError, match="not found"):
            parse_with_imports(a)


class TestParseWithImports:
    def test_no_imports(self, tmp_path):
        f = tmp_path / "simple.rigy.yaml"
        f.write_text('version: "0.2"\n')
        asset = parse_with_imports(f)
        assert asset.imported_assets == {}
        assert asset.spec.version == "0.2"

    def test_with_imports(self, tmp_path):
        parts = tmp_path / "parts"
        parts.mkdir()
        wheel = parts / "wheel.rigy.yaml"
        wheel.write_text('version: "0.2"\nanchors:\n  - id: mount_a\n    translation: [0, 0, 0]\n')
        car = tmp_path / "car.rigy.yaml"
        car.write_text('version: "0.2"\nimports:\n  wheel:\n    source: parts/wheel.rigy.yaml\n')
        asset = parse_with_imports(car)
        assert "wheel" in asset.imported_assets
        assert asset.imported_assets["wheel"].spec.version == "0.2"

    def test_with_contract(self, tmp_path):
        parts = tmp_path / "parts"
        parts.mkdir()
        wheel = parts / "wheel.rigy.yaml"
        wheel.write_text('version: "0.2"\nanchors:\n  - id: mount_a\n    translation: [0, 0, 0]\n')
        contract = parts / "wheel.ricy.yaml"
        contract.write_text('contract_version: "0.1"\nrequired_anchors:\n  - mount_a\n')
        car = tmp_path / "car.rigy.yaml"
        car.write_text(
            'version: "0.2"\n'
            "imports:\n"
            "  wheel:\n"
            "    source: parts/wheel.rigy.yaml\n"
            "    contract: parts/wheel.ricy.yaml\n"
        )
        asset = parse_with_imports(car)
        assert asset.imported_assets["wheel"].contract is not None
        assert "mount_a" in asset.imported_assets["wheel"].contract.required_anchors


class TestCompositionFixture:
    def test_car_fixture_compiles(self, tmp_path):
        fixture = Path(__file__).parent / "composition" / "car.rigy.yaml"
        if not fixture.exists():
            pytest.skip("Car fixture not found")

        from rigy.composition import resolve_composition
        from rigy.exporter import export_gltf
        from rigy.parser import parse_with_imports
        from rigy.symmetry import expand_symmetry
        from rigy.validation import validate

        asset = parse_with_imports(fixture)
        asset.spec = expand_symmetry(asset.spec)
        validate(asset.spec)
        for ns, imported in asset.imported_assets.items():
            imported.spec = expand_symmetry(imported.spec)
        composed = resolve_composition(asset)

        out = tmp_path / "car.glb"
        export_gltf(composed, out)
        assert out.exists()

        import pygltflib

        gltf = pygltflib.GLTF2().load(str(out))
        # Root body mesh + 4 wheel meshes = 5 meshes
        assert len(gltf.meshes) == 5
        # 4 instance nodes + 4 wheel mesh child nodes + 1 body mesh node = 9 nodes min
        assert len(gltf.nodes) >= 9

    def test_car_fixture_determinism(self, tmp_path):
        fixture = Path(__file__).parent / "composition" / "car.rigy.yaml"
        if not fixture.exists():
            pytest.skip("Car fixture not found")

        from rigy.composition import resolve_composition
        from rigy.exporter import export_gltf
        from rigy.parser import parse_with_imports
        from rigy.symmetry import expand_symmetry
        from rigy.validation import validate

        def _compile(out):
            asset = parse_with_imports(fixture)
            asset.spec = expand_symmetry(asset.spec)
            validate(asset.spec)
            for ns, imported in asset.imported_assets.items():
                imported.spec = expand_symmetry(imported.spec)
            composed = resolve_composition(asset)
            export_gltf(composed, out)

        out1 = tmp_path / "car1.glb"
        out2 = tmp_path / "car2.glb"
        _compile(out1)
        _compile(out2)
        assert out1.read_bytes() == out2.read_bytes()


class TestLocalMeshInstance:
    def test_local_mesh_resolves_identity(self):
        spec = RigySpec(
            version="0.2",
            meshes=[
                {
                    "id": "shelf",
                    "primitives": [
                        {
                            "type": "box",
                            "id": "shelf_box",
                            "dimensions": {"x": 1, "y": 0.1, "z": 0.5},
                        }
                    ],
                }
            ],
            instances=[Instance(id="shelf_copy", mesh_id="shelf")],
        )
        asset = ResolvedAsset(spec=spec, path=Path("/fake"))
        composed = resolve_composition(asset)
        assert len(composed.instances) == 1
        inst = composed.instances[0]
        assert inst.mesh_id == "shelf"
        assert inst.source_spec is None
        assert_allclose(inst.transform, np.eye(4), atol=1e-10)

    def test_local_mesh_with_attach3(self):
        spec = RigySpec(
            version="0.2",
            meshes=[
                {
                    "id": "shelf",
                    "primitives": [
                        {
                            "type": "box",
                            "id": "shelf_box",
                            "dimensions": {"x": 1, "y": 0.1, "z": 0.5},
                        }
                    ],
                }
            ],
            anchors=[
                Anchor(id="from_a", translation=(0, 0, 0)),
                Anchor(id="from_b", translation=(1, 0, 0)),
                Anchor(id="from_c", translation=(0, 0, 1)),
                Anchor(id="to_a", translation=(2, 0, 0)),
                Anchor(id="to_b", translation=(3, 0, 0)),
                Anchor(id="to_c", translation=(2, 0, 1)),
            ],
            instances=[
                Instance(
                    id="shelf_copy",
                    mesh_id="shelf",
                    attach3=Attach3(
                        from_=["from_a", "from_b", "from_c"],
                        to=["to_a", "to_b", "to_c"],
                        mode="rigid",
                    ),
                )
            ],
        )
        asset = ResolvedAsset(spec=spec, path=Path("/fake"))
        composed = resolve_composition(asset)
        inst = composed.instances[0]
        # Transform should translate by (2, 0, 0)
        origin = np.array([0, 0, 0, 1])
        result = inst.transform @ origin
        assert_allclose(result[:3], [2, 0, 0], atol=1e-10)

    def test_local_mesh_exports(self, tmp_path):
        from rigy.exporter import export_gltf

        spec = RigySpec(
            version="0.2",
            meshes=[
                {
                    "id": "shelf",
                    "primitives": [
                        {
                            "type": "box",
                            "id": "shelf_box",
                            "dimensions": {"x": 1, "y": 0.1, "z": 0.5},
                        }
                    ],
                }
            ],
            instances=[Instance(id="shelf_copy", mesh_id="shelf")],
        )
        asset = ResolvedAsset(spec=spec, path=Path("/fake"))
        composed = resolve_composition(asset)
        out = tmp_path / "local_mesh.glb"
        export_gltf(composed, out)
        assert out.exists()

        import pygltflib

        gltf = pygltflib.GLTF2().load(str(out))
        # 1 root mesh + 1 local instance referencing same mesh
        assert len(gltf.meshes) == 1
        # Node for root mesh + node for local instance
        assert len(gltf.nodes) == 2


class TestBakeTransforms:
    def test_bake_identity_unchanged(self):
        """Baking identity transforms is a no-op."""
        wheel_spec = _make_wheel_spec()
        car_spec = _make_car_spec_with_one_wheel()
        wheel_asset = ResolvedAsset(spec=wheel_spec, path=Path("/fake/wheel.rigy.yaml"))
        car_asset = ResolvedAsset(
            spec=car_spec,
            path=Path("/fake/car.rigy.yaml"),
            imported_assets={"wheel": wheel_asset},
        )
        composed = resolve_composition(car_asset)
        # Manually set transform to identity
        composed.instances[0].transform = np.eye(4)
        baked = bake_transforms(composed)
        assert_allclose(baked.instances[0].transform, np.eye(4), atol=1e-10)

    def test_bake_produces_identity_transform(self):
        """After baking, instance transform should be identity."""
        wheel_spec = _make_wheel_spec()
        car_spec = _make_car_spec_with_one_wheel()
        wheel_asset = ResolvedAsset(spec=wheel_spec, path=Path("/fake/wheel.rigy.yaml"))
        car_asset = ResolvedAsset(
            spec=car_spec,
            path=Path("/fake/car.rigy.yaml"),
            imported_assets={"wheel": wheel_asset},
        )
        composed = resolve_composition(car_asset)
        original_transform = composed.instances[0].transform.copy()
        assert not np.allclose(original_transform, np.eye(4))

        baked = bake_transforms(composed)
        assert_allclose(baked.instances[0].transform, np.eye(4), atol=1e-10)
        # Original should not be mutated
        assert_allclose(composed.instances[0].transform, original_transform, atol=1e-10)

    def test_bake_transforms_bone_positions(self):
        """After baking, bone heads should be in world space."""
        wheel_spec = RigySpec(
            version="0.2",
            meshes=[
                {
                    "id": "w_mesh",
                    "primitives": [
                        {
                            "type": "cylinder",
                            "id": "w_geo",
                            "dimensions": {"radius": 0.25, "height": 0.15},
                        }
                    ],
                }
            ],
            armatures=[
                {
                    "id": "w_arm",
                    "bones": [
                        {"id": "root", "parent": "none", "head": [0, 0, 0], "tail": [0, 1, 0]},
                    ],
                }
            ],
            anchors=[
                Anchor(id="mount_a", translation=(0, 0, 0)),
                Anchor(id="mount_b", translation=(1, 0, 0)),
                Anchor(id="mount_c", translation=(0, 0, 1)),
            ],
        )
        car_spec = _make_car_spec_with_one_wheel()
        wheel_asset = ResolvedAsset(spec=wheel_spec, path=Path("/fake/wheel.rigy.yaml"))
        car_asset = ResolvedAsset(
            spec=car_spec,
            path=Path("/fake/car.rigy.yaml"),
            imported_assets={"wheel": wheel_asset},
        )
        composed = resolve_composition(car_asset)
        T = composed.instances[0].transform

        baked = bake_transforms(composed)
        baked_bone = baked.instances[0].source_spec.armatures[0].bones[0]

        # The root bone head (0,0,0) should now be at T @ (0,0,0,1)
        expected = (T @ np.array([0, 0, 0, 1]))[:3]
        assert_allclose(baked_bone.head, expected, atol=1e-10)

    def test_baked_car_exports(self, tmp_path):
        """Car with bake-transforms should produce valid GLB."""
        fixture = Path(__file__).parent / "composition" / "car.rigy.yaml"
        if not fixture.exists():
            pytest.skip("Car fixture not found")

        from rigy.exporter import export_gltf
        from rigy.parser import parse_with_imports
        from rigy.symmetry import expand_symmetry
        from rigy.validation import validate

        asset = parse_with_imports(fixture)
        asset.spec = expand_symmetry(asset.spec)
        validate(asset.spec)
        for ns, imported in asset.imported_assets.items():
            imported.spec = expand_symmetry(imported.spec)
        composed = resolve_composition(asset)
        baked = bake_transforms(composed)
        out = tmp_path / "car_baked.glb"
        export_gltf(baked, out)
        assert out.exists()

        import pygltflib

        gltf = pygltflib.GLTF2().load(str(out))
        assert len(gltf.meshes) == 5
