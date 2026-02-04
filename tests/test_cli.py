"""Tests for CLI entry point."""

import json

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

    def test_inspect_text_success(self, tmp_path):
        runner = CliRunner()
        input_file = tmp_path / "inspect_text.rigy.yaml"
        input_file.write_text(
            """\
version: "0.11"
units: meters
meshes:
  - id: m
    primitives:
      - type: box
        id: wall
        dimensions: { x: 2, y: 4, z: 6 }
"""
        )

        result = runner.invoke(main, ["inspect", str(input_file)])
        assert result.exit_code == 0, result.output
        assert "summary:" in result.output
        assert "primitive_count: 1" in result.output
        assert "id: wall" in result.output
        assert "surface_key: +x" in result.output

    def test_inspect_json_with_pairwise_gaps(self, tmp_path):
        runner = CliRunner()
        input_file = tmp_path / "inspect_pairs.rigy.yaml"
        input_file.write_text(
            """\
version: "0.11"
units: meters
meshes:
  - id: m
    primitives:
      - type: box
        id: a
        dimensions: { x: 1, y: 1, z: 1 }
      - type: box
        id: b
        dimensions: { x: 1, y: 1, z: 1 }
        transform: { translation: [2, 0, 0] }
"""
        )

        result = runner.invoke(
            main,
            ["inspect", str(input_file), "--format", "json", "--pairwise-gaps"],
        )
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["summary"]["mesh_count"] == 1
        assert payload["summary"]["primitive_count"] == 2
        assert [p["id"] for p in payload["primitives"]] == ["a", "b"]
        assert len(payload["faces"]) == 12
        assert len(payload["pairs"]) == 1
        gap = payload["pairs"][0]["gap"]
        assert gap["x"] == 1.0
        assert gap["y"] == -1.0
        assert gap["z"] == -1.0
        assert gap["overall"] == 1.0

    def test_inspect_unknown_primitive_filter(self, tmp_path):
        runner = CliRunner()
        input_file = tmp_path / "inspect_filter.rigy.yaml"
        input_file.write_text(
            """\
version: "0.11"
units: meters
meshes:
  - id: m
    primitives:
      - type: box
        id: a
        dimensions: { x: 1, y: 1, z: 1 }
"""
        )

        result = runner.invoke(
            main,
            ["inspect", str(input_file), "--primitive", "missing"],
        )
        assert result.exit_code == 2
        assert "Unknown primitive id(s)" in result.output

    def test_inspect_fail_on_intent_requires_intent_checks(self, tmp_path):
        runner = CliRunner()
        input_file = tmp_path / "inspect_intent.rigy.yaml"
        input_file.write_text(
            """\
version: "0.11"
units: meters
meshes:
  - id: m
    primitives:
      - type: box
        id: a
        dimensions: { x: 1, y: 1, z: 1 }
"""
        )

        result = runner.invoke(main, ["inspect", str(input_file), "--fail-on-intent"])
        assert result.exit_code == 2
        assert "--fail-on-intent requires --intent-checks" in result.output

    def test_inspect_rejects_rigs_files(self, tmp_path):
        runner = CliRunner()
        rigs_file = tmp_path / "scene.rigs.yaml"
        rigs_file.write_text("rigs_version: '0.1'\nimports: {}\nscene:\n  base: x\n")

        result = runner.invoke(main, ["inspect", str(rigs_file)])
        assert result.exit_code == 2
        assert "supports only .rigy.yaml inputs" in result.output

    def test_inspect_schema_version_in_json(self, tmp_path):
        runner = CliRunner()
        input_file = tmp_path / "inspect_sv.rigy.yaml"
        input_file.write_text(
            """\
version: "0.11"
units: meters
meshes:
  - id: m
    primitives:
      - type: box
        id: p
        dimensions: { x: 1, y: 1, z: 1 }
"""
        )

        result = runner.invoke(
            main,
            ["inspect", str(input_file), "--format", "json"],
        )
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["inspect_schema_version"] == 1

    def test_inspect_schema_version_in_text(self, tmp_path):
        runner = CliRunner()
        input_file = tmp_path / "inspect_sv_text.rigy.yaml"
        input_file.write_text(
            """\
version: "0.11"
units: meters
meshes:
  - id: m
    primitives:
      - type: box
        id: p
        dimensions: { x: 1, y: 1, z: 1 }
"""
        )

        result = runner.invoke(main, ["inspect", str(input_file)])
        assert result.exit_code == 0, result.output
        assert "inspect_schema_version: 1" in result.output

    def test_inspect_json_with_expanded_yaml(self, tmp_path):
        runner = CliRunner()
        input_file = tmp_path / "inspect_expanded.rigy.yaml"
        input_file.write_text(
            """\
version: "0.11"
units: meters
params:
  size: 1.25
meshes:
  - id: m
    primitives:
      - type: box
        id: p
        dimensions:
          x: $size
          y: 1
          z: 1
"""
        )

        result = runner.invoke(
            main,
            ["inspect", str(input_file), "--format", "json", "--expanded"],
        )
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert "expanded_yaml" in payload
        assert "params:" not in payload["expanded_yaml"]
        assert "x: 1.25" in payload["expanded_yaml"]

    def test_warn_as_error_exits_nonzero(self, tmp_path):
        """A spec triggering W03 should fail with --warn-as-error W03."""
        runner = CliRunner()
        input_file = tmp_path / "w03.rigy.yaml"
        input_file.write_text(
            """\
version: "0.6"
units: meters
meshes:
  - id: m
    primitives:
      - type: box
        id: p
        dimensions: { x: 1, y: 1, z: 1 }
armatures:
  - id: arm
    bones:
      - id: root
        parent: none
        head: [1, 0, 0]
        tail: [1, 1, 0]
        roll: 0
bindings:
  - mesh_id: m
    armature_id: arm
    weights:
      - primitive_id: p
        bones:
          - bone_id: root
            weight: 1.0
"""
        )
        output_file = tmp_path / "w03.glb"
        result = runner.invoke(
            main,
            ["compile", str(input_file), "-o", str(output_file), "--warn-as-error", "W03"],
        )
        assert result.exit_code != 0
        assert "W03" in result.output

    def test_suppress_warning_silences(self, tmp_path):
        """A spec triggering W03 should succeed silently with --suppress-warning W03."""
        runner = CliRunner()
        input_file = tmp_path / "w03_suppress.rigy.yaml"
        input_file.write_text(
            """\
version: "0.6"
units: meters
meshes:
  - id: m
    primitives:
      - type: box
        id: p
        dimensions: { x: 1, y: 1, z: 1 }
armatures:
  - id: arm
    bones:
      - id: root
        parent: none
        head: [1, 0, 0]
        tail: [1, 1, 0]
        roll: 0
bindings:
  - mesh_id: m
    armature_id: arm
    weights:
      - primitive_id: p
        bones:
          - bone_id: root
            weight: 1.0
"""
        )
        output_file = tmp_path / "w03_suppress.glb"
        result = runner.invoke(
            main,
            [
                "compile",
                str(input_file),
                "-o",
                str(output_file),
                "--suppress-warning",
                "W03",
            ],
        )
        assert result.exit_code == 0, result.output

    def test_invalid_warning_code_rejected(self, tmp_path):
        runner = CliRunner()
        input_file = tmp_path / "valid.rigy.yaml"
        input_file.write_text(
            """\
version: "0.11"
units: meters
meshes:
  - id: m
    primitives:
      - type: box
        id: p
        dimensions: { x: 1, y: 1, z: 1 }
"""
        )
        result = runner.invoke(
            main,
            ["compile", str(input_file), "--warn-as-error", "W99"],
        )
        assert result.exit_code != 0
        assert "Unknown warning code" in result.output

    def test_emit_manifest_creates_valid_json(self, minimal_mesh_yaml, tmp_path):
        runner = CliRunner()
        input_file = tmp_path / "manifest_test.rigy.yaml"
        input_file.write_text(minimal_mesh_yaml)
        output_file = tmp_path / "manifest_test.glb"
        manifest_file = tmp_path / "manifest.json"

        result = runner.invoke(
            main,
            [
                "compile",
                str(input_file),
                "-o",
                str(output_file),
                "--emit-manifest",
                str(manifest_file),
            ],
        )
        assert result.exit_code == 0, result.output
        assert manifest_file.exists()

        manifest = json.loads(manifest_file.read_text())
        assert manifest["manifest_version"] == 1
        assert manifest["tool"]["name"] == "rigy"
        assert "sha256" in manifest["input"]
        assert "sha256" in manifest["output"]
        assert len(manifest["output"]["sha256"]) == 64

    def test_manifest_not_written_on_failure(self, tmp_path):
        runner = CliRunner()
        input_file = tmp_path / "bad.rigy.yaml"
        input_file.write_text("version: '1.0'\n")
        manifest_file = tmp_path / "manifest.json"

        result = runner.invoke(
            main,
            ["compile", str(input_file), "--emit-manifest", str(manifest_file)],
        )
        assert result.exit_code != 0
        assert not manifest_file.exists()

    def test_manifest_includes_expanded_yaml(self, tmp_path):
        runner = CliRunner()
        input_file = tmp_path / "manifest_exp.rigy.yaml"
        input_file.write_text(
            """\
version: "0.11"
units: meters
params:
  size: 1.0
meshes:
  - id: m
    primitives:
      - type: box
        id: p
        dimensions:
          x: $size
          y: 1
          z: 1
"""
        )
        output_file = tmp_path / "manifest_exp.glb"
        expanded_file = tmp_path / "expanded.yaml"
        manifest_file = tmp_path / "manifest.json"

        result = runner.invoke(
            main,
            [
                "compile",
                str(input_file),
                "-o",
                str(output_file),
                "--emit-expanded-yaml",
                str(expanded_file),
                "--emit-manifest",
                str(manifest_file),
            ],
        )
        assert result.exit_code == 0, result.output
        manifest = json.loads(manifest_file.read_text())
        assert "expanded_yaml" in manifest
        assert "sha256" in manifest["expanded_yaml"]
