"""Parse .rigs.yaml scene composition files."""

from __future__ import annotations

import re
from pathlib import Path

from pydantic import ValidationError as PydanticValidationError
from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from rigy.errors import ParseError
from rigy.parser import parse_with_imports
from rigy.rigs_models import ResolvedRigsAsset, RigsSpec

_VALID_ROTATE = frozenset({"0deg", "90deg", "180deg", "270deg"})
_NUDGE_PATTERN = re.compile(r"^-?\d+(\.\d+)?(cm|m|in|ft)?$")


def _make_yaml() -> YAML:
    yml = YAML(typ="safe")
    yml.allow_duplicate_keys = False
    return yml


def parse_rigs(source: Path) -> ResolvedRigsAsset:
    """Parse a .rigs.yaml file and resolve all Rigy imports.

    Args:
        source: Path to the .rigs.yaml file.

    Returns:
        ResolvedRigsAsset with parsed spec and resolved imports.

    Raises:
        ParseError: On YAML errors, schema violations, or import failures.
    """
    try:
        text = source.read_text(encoding="utf-8")
    except OSError as e:
        raise ParseError(f"Cannot read file: {e}") from e

    yml = _make_yaml()
    try:
        data = yml.load(text)
    except YAMLError as e:
        raise ParseError(f"Invalid YAML: {e}") from e

    if not isinstance(data, dict):
        raise ParseError("Top-level YAML value must be a mapping")

    version = data.get("rigs_version")
    if version is None:
        raise ParseError("Missing required field: rigs_version")
    if str(version) != "0.1":
        raise ParseError(f"Unsupported rigs_version: {version!r} (only '0.1' is supported)")

    try:
        spec = RigsSpec(**data)
    except PydanticValidationError as e:
        raise ParseError(f"Schema validation failed:\n{e}") from e

    # Validate tokens at parse time
    _validate_tokens(spec)

    # Resolve Rigy imports
    resolved_imports = {}
    base_dir = source.parent
    for alias, rel_path in spec.imports.items():
        import_path = base_dir / rel_path
        if not import_path.exists():
            raise ParseError(f"Import {alias!r}: source file not found: {import_path}")
        resolved_imports[alias] = parse_with_imports(import_path)

    return ResolvedRigsAsset(
        spec=spec,
        path=source.resolve(),
        resolved_imports=resolved_imports,
    )


def _validate_tokens(spec: RigsSpec) -> None:
    """Validate rotate and nudge tokens in all placements."""
    if spec.scene.children:
        for child in spec.scene.children:
            _validate_child_tokens(child)


def _validate_child_tokens(child) -> None:
    """Recursively validate tokens in a scene child."""
    rotate = child.place.rotate
    if rotate not in _VALID_ROTATE:
        raise ParseError(
            f"Instance {child.id!r}: invalid rotate value {rotate!r}. "
            f"Must be one of: {', '.join(sorted(_VALID_ROTATE))}"
        )

    if child.place.nudge is not None:
        for axis, value in [
            ("north", child.place.nudge.north),
            ("east", child.place.nudge.east),
            ("up", child.place.nudge.up),
        ]:
            if not _NUDGE_PATTERN.match(str(value)):
                raise ParseError(
                    f"Instance {child.id!r}: invalid nudge.{axis} value {value!r}. "
                    f"Expected format: number with optional unit (cm, m, in, ft)"
                )

    if child.children:
        for grandchild in child.children:
            _validate_child_tokens(grandchild)
