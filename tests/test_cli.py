"""Tests for CLI entry point."""

from click.testing import CliRunner

from rigy.cli import main


class TestCLI:
    def test_version_flag(self):
        runner = CliRunner()
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert "0.2.0" in result.output

    def test_compile_success(self, minimal_mesh_yaml, tmp_path):
        runner = CliRunner()
        input_file = tmp_path / "test.rigy.yaml"
        input_file.write_text(minimal_mesh_yaml)
        output_file = tmp_path / "test.glb"
        result = runner.invoke(main, ["compile", str(input_file), "-o", str(output_file)])
        assert result.exit_code == 0, result.output
        assert output_file.exists()
        assert "Compiled" in result.output

    def test_compile_default_output_path(self, minimal_mesh_yaml, tmp_path):
        runner = CliRunner()
        input_file = tmp_path / "model.rigy.yaml"
        input_file.write_text(minimal_mesh_yaml)
        result = runner.invoke(main, ["compile", str(input_file)])
        assert result.exit_code == 0, result.output
        assert (tmp_path / "model.glb").exists()

    def test_missing_file(self, tmp_path):
        runner = CliRunner()
        result = runner.invoke(main, ["compile", str(tmp_path / "missing.yaml")])
        assert result.exit_code != 0

    def test_invalid_spec(self, tmp_path):
        runner = CliRunner()
        input_file = tmp_path / "bad.rigy.yaml"
        input_file.write_text("version: '1.0'\n")
        result = runner.invoke(main, ["compile", str(input_file)])
        assert result.exit_code != 0
        assert "Error" in result.output

    def test_emit_expanded_yaml_success(self, tmp_path):
        runner = CliRunner()
        input_file = tmp_path / "expanded.rigy.yaml"
        expanded_file = tmp_path / "expanded.yaml"
        output_file = tmp_path / "expanded.glb"
        input_file.write_text(
            """\
version: "0.11"
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
            transform:
              rotation_euler: [0.0, 1.57079632679, 0.0]
"""
        )

        result = runner.invoke(
            main,
            [
                "compile",
                str(input_file),
                "-o",
                str(output_file),
                "--emit-expanded-yaml",
                str(expanded_file),
            ],
        )
        assert result.exit_code == 0, result.output
        assert expanded_file.exists()
        text = expanded_file.read_text()
        assert "params:" not in text
        assert "\n      - repeat:" not in text
        assert "\n          rotation_euler:" not in text
        assert "rotation_degrees" in text
        assert "from repeat:" in text
        assert "was $size" in text

    def test_emit_expanded_yaml_without_emit_on_error(self, tmp_path):
        runner = CliRunner()
        input_file = tmp_path / "bad_semantic.rigy.yaml"
        expanded_file = tmp_path / "expanded.yaml"
        input_file.write_text(
            """\
version: "0.11"
units: meters
meshes:
  - id: m
    primitives:
      - type: box
        id: dup
        dimensions: { x: 1, y: 1, z: 1 }
      - type: box
        id: dup
        dimensions: { x: 1, y: 1, z: 1 }
"""
        )

        result = runner.invoke(
            main,
            ["compile", str(input_file), "--emit-expanded-yaml", str(expanded_file)],
        )
        assert result.exit_code != 0
        assert not expanded_file.exists()

    def test_emit_expanded_yaml_with_emit_on_error(self, tmp_path):
        runner = CliRunner()
        input_file = tmp_path / "bad_semantic_emit.rigy.yaml"
        expanded_file = tmp_path / "expanded.yaml"
        input_file.write_text(
            """\
version: "0.11"
units: meters
meshes:
  - id: m
    primitives:
      - type: box
        id: dup
        dimensions: { x: 1, y: 1, z: 1 }
      - type: box
        id: dup
        dimensions: { x: 1, y: 1, z: 1 }
"""
        )

        result = runner.invoke(
            main,
            [
                "compile",
                str(input_file),
                "--emit-expanded-yaml",
                str(expanded_file),
                "--emit-on-error",
            ],
        )
        assert result.exit_code != 0
        assert expanded_file.exists()

    def test_emit_expanded_yaml_not_emitted_on_preprocess_failure(self, tmp_path):
        runner = CliRunner()
        input_file = tmp_path / "bad_preprocess.rigy.yaml"
        expanded_file = tmp_path / "expanded.yaml"
        input_file.write_text(
            """\
version: "0.11"
units: meters
meshes:
  - id: m
    primitives:
      - type: box
        id: p
        dimensions:
          x: $missing
          y: 1
          z: 1
"""
        )

        result = runner.invoke(
            main,
            [
                "compile",
                str(input_file),
                "--emit-expanded-yaml",
                str(expanded_file),
                "--emit-on-error",
            ],
        )
        assert result.exit_code != 0
        assert not expanded_file.exists()

    def test_emit_comments_modes(self, tmp_path):
        runner = CliRunner()
        input_file = tmp_path / "comments.rigy.yaml"
        drop_file = tmp_path / "expanded_drop.yaml"
        provenance_file = tmp_path / "expanded_provenance.yaml"
        output_file = tmp_path / "comments.glb"
        input_file.write_text(
            """\
version: "0.11"  # author version
units: meters
params:
  size: 1.0  # author param
meshes:
  - id: m  # author mesh
    primitives:
      - type: box
        id: p  # author id
        dimensions:
          x: $size
          y: 1
          z: 1
"""
        )

        drop_result = runner.invoke(
            main,
            [
                "compile",
                str(input_file),
                "-o",
                str(output_file),
                "--emit-expanded-yaml",
                str(drop_file),
                "--emit-comments",
                "drop",
            ],
        )
        assert drop_result.exit_code == 0, drop_result.output
        drop_text = drop_file.read_text()
        assert "was $size" not in drop_text
        assert "#" not in drop_text

        provenance_result = runner.invoke(
            main,
            [
                "compile",
                str(input_file),
                "-o",
                str(output_file),
                "--emit-expanded-yaml",
                str(provenance_file),
                "--emit-comments",
                "provenance",
            ],
        )
        assert provenance_result.exit_code == 0, provenance_result.output
        provenance_text = provenance_file.read_text()
        assert "was $size" in provenance_text
        assert "author version" not in provenance_text

    def test_emit_expanded_yaml_rejected_for_rigs(self, tmp_path):
        runner = CliRunner()
        rigs_file = tmp_path / "scene.rigs.yaml"
        rigs_file.write_text("rigs_version: '0.1'\nimports: {}\nscene:\n  base: x\n")

        result = runner.invoke(
            main,
            [
                "compile",
                str(rigs_file),
                "--emit-expanded-yaml",
                str(tmp_path / "expanded.yaml"),
            ],
        )
        assert result.exit_code != 0
        assert "only supported for .rigy.yaml inputs" in result.output
