"""Tests for Rigs validation."""

from pathlib import Path

import pytest

from rigy.errors import ValidationError
from rigy.rigs_parser import parse_rigs
from rigy.rigs_validation import validate_rigs

FIXTURES = Path(__file__).parent / "rigs_fixtures"


class TestValidRigs:
    def test_simple_scene_valid(self):
        asset = parse_rigs(FIXTURES / "simple_scene.rigs.yaml")
        validate_rigs(asset)  # Should not raise

    def test_nested_scene_valid(self):
        asset = parse_rigs(FIXTURES / "nested_scene.rigs.yaml")
        validate_rigs(asset)  # Should not raise

    def test_rotated_scene_valid(self):
        asset = parse_rigs(FIXTURES / "rotated_scene.rigs.yaml")
        validate_rigs(asset)  # Should not raise


class TestInvalidBase:
    def test_unknown_scene_base(self, tmp_path):
        _write_parts(tmp_path)
        doc = tmp_path / "scene.rigs.yaml"
        doc.write_text(
            'rigs_version: "0.1"\nimports:\n  a: parts/a.rigy.yaml\nscene:\n  base: nonexistent\n'
        )
        asset = parse_rigs(doc)
        with pytest.raises(ValidationError, match="not a key in imports"):
            validate_rigs(asset)

    def test_unknown_child_base(self, tmp_path):
        _write_parts(tmp_path)
        doc = tmp_path / "scene.rigs.yaml"
        doc.write_text(
            'rigs_version: "0.1"\n'
            "imports:\n"
            "  a: parts/a.rigy.yaml\n"
            "scene:\n"
            "  base: a\n"
            "  children:\n"
            "    - id: inst1\n"
            "      base: missing\n"
            "      place:\n"
            "        slot: { anchors: [p1, p2, p3] }\n"
            "        mount: { anchors: [p1, p2, p3] }\n"
        )
        asset = parse_rigs(doc)
        with pytest.raises(ValidationError, match="not a key in imports"):
            validate_rigs(asset)


class TestDuplicateIds:
    def test_duplicate_instance_ids(self, tmp_path):
        _write_parts(tmp_path)
        doc = tmp_path / "scene.rigs.yaml"
        doc.write_text(
            'rigs_version: "0.1"\n'
            "imports:\n"
            "  a: parts/a.rigy.yaml\n"
            "  b: parts/b.rigy.yaml\n"
            "scene:\n"
            "  base: a\n"
            "  children:\n"
            "    - id: dup\n"
            "      base: b\n"
            "      place:\n"
            "        slot: { anchors: [p1, p2, p3] }\n"
            "        mount: { anchors: [p1, p2, p3] }\n"
            "    - id: dup\n"
            "      base: b\n"
            "      place:\n"
            "        slot: { anchors: [p1, p2, p3] }\n"
            "        mount: { anchors: [p1, p2, p3] }\n"
        )
        asset = parse_rigs(doc)
        with pytest.raises(ValidationError, match="Duplicate instance ID"):
            validate_rigs(asset)


class TestMissingAnchors:
    def test_missing_slot_anchor(self, tmp_path):
        _write_parts(tmp_path)
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
            "        slot: { anchors: [p1, p2, nonexistent] }\n"
            "        mount: { anchors: [p1, p2, p3] }\n"
        )
        asset = parse_rigs(doc)
        with pytest.raises(ValidationError, match="not found in asset"):
            validate_rigs(asset)

    def test_missing_mount_anchor(self, tmp_path):
        _write_parts(tmp_path)
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
            "        mount: { anchors: [p1, p2, nonexistent] }\n"
        )
        asset = parse_rigs(doc)
        with pytest.raises(ValidationError, match="not found in asset"):
            validate_rigs(asset)


class TestNamedRefWithoutContract:
    def test_named_slot_no_contract(self, tmp_path):
        _write_parts(tmp_path)
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
            "        slot: { name: some_slot }\n"
            "        mount: { anchors: [p1, p2, p3] }\n"
        )
        asset = parse_rigs(doc)
        with pytest.raises(ValidationError, match="no contract"):
            validate_rigs(asset)


def _write_parts(tmp_path: Path) -> None:
    """Write minimal Rigy parts with anchors."""
    parts = tmp_path / "parts"
    parts.mkdir(exist_ok=True)
    for name in ["a", "b"]:
        (parts / f"{name}.rigy.yaml").write_text(
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
