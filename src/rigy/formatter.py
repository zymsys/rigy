"""YAML formatter / normalizer for Rigy spec files."""

from __future__ import annotations

import math
from io import StringIO

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap

# Canonical key orderings for known mapping levels.
_TOP_LEVEL_ORDER = [
    "version",
    "units",
    "coordinate_system",
    "tessellation_profile",
    "params",
    "materials",
    "meshes",
    "armatures",
    "bindings",
    "symmetry",
    "skinning_solver",
    "poses",
    "anchors",
    "imports",
    "instances",
    "geometry_checks",
]

_PRIMITIVE_ORDER = [
    "type",
    "id",
    "name",
    "dimensions",
    "transform",
    "material",
    "surface",
    "tags",
]

_TRANSFORM_ORDER = [
    "translation",
    "rotation_degrees",
]

_BOX_DIMS_ORDER = ["x", "y", "z"]

_BONE_ORDER = ["id", "parent", "head", "tail", "roll"]

# Keys that identify a mapping as a particular level.
_LEVEL_DETECTORS: list[tuple[list[str], set[str]]] = [
    (_PRIMITIVE_ORDER, {"type", "id", "dimensions"}),
    (_TRANSFORM_ORDER, {"translation", "rotation_degrees"}),
    (_BONE_ORDER, {"id", "parent", "head", "tail"}),
]


def format_yaml(source: str) -> str:
    """Format a Rigy YAML string, returning canonical output.

    - Converts ``rotation_euler`` → ``rotation_degrees``.
    - Converts box ``width``/``height``/``depth`` → ``x``/``y``/``z``.
    - Reorders keys to canonical order at each known mapping level.
    - Preserves comments (best-effort via ruamel round-trip mode).
    - Does NOT expand macros (``repeat``, ``params``, ``$param`` refs).
    """
    yml = YAML(typ="rt")
    yml.allow_duplicate_keys = False
    data = yml.load(source)
    if not isinstance(data, (dict, CommentedMap)):
        return source

    _normalize(data, level="top")

    yml_out = YAML(typ="rt")
    yml_out.allow_unicode = True
    yml_out.default_flow_style = False
    stream = StringIO()
    yml_out.dump(data, stream)
    return stream.getvalue()


def _normalize(obj: object, level: str = "") -> None:
    """Recursively normalize a parsed YAML tree in place."""
    if isinstance(obj, dict):
        _normalize_mapping(obj, level)
    elif isinstance(obj, list):
        for item in obj:
            _normalize(item, level=_child_level(level))


def _normalize_mapping(mapping: dict, level: str) -> None:
    """Normalize a single mapping: field renames, then key reorder."""
    # --- Field renames ---
    _rename_rotation_euler(mapping)
    _rename_box_dims(mapping, level)

    # Recurse into children before reordering
    for key, value in list(mapping.items()):
        child_lvl = _infer_child_level(key, level)
        _normalize(value, level=child_lvl)

    # --- Key reordering ---
    order = _order_for_level(level, mapping)
    if order is not None:
        _reorder_keys(mapping, order)


def _rename_rotation_euler(mapping: dict) -> None:
    """Convert rotation_euler → rotation_degrees inside transform blocks."""
    transform = mapping.get("transform")
    if isinstance(transform, dict):
        euler = transform.get("rotation_euler")
        degrees = transform.get("rotation_degrees")
        if euler is not None and degrees is None:
            # Only convert if the value is a numeric list, not a $param ref
            if isinstance(euler, (list, tuple)) and all(isinstance(v, (int, float)) for v in euler):
                converted = [math.degrees(float(v)) for v in euler]
                transform["rotation_degrees"] = converted
            else:
                # Keep as-is but rename the key
                transform["rotation_degrees"] = euler
            del transform["rotation_euler"]

    # Also handle transform at the current mapping level itself
    # (for cases where we are directly inside a transform)
    if "rotation_euler" in mapping and "rotation_degrees" not in mapping:
        euler = mapping["rotation_euler"]
        if isinstance(euler, (list, tuple)) and all(isinstance(v, (int, float)) for v in euler):
            mapping["rotation_degrees"] = [math.degrees(float(v)) for v in euler]
        else:
            mapping["rotation_degrees"] = euler
        del mapping["rotation_euler"]


def _rename_box_dims(mapping: dict, level: str) -> None:
    """Convert width/height/depth → x/y/z for box primitives."""
    # Only apply to primitives with type: box
    prim_type = mapping.get("type")
    if prim_type != "box":
        return

    dims = mapping.get("dimensions")
    if not isinstance(dims, dict):
        return

    renames = [("width", "x"), ("height", "y"), ("depth", "z")]
    for old_key, new_key in renames:
        if old_key in dims and new_key not in dims:
            dims[new_key] = dims[old_key]
            del dims[old_key]


def _order_for_level(level: str, mapping: dict) -> list[str] | None:
    """Return the canonical key order for a mapping, or None."""
    if level == "top":
        return _TOP_LEVEL_ORDER
    if level == "primitive":
        return _PRIMITIVE_ORDER
    if level == "transform":
        return _TRANSFORM_ORDER
    if level == "bone":
        return _BONE_ORDER
    if level == "box_dims":
        return _BOX_DIMS_ORDER

    # Auto-detect level from keys
    keys = set(mapping.keys())
    for order, required in _LEVEL_DETECTORS:
        if required.issubset(keys):
            return order

    return None


def _infer_child_level(key: str, parent_level: str) -> str:
    """Infer the level tag for a child based on key name and parent."""
    if key == "meshes":
        return "mesh_list"
    if key == "primitives":
        return "primitive_list"
    if key == "armatures":
        return "armature_list"
    if key == "bones":
        return "bone_list"
    if key == "transform":
        return "transform"
    if key == "dimensions":
        return "dims"
    if key == "coordinate_system":
        return "coord_sys"
    return ""


def _child_level(level: str) -> str:
    """Return the level tag for list items based on parent level."""
    if level == "mesh_list":
        return "mesh"
    if level == "primitive_list":
        return "primitive"
    if level == "armature_list":
        return "armature"
    if level == "bone_list":
        return "bone"
    return ""


def _reorder_keys(mapping: dict, canonical: list[str]) -> None:
    """Reorder keys in a CommentedMap to follow canonical order.

    Keys not in the canonical list are placed after the canonical keys,
    preserving their relative order.
    """
    if not isinstance(mapping, CommentedMap):
        return

    canonical_set = set(canonical)
    all_keys = list(mapping.keys())

    # Save all entries
    entries = [(k, mapping[k]) for k in all_keys]

    # Save comment tokens for each key
    saved_comments: dict[str, object] = {}
    ca = getattr(mapping, "ca", None)
    if ca is not None:
        items = getattr(ca, "items", {})
        if isinstance(items, dict):
            for k in all_keys:
                if k in items:
                    saved_comments[k] = items[k]

    # Clear and re-insert in canonical order
    for k in all_keys:
        del mapping[k]

    # Canonical keys first (in order)
    for k in canonical:
        for key, value in entries:
            if key == k:
                mapping[k] = value
                break

    # Non-canonical keys after, in original order
    for key, value in entries:
        if key not in canonical_set:
            mapping[key] = value

    # Restore comments
    ca = getattr(mapping, "ca", None)
    if ca is not None:
        items = getattr(ca, "items", None)
        if items is not None and isinstance(items, dict):
            for k, comment in saved_comments.items():
                if k in mapping:
                    items[k] = comment
