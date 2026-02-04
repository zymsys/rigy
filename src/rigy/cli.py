"""Click CLI entry point for the Rigy compiler."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from rigy import __version__
from rigy.composition import bake_transforms as _bake_transforms
from rigy.composition import resolve_composition
from rigy.errors import RigyError
from rigy.expanded_yaml import render_expanded_yaml
from rigy.exporter import export_baked_gltf, export_gltf
from rigy.manifest import build_manifest
from rigy.inspection import (
    has_failed_intent_checks,
    inspect_spec,
    render_text as render_inspection_text,
    validate_selected_primitive_ids,
)
from rigy.parser import parse_with_imports
from rigy.symmetry import expand_symmetry
from rigy.validation import validate, validate_composition
from rigy.warning_policy import WarningPolicy, parse_code_list


def _build_warning_policy(
    warn_as_error: str | None, suppress_warning: str | None
) -> WarningPolicy | None:
    """Parse CLI warning options into a WarningPolicy, or None if unset."""
    if warn_as_error is None and suppress_warning is None:
        return None
    try:
        wae = parse_code_list(warn_as_error) if warn_as_error else frozenset()
        sup = parse_code_list(suppress_warning) if suppress_warning else frozenset()
    except ValueError as e:
        raise click.ClickException(str(e)) from e
    return WarningPolicy(warn_as_error=wae, suppress=sup)


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
@click.option(
    "--warn-as-error",
    "warn_as_error",
    type=str,
    default=None,
    help="Comma-separated W-codes to treat as errors (e.g. W01,W02).",
)
@click.option(
    "--suppress-warning",
    "suppress_warning",
    type=str,
    default=None,
    help="Comma-separated W-codes to suppress (e.g. W03).",
)
@click.option(
    "--emit-manifest",
    "emit_manifest",
    type=click.Path(path_type=Path),
    default=None,
    help="Write a JSON build manifest to this path after successful compile.",
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
    warn_as_error: str | None = None,
    suppress_warning: str | None = None,
    emit_manifest: Path | None = None,
) -> None:
    """Compile a .rigy.yaml or .rigs.yaml spec to GLB."""
    warning_policy = _build_warning_policy(warn_as_error, suppress_warning)

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
        validate(asset.spec, warning_policy=warning_policy)

        if pose_id is not None and bake_skin:
            # Baked skin export path
            pose = None
            for p in asset.spec.poses:
                if p.id == pose_id:
                    pose = p
                    break
            if pose is None:
                raise click.ClickException(f"Pose {pose_id!r} not found in spec")
            export_baked_gltf(
                asset.spec,
                pose,
                output,
                yaml_dir=input_file.parent,
                warning_policy=warning_policy,
            )
        else:
            # Expand symmetry on imported assets too
            for ns, imported in asset.imported_assets.items():
                imported.spec = expand_symmetry(imported.spec)

            if asset.spec.instances:
                validate_composition(asset)

            composed = resolve_composition(asset)
            if bake_transforms:
                composed = _bake_transforms(composed)
            export_gltf(
                composed,
                output,
                yaml_dir=input_file.parent,
                warning_policy=warning_policy,
            )
        if expanded_yaml_text is not None and emit_expanded_yaml is not None:
            _write_expanded_yaml(expanded_yaml_text, emit_expanded_yaml)
        if emit_manifest is not None:
            expanded_yaml_path = (
                Path(emit_expanded_yaml)
                if emit_expanded_yaml is not None and emit_expanded_yaml != "-"
                else None
            )
            manifest = build_manifest(
                input_path=input_file,
                output_path=output,
                expanded_yaml_path=expanded_yaml_path,
                command_args=sys.argv[1:],
            )
            emit_manifest.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        click.echo(f"Compiled: {output}", err=emit_expanded_yaml == "-")
    except RigyError as e:
        if emit_on_error and expanded_yaml_text is not None and emit_expanded_yaml is not None:
            _write_expanded_yaml(expanded_yaml_text, emit_expanded_yaml)
        raise click.ClickException(str(e))


@main.command()
@click.argument("input_file", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    show_default=True,
    help="Inspection output format.",
)
@click.option(
    "--expanded",
    is_flag=True,
    default=False,
    help="Also emit expanded YAML diagnostics.",
)
@click.option(
    "--primitive",
    "primitive_ids",
    multiple=True,
    help="Restrict output to selected primitive id(s). May be repeated.",
)
@click.option(
    "--pairwise-gaps",
    is_flag=True,
    default=False,
    help="Compute pairwise AABB gap/overlap diagnostics.",
)
@click.option(
    "--intent-checks",
    is_flag=True,
    default=False,
    help="Evaluate intent checks when configured (tooling-level).",
)
@click.option(
    "--fail-on-intent",
    is_flag=True,
    default=False,
    help="Exit with code 3 if any intent check fails.",
)
@click.option(
    "--warn-as-error",
    "warn_as_error",
    type=str,
    default=None,
    help="Comma-separated W-codes to treat as errors (e.g. W01,W02).",
)
@click.option(
    "--suppress-warning",
    "suppress_warning",
    type=str,
    default=None,
    help="Comma-separated W-codes to suppress (e.g. W03).",
)
def inspect(
    input_file: Path,
    output_format: str = "text",
    expanded: bool = False,
    primitive_ids: tuple[str, ...] = (),
    pairwise_gaps: bool = False,
    intent_checks: bool = False,
    fail_on_intent: bool = False,
    warn_as_error: str | None = None,
    suppress_warning: str | None = None,
) -> None:
    """Inspect Rigy geometry without exporting GLB."""
    warning_policy = _build_warning_policy(warn_as_error, suppress_warning)

    if _is_rigs_file(input_file):
        raise click.UsageError("inspect currently supports only .rigy.yaml inputs")
    if fail_on_intent and not intent_checks:
        raise click.UsageError("--fail-on-intent requires --intent-checks")

    expanded_yaml_text: str | None = None
    if expanded:
        try:
            expanded_yaml_text = render_expanded_yaml(input_file)
        except RigyError as e:
            raise click.ClickException(str(e))

    try:
        asset = parse_with_imports(input_file)
        asset.spec = expand_symmetry(asset.spec)
        validate(asset.spec, warning_policy=warning_policy)

        for imported in asset.imported_assets.values():
            imported.spec = expand_symmetry(imported.spec)
        if asset.spec.instances:
            validate_composition(asset)

        selected_primitive_ids = set(primitive_ids)
        unknown_ids = validate_selected_primitive_ids(asset.spec, selected_primitive_ids)
        if unknown_ids:
            raise click.UsageError(
                "Unknown primitive id(s): " + ", ".join(repr(prim_id) for prim_id in unknown_ids)
            )

        payload = inspect_spec(
            asset.spec,
            selected_primitive_ids=selected_primitive_ids or None,
            pairwise_gaps=pairwise_gaps,
            include_intent_checks=intent_checks,
        )

        if expanded_yaml_text is not None:
            payload["expanded_yaml"] = expanded_yaml_text

        if output_format == "json":
            output_text = json.dumps(payload, indent=2)
            click.echo(output_text)
        else:
            output_text = render_inspection_text(payload, expanded_yaml=expanded_yaml_text)
            click.echo(output_text, nl=False)

        if fail_on_intent and has_failed_intent_checks(payload):
            raise click.exceptions.Exit(3)
    except RigyError as e:
        raise click.ClickException(str(e))


@main.command()
@click.argument("input_file", type=click.Path(exists=True, path_type=Path))
@click.option(
    "-o",
    "--output",
    type=click.Path(path_type=Path),
    default=None,
    help="Write formatted output to this file instead of stdout.",
)
@click.option(
    "--in-place",
    is_flag=True,
    default=False,
    help="Overwrite the input file with formatted output.",
)
@click.option(
    "--check",
    is_flag=True,
    default=False,
    help="Exit with code 1 if the file would change (CI mode). No output is written.",
)
def fmt(
    input_file: Path,
    output: Path | None = None,
    in_place: bool = False,
    check: bool = False,
) -> None:
    """Format a .rigy.yaml file to canonical style."""
    from rigy.formatter import format_yaml

    if in_place and output is not None:
        raise click.UsageError("--in-place and -o/--output are mutually exclusive")
    if in_place and check:
        raise click.UsageError("--in-place and --check are mutually exclusive")

    try:
        source = input_file.read_text(encoding="utf-8")
    except OSError as e:
        raise click.ClickException(f"Cannot read {input_file}: {e}") from e

    formatted = format_yaml(source)

    if check:
        if formatted != source:
            raise SystemExit(1)
        return

    if in_place:
        input_file.write_text(formatted, encoding="utf-8")
        click.echo(f"Formatted: {input_file}")
    elif output is not None:
        output.write_text(formatted, encoding="utf-8")
        click.echo(f"Formatted: {output}")
    else:
        click.echo(formatted, nl=False)


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
