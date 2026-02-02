"""Tests for Rigs parser."""

from pathlib import Path

import pytest

from rigy.errors import ParseError
from rigy.rigs_parser import parse_rigs

FIXTURES = Path(__file__).parent / "rigs_fixtures"


class TestParseRigs:
    def test_valid_simple_scene(self):
        asset = parse_rigs(FIXTURES / "simple_scene.rigs.yaml")
        assert asset.spec.rigs_version == "0.1"
        assert "plate" in asset.spec.imports
        assert "cube" in asset.spec.imports
        assert asset.spec.scene.base == "plate"
        assert len(asset.spec.scene.children) == 1
        assert asset.spec.scene.children[0].id == "cube1"

    def test_resolved_imports(self):
        asset = parse_rigs(FIXTURES / "simple_scene.rigs.yaml")
        assert "plate" in asset.resolved_imports
        assert "cube" in asset.resolved_imports
        assert len(asset.resolved_imports["plate"].spec.meshes) == 1
        assert len(asset.resolved_imports["cube"].spec.meshes) == 1


class TestVersionRejection:
    def test_wrong_version(self, tmp_path):
        doc = tmp_path / "bad.rigs.yaml"
        doc.write_text('rigs_version: "0.2"\nimports: {}\nscene:\n  base: x\n')
        with pytest.raises(ParseError, match="Unsupported rigs_version"):
            parse_rigs(doc)

    def test_missing_version(self, tmp_path):
        doc = tmp_path / "bad.rigs.yaml"
        doc.write_text("imports: {}\nscene:\n  base: x\n")
        with pytest.raises(ParseError, match="Missing required field"):
            parse_rigs(doc)


class TestInvalidTokens:
    def test_invalid_rotate(self, tmp_path):
        parts = tmp_path / "parts"
        parts.mkdir()
        _write_minimal_part(parts / "a.rigy.yaml")
        _write_minimal_part(parts / "b.rigy.yaml")

        doc = tmp_path / "scene.rigs.yaml"
        doc.write_text(
            'rigs_version: "0.1"\n'
            "imports:\n"
            "  a: parts/a.rigy.yaml\n"
            "  b: parts/b.rigy.yaml\n"
            "scene:\n"
            "  base: a\n"
            "  children:\n"
            "    - id: inst1\n"
            "      base: b\n"
            "      place:\n"
            "        slot: { anchors: [p1, p2, p3] }\n"
            "        mount: { anchors: [p1, p2, p3] }\n"
            "        rotate: 45deg\n"
        )
        with pytest.raises(ParseError, match="invalid rotate"):
            parse_rigs(doc)

    def test_invalid_nudge(self, tmp_path):
        parts = tmp_path / "parts"
        parts.mkdir()
        _write_minimal_part(parts / "a.rigy.yaml")
        _write_minimal_part(parts / "b.rigy.yaml")

        doc = tmp_path / "scene.rigs.yaml"
        doc.write_text(
            'rigs_version: "0.1"\n'
            "imports:\n"
            "  a: parts/a.rigy.yaml\n"
            "  b: parts/b.rigy.yaml\n"
            "scene:\n"
            "  base: a\n"
            "  children:\n"
            "    - id: inst1\n"
            "      base: b\n"
            "      place:\n"
            "        slot: { anchors: [p1, p2, p3] }\n"
            "        mount: { anchors: [p1, p2, p3] }\n"
            "        nudge: { north: abc, east: 0, up: 0 }\n"
        )
        with pytest.raises(ParseError, match="invalid nudge"):
            parse_rigs(doc)

    def test_missing_import_file(self, tmp_path):
        doc = tmp_path / "scene.rigs.yaml"
        doc.write_text(
            'rigs_version: "0.1"\nimports:\n  a: nonexistent.rigy.yaml\nscene:\n  base: a\n'
        )
        with pytest.raises(ParseError, match="source file not found"):
            parse_rigs(doc)


def _write_minimal_part(path: Path) -> None:
    """Write a minimal Rigy asset with anchors."""
    path.write_text(
        'version: "0.2"\n'
        "units: meters\n"
        "coordinate_system:\n"
        "  up: Y\n"
        "  forward: -Z\n"
        "  handedness: right\n"
        "tessellation_profile: v0_1_default\n"
        "meshes:\n"
        "  - id: m\n"
        "    primitives:\n"
        "      - type: box\n"
        "        id: b\n"
        "        dimensions: { x: 1, y: 1, z: 1 }\n"
        "anchors:\n"
        "  - id: p1\n"
        "    translation: [0, 0, 0]\n"
        "  - id: p2\n"
        "    translation: [1, 0, 0]\n"
        "  - id: p3\n"
        "    translation: [0, 0, 1]\n"
    )
