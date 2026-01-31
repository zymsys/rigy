"""Tests for CLI entry point."""

from click.testing import CliRunner

from rigy.cli import main


class TestCLI:
    def test_version_flag(self):
        runner = CliRunner()
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output

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
