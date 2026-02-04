"""Click CLI entry point for the Rigy compiler."""

from __future__ import annotations

from pathlib import Path

import click

from rigy import __version__
from rigy.composition import bake_transforms as _bake_transforms
from rigy.composition import resolve_composition
from rigy.errors import RigyError
from rigy.expanded_yaml import render_expanded_yaml
from rigy.exporter import export_baked_gltf, export_gltf
from rigy.parser import parse_with_imports
from rigy.symmetry import expand_symmetry
from rigy.validation import validate, validate_composition


def _is_rigs_file(path: Path) -> bool:
    """Check if a path is a .rigs.yaml file."""
    name = path.name
    return name.endswith(".rigs.yaml") or name.endswith(".rigs.yml")


def _write_expanded_yaml(text: str, destination: str) -> None:
    """Write expanded YAML either to file path or stdout ('-')."""
    if destination == "-":
        click.echo(text, nl=False)
        return

    output_path = Path(destination)
    try:
        output_path.write_text(text, encoding="utf-8")
    except OSError as e:
        raise click.ClickException(f"Cannot write expanded YAML to {output_path}: {e}") from e


@click.group()
@click.version_option(version=__version__, prog_name="rigy")
def main() -> None:
    """Rigy — text-based specification language for rigged 3D assemblies."""


@main.command()
@click.argument("input_file", type=click.Path(exists=True, path_type=Path))
@click.option(
    "-o",
    "--output",
    type=click.Path(path_type=Path),
    default=None,
    help="Output GLB file path. Defaults to input name with .glb extension.",
)
@click.option(
    "--bake-transforms",
    is_flag=True,
    default=False,
    help="Bake instance transforms into geometry and bones.",
)
@click.option(
    "--pose",
    "pose_id",
    type=str,
    default=None,
    help="Evaluate a named pose from the spec.",
)
@click.option(
    "--bake-skin",
    is_flag=True,
    default=False,
    help="Bake skinning into geometry and remove skin from GLB.",
)
@click.option(
    "--emit-expanded-yaml",
    "emit_expanded_yaml",
    type=str,
    default=None,
    help="Emit post-preprocessing Rigy YAML to a path, or '-' for stdout.",
)
@click.option(
    "--emit-on-error",
    is_flag=True,
    default=False,
    help="Emit expanded YAML if preprocessing succeeds, even when later validation/export fails.",
)
@click.option(
    "--emit-comments",
    type=click.Choice(["keep", "drop", "provenance"]),
    default="keep",
    show_default=True,
    help="Comment mode for expanded YAML output.",
)
def compile(
    input_file: Path,
    output: Path | None,
    bake_transforms: bool = False,
    pose_id: str | None = None,
    bake_skin: bool = False,
    emit_expanded_yaml: str | None = None,
    emit_on_error: bool = False,
    emit_comments: str = "keep",
) -> None:
    """Compile a .rigy.yaml or .rigs.yaml spec to GLB."""
    if _is_rigs_file(input_file):
        if emit_expanded_yaml is not None:
            raise click.ClickException(
                "--emit-expanded-yaml is only supported for .rigy.yaml inputs"
            )
        _compile_rigs(input_file, output)
        return

    expanded_yaml_text: str | None = None
    if emit_expanded_yaml is not None:
        try:
            expanded_yaml_text = render_expanded_yaml(input_file, emit_comments=emit_comments)
        except RigyError as e:
            raise click.ClickException(str(e))

    if output is None:
        # Strip .rigy.yaml or .yaml and add .glb
        stem = input_file.name
        for suffix in [".rigy.yaml", ".rigy.yml", ".yaml", ".yml"]:
            if stem.endswith(suffix):
                stem = stem[: -len(suffix)]
                break
        output = input_file.parent / f"{stem}.glb"

    try:
        asset = parse_with_imports(input_file)
        asset.spec = expand_symmetry(asset.spec)
        validate(asset.spec)

        if pose_id is not None and bake_skin:
            # Baked skin export path
            pose = None
            for p in asset.spec.poses:
                if p.id == pose_id:
                    pose = p
                    break
            if pose is None:
                raise click.ClickException(f"Pose {pose_id!r} not found in spec")
            export_baked_gltf(asset.spec, pose, output, yaml_dir=input_file.parent)
        else:
            # Expand symmetry on imported assets too
            for ns, imported in asset.imported_assets.items():
                imported.spec = expand_symmetry(imported.spec)

            if asset.spec.instances:
                validate_composition(asset)

            composed = resolve_composition(asset)
            if bake_transforms:
                composed = _bake_transforms(composed)
            export_gltf(composed, output, yaml_dir=input_file.parent)
        if expanded_yaml_text is not None and emit_expanded_yaml is not None:
            _write_expanded_yaml(expanded_yaml_text, emit_expanded_yaml)
        click.echo(f"Compiled: {output}", err=emit_expanded_yaml == "-")
    except RigyError as e:
        if emit_on_error and expanded_yaml_text is not None and emit_expanded_yaml is not None:
            _write_expanded_yaml(expanded_yaml_text, emit_expanded_yaml)
        raise click.ClickException(str(e))


def _compile_rigs(input_file: Path, output: Path | None) -> None:
    """Compile a .rigs.yaml scene composition file to GLB."""
    from rigy.rigs_composition import compose_rigs
    from rigy.rigs_exporter import export_rigs_gltf
    from rigy.rigs_parser import parse_rigs
    from rigy.rigs_validation import validate_rigs

    if output is None:
        stem = input_file.name
        for suffix in [".rigs.yaml", ".rigs.yml"]:
            if stem.endswith(suffix):
                stem = stem[: -len(suffix)]
                break
        output = input_file.parent / f"{stem}.glb"

    try:
        asset = parse_rigs(input_file)
        validate_rigs(asset)
        composed = compose_rigs(asset)
        export_rigs_gltf(composed, output)
        click.echo(f"Compiled: {output}")
    except RigyError as e:
        raise click.ClickException(str(e))
