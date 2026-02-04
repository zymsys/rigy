"""YAML loading and version checking for Rigy specs."""

from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError as PydanticValidationError
from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from rigy.errors import ParseError
from rigy.models import ResolvedAsset, RigySpec


def _make_yaml(preserve_comments: bool = False) -> YAML:
    """Create a ruamel.yaml safe loader that errors on duplicate keys."""
    yml = YAML(typ="rt" if preserve_comments else "safe")
    yml.allow_duplicate_keys = False
    return yml


def _read_source_text(source: str | Path) -> str:
    """Read source YAML content from path or treat input as raw YAML text."""
    if isinstance(source, Path):
        try:
            return source.read_text(encoding="utf-8")
        except OSError as e:
            raise ParseError(f"Cannot read file: {e}") from e
    return source


def load_yaml_data(source: str | Path, preserve_comments: bool = False) -> dict:
    """Load YAML and run top-level shape/version checks, before preprocessing."""
    text = _read_source_text(source)
    yml = _make_yaml(preserve_comments=preserve_comments)
    try:
        data = yml.load(text)
    except YAMLError as e:
        raise ParseError(f"Invalid YAML: {e}") from e

    if not isinstance(data, dict):
        raise ParseError("Top-level YAML value must be a mapping")

    version = data.get("version")
    if version is None:
        raise ParseError("Missing required field: version")
    _check_version(str(version))
    return data


def strip_yaml_comments(obj: object) -> None:
    """Remove ruamel round-trip comments recursively (best effort)."""
    comment_attr = getattr(obj, "ca", None)
    if comment_attr is not None:
        if hasattr(comment_attr, "comment"):
            comment_attr.comment = None
        items = getattr(comment_attr, "items", None)
        if items is not None and hasattr(items, "clear"):
            items.clear()
        if hasattr(comment_attr, "end"):
            comment_attr.end = []

    if isinstance(obj, dict):
        for value in obj.values():
            strip_yaml_comments(value)
    elif isinstance(obj, list):
        for item in obj:
            strip_yaml_comments(item)


def parse_preprocessed_yaml(
    source: str | Path,
    preserve_comments: bool = False,
    strip_comments_before_preprocess: bool = False,
    add_provenance_comments: bool = False,
) -> dict:
    """Load + preprocess YAML, optionally preserving/stripping comments."""
    data = load_yaml_data(source, preserve_comments=preserve_comments)
    if strip_comments_before_preprocess:
        strip_yaml_comments(data)

    from rigy.preprocessing import preprocess

    return preprocess(data, add_provenance_comments=add_provenance_comments)


def parse_yaml(source: str | Path) -> RigySpec:
    """Parse a Rigy YAML spec from a string or file path.

    Args:
        source: YAML string or path to a .rigy.yaml file.

    Returns:
        Parsed and schema-validated RigySpec.

    Raises:
        ParseError: On YAML syntax errors, schema violations, or version mismatches.
    """
    data = parse_preprocessed_yaml(source)

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

    if (major, minor) > (0, 11):
        raise ParseError(f"Unsupported version: {version!r} (latest supported is 0.11)")
