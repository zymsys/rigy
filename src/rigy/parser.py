"""YAML loading and version checking for Rigy specs."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError as PydanticValidationError

from rigy.errors import ParseError
from rigy.models import ResolvedAsset, RigySpec


def parse_yaml(source: str | Path) -> RigySpec:
    """Parse a Rigy YAML spec from a string or file path.

    Args:
        source: YAML string or path to a .rigy.yaml file.

    Returns:
        Parsed and schema-validated RigySpec.

    Raises:
        ParseError: On YAML syntax errors, schema violations, or version mismatches.
    """
    if isinstance(source, Path):
        try:
            text = source.read_text(encoding="utf-8")
        except OSError as e:
            raise ParseError(f"Cannot read file: {e}") from e
    else:
        text = source

    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise ParseError(f"Invalid YAML: {e}") from e

    if not isinstance(data, dict):
        raise ParseError("Top-level YAML value must be a mapping")

    # Version check before Pydantic parsing
    version = data.get("version")
    if version is None:
        raise ParseError("Missing required field: version")

    _check_version(str(version))

    try:
        return RigySpec(**data)
    except PydanticValidationError as e:
        raise ParseError(f"Schema validation failed:\n{e}") from e


def parse_with_imports(source: Path) -> ResolvedAsset:
    """Parse a Rigy file and recursively resolve its imports.

    Args:
        source: Path to the top-level .rigy.yaml file.

    Returns:
        ResolvedAsset tree with all imports resolved.

    Raises:
        ParseError: On circular imports, missing files, or parse errors.
    """
    return _resolve_imports(source, visited=set())


def _resolve_imports(source: Path, visited: set[Path]) -> ResolvedAsset:
    """Recursively resolve imports with cycle detection."""
    resolved_path = source.resolve()

    if resolved_path in visited:
        raise ParseError(f"Circular import detected: {source}")
    visited = visited | {resolved_path}  # new set to avoid mutation across branches

    spec = parse_yaml(source)

    imported_assets: dict[str, ResolvedAsset] = {}
    for namespace, import_def in spec.imports.items():
        import_path = source.parent / import_def.source
        if not import_path.exists():
            raise ParseError(f"Import {namespace!r}: source file not found: {import_path}")

        imported_asset = _resolve_imports(import_path, visited)

        # Parse contract if specified
        if import_def.contract:
            contract_path = source.parent / import_def.contract
            if not contract_path.exists():
                raise ParseError(f"Import {namespace!r}: contract file not found: {contract_path}")
            from rigy.contracts import parse_contract

            imported_asset.contract = parse_contract(contract_path)

        imported_assets[namespace] = imported_asset

    return ResolvedAsset(
        spec=spec,
        path=resolved_path,
        imported_assets=imported_assets,
    )


def _check_version(version: str) -> None:
    """Validate version string compatibility."""
    parts = version.split(".")
    if len(parts) != 2:
        raise ParseError(f"Invalid version format: {version!r}")

    try:
        major = int(parts[0])
        minor = int(parts[1])
    except ValueError:
        raise ParseError(f"Invalid version format: {version!r}")

    if (major, minor) > (0, 5):
        raise ParseError(f"Unsupported version: {version!r} (latest supported is 0.5)")
