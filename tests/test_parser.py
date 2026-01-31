"""Tests for YAML parser."""

import warnings

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

    def test_unsupported_major_version(self):
        with pytest.raises(ParseError, match="Unsupported major version"):
            parse_yaml('version: "1.0"\nunits: meters\n')

    def test_newer_minor_version_warns(self):
        yaml_str = 'version: "0.3"\nunits: meters\n'
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            parse_yaml(yaml_str)
            assert len(w) == 1
            assert "newer" in str(w[0].message).lower()

    def test_v02_accepted_without_warning(self):
        yaml_str = 'version: "0.2"\nunits: meters\n'
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            spec = parse_yaml(yaml_str)
            assert len(w) == 0
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
