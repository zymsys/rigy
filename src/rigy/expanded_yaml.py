"""Expanded YAML emission utilities for Rigy tooling."""

from __future__ import annotations

import math
from io import StringIO
from pathlib import Path
from typing import Literal

from ruamel.yaml import YAML

from rigy.parser import parse_preprocessed_yaml

EmitCommentsMode = Literal["keep", "drop", "provenance"]


def render_expanded_yaml(source: Path, emit_comments: EmitCommentsMode = "keep") -> str:
    """Render post-preprocessing Rigy YAML for inspection/debugging."""
    preserve_comments = emit_comments != "drop"
    strip_comments = emit_comments == "provenance"
    add_provenance_comments = emit_comments in {"keep", "provenance"}

    data = parse_preprocessed_yaml(
        source,
        preserve_comments=preserve_comments,
        strip_comments_before_preprocess=strip_comments,
        add_provenance_comments=add_provenance_comments,
    )
    _canonicalize_rotation_fields(data, add_provenance_comments=add_provenance_comments)

    yml = YAML(typ="rt")
    yml.allow_unicode = True
    yml.default_flow_style = False
    stream = StringIO()
    yml.dump(data, stream)
    return stream.getvalue()


def _canonicalize_rotation_fields(
    obj: object, add_provenance_comments: bool = False
) -> None:
    """Emit rotation as rotation_degrees and omit rotation_euler."""
    if isinstance(obj, dict):
        transform = obj.get("transform")
        if isinstance(transform, dict):
            _canonicalize_transform(transform, add_provenance_comments=add_provenance_comments)

        for value in obj.values():
            _canonicalize_rotation_fields(
                value,
                add_provenance_comments=add_provenance_comments,
            )
    elif isinstance(obj, list):
        for item in obj:
            _canonicalize_rotation_fields(
                item,
                add_provenance_comments=add_provenance_comments,
            )


def _canonicalize_transform(
    transform: dict, add_provenance_comments: bool = False
) -> None:
    rotation_degrees = transform.get("rotation_degrees")
    rotation_euler = transform.get("rotation_euler")

    if rotation_degrees is None and rotation_euler is None:
        return

    if rotation_degrees is None and rotation_euler is not None:
        converted = _to_degrees_triplet(rotation_euler)
        transform["rotation_degrees"] = converted
        if add_provenance_comments:
            _add_provenance_comment(
                transform,
                "rotation_degrees",
                "derived from rotation_euler (radians)",
            )

    # Enforce emit invariant: no rotation_euler field in expanded output.
    transform.pop("rotation_euler", None)


def _to_degrees_triplet(value: object) -> object:
    if isinstance(value, (list, tuple)) and len(value) == 3:
        converted = []
        for component in value:
            if isinstance(component, (int, float)):
                converted.append(math.degrees(float(component)))
            else:
                converted.append(component)
        return converted
    return value


def _add_provenance_comment(container: object, key_or_idx: object, comment: str) -> None:
    yaml_add_eol_comment = getattr(container, "yaml_add_eol_comment", None)
    if callable(yaml_add_eol_comment):
        try:
            yaml_add_eol_comment(comment, key_or_idx)
        except Exception:
            pass
