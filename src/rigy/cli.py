"""Click CLI entry point for the Rigy compiler."""

from __future__ import annotations

from pathlib import Path

import click

from rigy import __version__
from rigy.composition import bake_transforms as _bake_transforms
from rigy.composition import resolve_composition
from rigy.errors import RigyError
from rigy.exporter import export_gltf
from rigy.parser import parse_with_imports
from rigy.symmetry import expand_symmetry
from rigy.validation import validate, validate_composition


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
def compile(input_file: Path, output: Path | None, bake_transforms: bool = False) -> None:
    """Compile a .rigy.yaml spec to GLB."""
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

        # Expand symmetry on imported assets too
        for ns, imported in asset.imported_assets.items():
            imported.spec = expand_symmetry(imported.spec)

        if asset.spec.instances:
            validate_composition(asset)

        composed = resolve_composition(asset)
        if bake_transforms:
            composed = _bake_transforms(composed)
        export_gltf(composed, output, yaml_dir=input_file.parent)
        click.echo(f"Compiled: {output}")
    except RigyError as e:
        raise click.ClickException(str(e))
