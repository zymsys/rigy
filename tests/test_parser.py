"""Tests for YAML parser."""

import pytest

from rigy.errors import ParseError
from rigy.parser import parse_yaml


class TestParseYaml:
    def test_parse_valid_string(self, minimal_mesh_yaml):
        spec = parse_yaml(minimal_mesh_yaml)
        assert spec.version == "0.1"
        assert len(spec.meshes) == 1

    def test_parse_from_file(self, minimal_mesh_yaml, tmp_path):
        f = tmp_path / "test.rigy.yaml"
        f.write_text(minimal_mesh_yaml)
        spec = parse_yaml(f)
        assert spec.version == "0.1"

    def test_reject_invalid_yaml(self):
        with pytest.raises(ParseError, match="Invalid YAML"):
            parse_yaml("{{{{not valid yaml")

    def test_reject_non_dict(self):
        with pytest.raises(ParseError, match="mapping"):
            parse_yaml("- item1\n- item2")

    def test_missing_version(self):
        with pytest.raises(ParseError, match="version"):
            parse_yaml("units: meters\n")

    def test_unsupported_version_error(self):
        with pytest.raises(ParseError, match="Unsupported version"):
            parse_yaml('version: "1000.0"\nunits: meters\n')

    def test_unsupported_minor_version_error(self):
        with pytest.raises(ParseError, match="Unsupported version"):
            parse_yaml('version: "0.10"\nunits: meters\n')

    def test_v05_accepted(self):
        spec = parse_yaml('version: "0.5"\nunits: meters\n')
        assert spec.version == "0.5"

    def test_v04_accepted(self):
        spec = parse_yaml('version: "0.4"\nunits: meters\n')
        assert spec.version == "0.4"

    def test_v03_accepted(self):
        spec = parse_yaml('version: "0.3"\nunits: meters\n')
        assert spec.version == "0.3"

    def test_v02_accepted(self):
        spec = parse_yaml('version: "0.2"\nunits: meters\n')
        assert spec.version == "0.2"

    def test_invalid_version_format(self):
        with pytest.raises(ParseError, match="Invalid version"):
            parse_yaml('version: "abc"\n')

    def test_file_not_found(self, tmp_path):
        with pytest.raises(ParseError, match="Cannot read"):
            parse_yaml(tmp_path / "nonexistent.yaml")

    def test_v06_accepted(self):
        spec = parse_yaml('version: "0.6"\nunits: meters\n')
        assert spec.version == "0.6"

    def test_material_parsed(self):
        yaml_str = """\
version: "0.6"
units: meters
materials:
  red:
    base_color: [1.0, 0.0, 0.0, 1.0]
meshes:
  - id: m
    primitives:
      - type: box
        id: p
        dimensions:
          x: 1
          y: 1
          z: 1
        material: red
"""
        spec = parse_yaml(yaml_str)
        assert "red" in spec.materials
        assert spec.materials["red"].base_color == [1.0, 0.0, 0.0, 1.0]
        assert spec.meshes[0].primitives[0].material == "red"

    def test_v08_accepted(self):
        spec = parse_yaml('version: "0.8"\nunits: meters\n')
        assert spec.version == "0.8"

    def test_v07_accepted(self):
        spec = parse_yaml('version: "0.7"\nunits: meters\n')
        assert spec.version == "0.7"

    def test_duplicate_yaml_keys_rejected(self):
        yaml_str = """\
version: "0.7"
meshes:
  - id: m
    uv_roles:
      albedo:
        set: uv0
      albedo:
        set: uv1
    primitives:
      - type: box
        id: p
        dimensions:
          x: 1
          y: 1
          z: 1
"""
        with pytest.raises(ParseError, match="Invalid YAML"):
            parse_yaml(yaml_str)

    def test_duplicate_top_level_keys_rejected(self):
        yaml_str = """\
version: "0.7"
units: meters
units: meters
"""
        with pytest.raises(ParseError, match="Invalid YAML"):
            parse_yaml(yaml_str)

    def test_ruamel_parses_existing_specs(self, minimal_mesh_yaml):
        """Verify ruamel.yaml migration doesn't break existing parse behavior."""
        spec = parse_yaml(minimal_mesh_yaml)
        assert spec.version == "0.1"
        assert len(spec.meshes) == 1
        assert spec.meshes[0].primitives[0].type == "box"

    def test_v09_accepted(self):
        spec = parse_yaml('version: "0.9"\nunits: meters\n')
        assert spec.version == "0.9"

    def test_wedge_accepted_v09(self):
        yaml_str = """\
version: "0.9"
units: meters
meshes:
  - id: m
    primitives:
      - type: wedge
        id: w
        dimensions:
          x: 2.0
          y: 2.0
          z: 2.0
"""
        spec = parse_yaml(yaml_str)
        assert spec.meshes[0].primitives[0].type == "wedge"

    def test_wedge_rejected_v08(self):
        yaml_str = """\
version: "0.8"
units: meters
meshes:
  - id: m
    primitives:
      - type: wedge
        id: w
        dimensions:
          x: 2.0
          y: 2.0
          z: 2.0
"""
        # wedge is not in the Literal for v0.8 schema... actually it is now in the
        # Pydantic model. The version gate is in validation, not parsing.
        # So parsing should succeed, but validation should fail.
        from rigy.validation import validate

        spec = parse_yaml(yaml_str)
        from rigy.errors import ValidationError

        with pytest.raises(ValidationError, match="wedge.*requires version >= 0.9"):
            validate(spec)

    def test_schema_error_wrapped(self):
        yaml_str = 'version: "0.1"\nmeshes:\n  - id: m\n    primitives:\n      - type: invalid_type\n        id: p\n        dimensions:\n          x: 1\n'
        with pytest.raises(ParseError, match="Schema validation"):
            parse_yaml(yaml_str)
