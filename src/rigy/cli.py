"""Click CLI entry point for the Rigy compiler."""

from __future__ import annotations

from pathlib import Path

import click

from rigy import __version__
from rigy.errors import RigyError
from rigy.exporter import export_gltf
from rigy.parser import parse_yaml
from rigy.symmetry import expand_symmetry
from rigy.validation import validate


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
def compile(input_file: Path, output: Path | None) -> None:
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
        spec = parse_yaml(input_file)
        spec = expand_symmetry(spec)
        validate(spec)
        export_gltf(spec, output)
        click.echo(f"Compiled: {output}")
    except RigyError as e:
        raise click.ClickException(str(e))
