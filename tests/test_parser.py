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
            parse_yaml('version: "0.6"\nunits: meters\n')

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

    def test_schema_error_wrapped(self):
        yaml_str = 'version: "0.1"\nmeshes:\n  - id: m\n    primitives:\n      - type: invalid_type\n        id: p\n        dimensions:\n          x: 1\n'
        with pytest.raises(ParseError, match="Schema validation"):
            parse_yaml(yaml_str)
