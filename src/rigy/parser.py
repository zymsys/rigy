"""YAML loading and version checking for Rigy specs."""

from __future__ import annotations

import warnings
from pathlib import Path

import yaml
from pydantic import ValidationError as PydanticValidationError

from rigy.errors import ParseError
from rigy.models import RigySpec


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

    if major != 0:
        raise ParseError(f"Unsupported major version: {major} (expected 0)")

    if minor > 1:
        warnings.warn(
            f"Rigy spec version 0.{minor} is newer than supported 0.1; "
            "some features may be unsupported",
            stacklevel=3,
        )
