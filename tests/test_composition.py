"""Tests for composition: instance resolution, namespace handling, circular imports."""

from pathlib import Path

import numpy as np
import pytest
from numpy.testing import assert_allclose

from rigy.composition import ComposedAsset, resolve_composition
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
