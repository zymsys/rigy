"""Tests for rigy fmt / formatter."""

from __future__ import annotations

from click.testing import CliRunner

from rigy.cli import main
from rigy.formatter import format_yaml


class TestFormatYaml:
    def test_idempotent(self):
        source = """\
version: '0.11'
units: meters
meshes:
- id: m
  primitives:
  - type: box
    id: p
    dimensions:
      x: 1.0
      y: 2.0
      z: 3.0
"""
        first = format_yaml(source)
        second = format_yaml(first)
        assert first == second

    def test_rotation_euler_to_degrees(self):
        source = """\
version: '0.11'
units: meters
meshes:
- id: m
  primitives:
  - type: box
    id: p
    dimensions:
      x: 1.0
      y: 1.0
      z: 1.0
    transform:
      rotation_euler: [0.0, 1.5707963267948966, 0.0]
"""
        result = format_yaml(source)
        assert "rotation_euler" not in result
        assert "rotation_degrees" in result
        # ~90 degrees
        assert "90.0" in result

    def test_box_aliases_normalized(self):
        source = """\
version: '0.11'
units: meters
meshes:
- id: m
  primitives:
  - type: box
    id: p
    dimensions:
      width: 1.0
      height: 2.0
      depth: 3.0
"""
        result = format_yaml(source)
        assert "width" not in result
        assert "height" not in result
        assert "depth" not in result
        assert "x: 1.0" in result
        assert "y: 2.0" in result
        assert "z: 3.0" in result

    def test_key_ordering_top_level(self):
        source = """\
meshes:
- id: m
  primitives:
  - type: box
    id: p
    dimensions: {x: 1, y: 1, z: 1}
units: meters
version: '0.11'
"""
        result = format_yaml(source)
        lines = result.strip().split("\n")
        # version should come before units, units before meshes
        version_idx = next(i for i, l in enumerate(lines) if l.startswith("version"))
        units_idx = next(i for i, l in enumerate(lines) if l.startswith("units"))
        meshes_idx = next(i for i, l in enumerate(lines) if l.startswith("meshes"))
        assert version_idx < units_idx < meshes_idx

    def test_key_ordering_primitive(self):
        source = """\
version: '0.11'
units: meters
meshes:
- id: m
  primitives:
  - dimensions: {x: 1, y: 1, z: 1}
    id: p
    type: box
    material: mat1
"""
        result = format_yaml(source)
        lines = [l.strip().lstrip("- ") for l in result.strip().split("\n")]
        # Find the primitive lines
        type_idx = next(i for i, l in enumerate(lines) if l.startswith("type: box"))
        id_idx = next(i for i, l in enumerate(lines) if l.startswith("id: p"))
        dims_idx = next(i for i, l in enumerate(lines) if l.startswith("dimensions:"))
        mat_idx = next(i for i, l in enumerate(lines) if l.startswith("material:"))
        assert type_idx < id_idx < dims_idx < mat_idx

    def test_comments_preserved(self):
        source = """\
version: '0.11'  # spec version
units: meters
meshes:
- id: m  # main mesh
  primitives:
  - type: box
    id: p
    dimensions:
      x: 1.0
      y: 1.0
      z: 1.0
"""
        result = format_yaml(source)
        assert "# spec version" in result
        assert "# main mesh" in result

    def test_no_macro_expansion(self):
        source = """\
version: '0.11'
units: meters
params:
  size: 1.25
meshes:
- id: m
  primitives:
  - repeat:
      count: 2
      as: i
      body:
        type: box
        id: p${i}
        dimensions:
          x: $size
          y: 1.0
          z: 1.0
"""
        result = format_yaml(source)
        assert "repeat:" in result
        assert "params:" in result
        assert "$size" in result
        assert "${i}" in result

    def test_param_refs_untouched(self):
        source = """\
version: '0.11'
units: meters
params:
  angle: 1.57
meshes:
- id: m
  primitives:
  - type: box
    id: p
    dimensions:
      x: 1
      y: 1
      z: 1
    transform:
      rotation_euler: $angle
"""
        result = format_yaml(source)
        # $angle is a string reference, should be kept as rotation_degrees: $angle
        assert "rotation_degrees: $angle" in result
        assert "rotation_euler" not in result


class TestFmtCLI:
    def test_fmt_stdout(self, tmp_path):
        runner = CliRunner()
        input_file = tmp_path / "fmt_test.rigy.yaml"
        input_file.write_text(
            """\
meshes:
- id: m
  primitives:
  - type: box
    id: p
    dimensions: {x: 1, y: 1, z: 1}
units: meters
version: '0.11'
"""
        )

        result = runner.invoke(main, ["fmt", str(input_file)])
        assert result.exit_code == 0
        assert result.output.startswith("version:")

    def test_check_mode_unformatted(self, tmp_path):
        runner = CliRunner()
        input_file = tmp_path / "unformatted.rigy.yaml"
        input_file.write_text(
            """\
meshes:
- id: m
  primitives:
  - type: box
    id: p
    dimensions: {x: 1, y: 1, z: 1}
units: meters
version: '0.11'
"""
        )

        result = runner.invoke(main, ["fmt", str(input_file), "--check"])
        assert result.exit_code == 1

    def test_check_mode_formatted(self, tmp_path):
        runner = CliRunner()
        source = """\
version: '0.11'
units: meters
meshes:
- id: m
  primitives:
  - type: box
    id: p
    dimensions: {x: 1, y: 1, z: 1}
"""
        formatted = format_yaml(source)
        input_file = tmp_path / "formatted.rigy.yaml"
        input_file.write_text(formatted)

        result = runner.invoke(main, ["fmt", str(input_file), "--check"])
        assert result.exit_code == 0

    def test_in_place(self, tmp_path):
        runner = CliRunner()
        input_file = tmp_path / "inplace.rigy.yaml"
        original = """\
meshes:
- id: m
  primitives:
  - type: box
    id: p
    dimensions: {x: 1, y: 1, z: 1}
units: meters
version: '0.11'
"""
        input_file.write_text(original)

        result = runner.invoke(main, ["fmt", str(input_file), "--in-place"])
        assert result.exit_code == 0
        assert "Formatted:" in result.output

        new_content = input_file.read_text()
        assert new_content != original
        assert new_content.startswith("version:")

    def test_in_place_and_output_mutually_exclusive(self, tmp_path):
        runner = CliRunner()
        input_file = tmp_path / "test.rigy.yaml"
        input_file.write_text("version: '0.11'\nunits: meters\nmeshes: []\n")

        result = runner.invoke(
            main,
            ["fmt", str(input_file), "--in-place", "-o", str(tmp_path / "out.yaml")],
        )
        assert result.exit_code != 0
        assert "mutually exclusive" in result.output

    def test_in_place_and_check_mutually_exclusive(self, tmp_path):
        runner = CliRunner()
        input_file = tmp_path / "test.rigy.yaml"
        input_file.write_text("version: '0.11'\nunits: meters\nmeshes: []\n")

        result = runner.invoke(
            main,
            ["fmt", str(input_file), "--in-place", "--check"],
        )
        assert result.exit_code != 0
        assert "mutually exclusive" in result.output
