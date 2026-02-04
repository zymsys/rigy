"""v0.10–v0.11 preprocessing: repeat/params, AABB, and macro expansion.

Operates on raw dicts/lists/scalars from ruamel.yaml, before Pydantic
model construction. Never imports Pydantic models.
"""

from __future__ import annotations

import copy
import math
import re

from rigy.errors import ParseError

_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_PARAM_REF_RE = re.compile(r"^\$([A-Za-z_][A-Za-z0-9_]*)$")
_EMBEDDED_PARAM_RE = re.compile(r"\$[A-Za-z_][A-Za-z0-9_]*")
_INDEX_TOKEN_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")
_UNRESOLVED_TOKEN_RE = re.compile(r"\$\{[A-Za-z_][A-Za-z0-9_]*\}")
_MISSING = object()


def preprocess(data: dict, add_provenance_comments: bool = False) -> dict:
    """Entry point. Deep-copies data, expands repeats, substitutes params,
    strips the params key, checks for unresolved tokens, then expands
    AABB and macros."""
    data = copy.deepcopy(data)
    geometry_checks = data.pop("geometry_checks", _MISSING)
    _expand_repeats(data, add_provenance_comments=add_provenance_comments)

    # Validate and substitute params
    raw_params = data.get("params")
    if raw_params is not None:
        params = _validate_params(raw_params)
        _substitute_params(data, params, add_provenance_comments=add_provenance_comments)
        del data["params"]
    else:
        # Even without params, check for stray $param references
        _substitute_params(data, {}, add_provenance_comments=add_provenance_comments)

    _check_no_unresolved_tokens(data)
    _expand_aabb(data, add_provenance_comments=add_provenance_comments)
    _expand_macros(data, add_provenance_comments=add_provenance_comments)
    if geometry_checks is not _MISSING:
        data["geometry_checks"] = geometry_checks
    return data


def _add_provenance_comment(container: object, key_or_idx: object, comment: str) -> None:
    """Best-effort helper for ruamel comment-capable containers."""
    yaml_add_eol_comment = getattr(container, "yaml_add_eol_comment", None)
    if callable(yaml_add_eol_comment):
        try:
            yaml_add_eol_comment(comment, key_or_idx)
        except Exception:
            # Keep preprocessing behavior stable even if comment attachment fails.
            pass


# ---------------------------------------------------------------------------
# Repeat expansion (v0.10)
# ---------------------------------------------------------------------------


def _expand_repeats(obj: object, add_provenance_comments: bool = False) -> None:
    """Recursive walk. In any list, detect repeat macros and expand in-place."""
    if isinstance(obj, dict):
        for value in obj.values():
            _expand_repeats(value, add_provenance_comments=add_provenance_comments)
    elif isinstance(obj, list):
        i = 0
        while i < len(obj):
            item = obj[i]
            if isinstance(item, dict) and list(item.keys()) == ["repeat"]:
                block = item["repeat"]
                count, token_name, body = _validate_repeat_block(block)
                expanded = []
                for idx in range(count):
                    instance = copy.deepcopy(body)
                    _substitute_index_token(instance, token_name, idx)
                    if add_provenance_comments and isinstance(instance, dict):
                        comment_key = "id" if "id" in instance else next(iter(instance), None)
                        if comment_key is not None:
                            _add_provenance_comment(
                                instance,
                                comment_key,
                                f"from repeat: as={token_name} index={idx}",
                            )
                    expanded.append(instance)
                obj[i : i + 1] = expanded
                # Recurse into newly expanded items
                for e in expanded:
                    _expand_repeats(e, add_provenance_comments=add_provenance_comments)
                i += len(expanded)
            else:
                _expand_repeats(item, add_provenance_comments=add_provenance_comments)
                i += 1


def _validate_repeat_block(block: object) -> tuple[int, str, dict]:
    """Validate repeat block structure. Returns (count, as_name, body)."""
    if not isinstance(block, dict):
        raise ParseError("V64: repeat value must be a mapping")

    allowed_keys = {"count", "as", "body"}
    extra = set(block.keys()) - allowed_keys
    if extra:
        raise ParseError(f"V64: unexpected keys in repeat block: {extra}")

    # count
    if "count" not in block:
        raise ParseError("V64: repeat block missing required key 'count'")
    count = block["count"]
    if not isinstance(count, int) or isinstance(count, bool):
        raise ParseError(f"V62: repeat.count must be an integer, got {type(count).__name__}")
    if count < 0:
        raise ParseError(f"V62: repeat.count must be >= 0, got {count}")

    # as
    if "as" not in block:
        raise ParseError("V64: repeat block missing required key 'as'")
    as_name = block["as"]
    if not isinstance(as_name, str) or not _IDENTIFIER_RE.match(as_name):
        raise ParseError(f"V63: repeat.as must be a valid identifier, got {as_name!r}")

    # body
    if "body" not in block:
        raise ParseError("V64: repeat block missing required key 'body'")
    body = block["body"]
    if not isinstance(body, dict):
        raise ParseError("V64: repeat.body must be a single object (mapping)")

    return count, as_name, body


def _substitute_index_token(obj: object, token_name: str, index: int) -> object:
    """Recursive substitution of ${token_name} with index value.

    Returns the substituted value (needed for scalar replacement in lists).
    Mutates dicts and lists in-place where possible.
    """
    token = "${" + token_name + "}"

    if isinstance(obj, str):
        if obj == token:
            return index
        if token in obj:
            return obj.replace(token, str(index))
        return obj
    elif isinstance(obj, dict):
        for key in list(obj.keys()):
            obj[key] = _substitute_index_token(obj[key], token_name, index)
        return obj
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            obj[i] = _substitute_index_token(item, token_name, index)
        return obj
    return obj


# ---------------------------------------------------------------------------
# Params substitution (v0.10)
# ---------------------------------------------------------------------------


def _validate_params(raw: object) -> dict:
    """Validate params mapping: keys are identifiers, values are scalars."""
    if not isinstance(raw, dict):
        raise ParseError("V58: params must be a mapping")

    params = {}
    for key, value in raw.items():
        if not isinstance(key, str) or not _IDENTIFIER_RE.match(key):
            raise ParseError(f"V58: invalid param identifier: {key!r}")
        if isinstance(value, bool):
            params[key] = value
        elif isinstance(value, (int, float, str)):
            params[key] = value
        else:
            raise ParseError(
                f"V58: param {key!r} has non-scalar value of type {type(value).__name__}"
            )
    return params


def _substitute_params(
    obj: object,
    params: dict,
    _skip_params_key: bool = True,
    add_provenance_comments: bool = False,
) -> object:
    """Recursive walk. Substitute $param references with values.

    Returns the substituted value. Mutates dicts/lists in-place.
    """
    if isinstance(obj, str):
        m = _PARAM_REF_RE.match(obj)
        if m:
            name = m.group(1)
            if name not in params:
                raise ParseError(f"V59: unknown param reference: ${name}")
            return params[name]
        # Check for embedded $param (prohibited)
        if _EMBEDDED_PARAM_RE.search(obj):
            # But skip if it looks like an index token ${...}
            cleaned = _INDEX_TOKEN_RE.sub("", obj)
            if _EMBEDDED_PARAM_RE.search(cleaned):
                raise ParseError(f"V60: invalid param usage (not whole-scalar): {obj!r}")
        return obj
    elif isinstance(obj, dict):
        for key in list(obj.keys()):
            if _skip_params_key and key == "params":
                continue
            original = obj[key]
            substituted = _substitute_params(
                original,
                params,
                _skip_params_key=False,
                add_provenance_comments=add_provenance_comments,
            )
            obj[key] = substituted
            if add_provenance_comments and isinstance(original, str):
                m = _PARAM_REF_RE.match(original)
                if m:
                    _add_provenance_comment(obj, key, f"was ${m.group(1)}")
        return obj
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            substituted = _substitute_params(
                item,
                params,
                _skip_params_key=False,
                add_provenance_comments=add_provenance_comments,
            )
            obj[i] = substituted
            if add_provenance_comments and isinstance(item, str):
                m = _PARAM_REF_RE.match(item)
                if m:
                    _add_provenance_comment(obj, i, f"was ${m.group(1)}")
        return obj
    return obj


def _check_no_unresolved_tokens(obj: object) -> None:
    """Recursive walk. Reject any remaining ${...} tokens."""
    if isinstance(obj, str):
        if _UNRESOLVED_TOKEN_RE.search(obj):
            raise ParseError(f"V65: unresolved token in: {obj!r}")
    elif isinstance(obj, dict):
        for value in obj.values():
            _check_no_unresolved_tokens(value)
    elif isinstance(obj, list):
        for item in obj:
            _check_no_unresolved_tokens(item)


# ---------------------------------------------------------------------------
# AABB expansion (v0.11)
# ---------------------------------------------------------------------------


def _expand_aabb(data: dict, add_provenance_comments: bool = False) -> None:
    """Walk meshes[].primitives[] and convert aabb → dimensions + translation."""
    for mesh in data.get("meshes", []):
        if not isinstance(mesh, dict):
            continue
        for prim in mesh.get("primitives", []):
            if not isinstance(prim, dict):
                continue
            if "aabb" not in prim:
                continue

            aabb = prim["aabb"]

            # Reject aabb + dimensions
            if "dimensions" in prim:
                raise ParseError("aabb and dimensions are mutually exclusive")

            # Validate aabb structure
            if not isinstance(aabb, dict):
                raise ParseError("aabb must be a mapping")
            allowed_keys = {"min", "max"}
            extra = set(aabb.keys()) - allowed_keys
            if extra:
                raise ParseError(f"Unknown keys inside aabb: {extra}")
            if "min" not in aabb or "max" not in aabb:
                raise ParseError("aabb requires both 'min' and 'max'")

            mn = aabb["min"]
            mx = aabb["max"]
            if not isinstance(mn, list) or len(mn) != 3:
                raise ParseError("aabb.min must be a list of 3 numbers")
            if not isinstance(mx, list) or len(mx) != 3:
                raise ParseError("aabb.max must be a list of 3 numbers")

            for i in range(3):
                if not isinstance(mn[i], (int, float)) or not math.isfinite(mn[i]):
                    raise ParseError(f"aabb.min[{i}] must be a finite number")
                if not isinstance(mx[i], (int, float)) or not math.isfinite(mx[i]):
                    raise ParseError(f"aabb.max[{i}] must be a finite number")
                if mx[i] <= mn[i]:
                    raise ParseError(f"aabb.max[{i}] ({mx[i]}) must be > aabb.min[{i}] ({mn[i]})")

            # F115: reject any transform keys alongside aabb
            transform = prim.get("transform")
            if isinstance(transform, dict) and transform:
                raise ParseError(
                    "F115: aabb must not be combined with transform "
                    "(translation, rotation, or scale)"
                )

            # Convert
            prim["dimensions"] = {
                "width": mx[0] - mn[0],
                "height": mx[1] - mn[1],
                "depth": mx[2] - mn[2],
            }
            prim["transform"] = {
                "translation": [
                    (mn[0] + mx[0]) / 2,
                    (mn[1] + mx[1]) / 2,
                    (mn[2] + mx[2]) / 2,
                ],
            }
            if add_provenance_comments:
                _add_provenance_comment(prim, "dimensions", "derived from aabb(min,max)")
                transform = prim.get("transform")
                if isinstance(transform, dict) and "translation" in transform:
                    _add_provenance_comment(
                        transform,
                        "translation",
                        "derived from aabb(min,max)",
                    )
            del prim["aabb"]


# ---------------------------------------------------------------------------
# Macro expansion (v0.11)
# ---------------------------------------------------------------------------


def _expand_macros(data: dict, add_provenance_comments: bool = False) -> None:
    """Walk meshes[].primitives[] and expand macro items in-place."""
    for mesh in data.get("meshes", []):
        if not isinstance(mesh, dict):
            continue
        prims = mesh.get("primitives", [])
        if not isinstance(prims, list):
            continue
        mesh_id = mesh.get("id", "")
        i = 0
        while i < len(prims):
            item = prims[i]
            if isinstance(item, dict) and "macro" in item:
                macro_type = item["macro"]
                if macro_type == "box_decompose":
                    expanded = _expand_box_decompose(
                        item,
                        mesh_id,
                        add_provenance_comments=add_provenance_comments,
                    )
                else:
                    raise ParseError(f"Unknown macro type: {macro_type!r}")
                prims[i : i + 1] = expanded
                i += len(expanded)
            else:
                i += 1


def _expand_box_decompose(
    item: dict, mesh_id: str, add_provenance_comments: bool = False
) -> list[dict]:
    """Expand a box_decompose macro into box primitives."""
    # Extract and validate fields
    box_id = item.get("id")
    if not box_id or not isinstance(box_id, str) or not _IDENTIFIER_RE.match(box_id):
        raise ParseError("box_decompose: 'id' is required and must be a valid identifier")

    axis = item.get("axis")
    if axis not in ("x", "z"):
        raise ParseError(f"box_decompose: axis must be 'x' or 'z', got {axis!r}")

    span = item.get("span")
    if not isinstance(span, list) or len(span) != 2:
        raise ParseError("box_decompose: span must be a list of 2 numbers")
    span_start, span_end = float(span[0]), float(span[1])
    if span_start >= span_end:
        raise ParseError(f"box_decompose: span[0] ({span_start}) must be < span[1] ({span_end})")

    base_y = float(item.get("base_y", 0.0))
    height = float(item.get("height", 0))
    if height <= 0:
        raise ParseError(f"box_decompose: height must be > 0, got {height}")

    thickness = float(item.get("thickness", 0))
    if thickness <= 0:
        raise ParseError(f"box_decompose: thickness must be > 0, got {thickness}")

    offset = float(item.get("offset", 0.0))

    cutouts = item.get("cutouts", [])
    if not isinstance(cutouts, list):
        raise ParseError("box_decompose: cutouts must be a list")

    macro_tags = item.get("tags", [])
    if not isinstance(macro_tags, list):
        macro_tags = []
    macro_surface = item.get("surface")
    macro_material = item.get("material")

    # Validate and parse cutouts
    parsed_cutouts = []
    for cut in cutouts:
        if not isinstance(cut, dict):
            raise ParseError("box_decompose: each cutout must be a mapping")
        cut_id = cut.get("id")
        if not cut_id or not isinstance(cut_id, str) or not _IDENTIFIER_RE.match(cut_id):
            raise ParseError(f"F116: cutout id must be a valid identifier, got {cut_id!r}")

        cut_span = cut.get("span")
        if not isinstance(cut_span, list) or len(cut_span) != 2:
            raise ParseError(f"box_decompose: cutout {cut_id!r} span must be 2 numbers")
        cut_start, cut_end = float(cut_span[0]), float(cut_span[1])
        if cut_start >= cut_end:
            raise ParseError(f"box_decompose: cutout {cut_id!r} span[0] must be < span[1]")
        if cut_start < span_start or cut_end > span_end:
            raise ParseError(
                f"box_decompose: cutout {cut_id!r} span [{cut_start}, {cut_end}] "
                f"exceeds box span [{span_start}, {span_end}]"
            )

        bottom = float(cut.get("bottom", 0.0))
        top = float(cut.get("top", height))
        if bottom >= top:
            raise ParseError(f"box_decompose: cutout {cut_id!r} bottom must be < top")
        if bottom < 0:
            raise ParseError(f"box_decompose: cutout {cut_id!r} bottom must be >= 0")
        if top > height:
            raise ParseError(
                f"box_decompose: cutout {cut_id!r} top ({top}) must be <= height ({height})"
            )

        parsed_cutouts.append(
            {
                "id": cut_id,
                "span_start": cut_start,
                "span_end": cut_end,
                "bottom": bottom,
                "top": top,
            }
        )

    # Check 2D overlap between cutouts
    for i_cut in range(len(parsed_cutouts)):
        for j_cut in range(i_cut + 1, len(parsed_cutouts)):
            a = parsed_cutouts[i_cut]
            b = parsed_cutouts[j_cut]
            # Overlap requires both span overlap AND vertical overlap
            span_overlap = a["span_start"] < b["span_end"] and b["span_start"] < a["span_end"]
            vert_overlap = a["bottom"] < b["top"] and b["bottom"] < a["top"]
            if span_overlap and vert_overlap:
                raise ParseError(f"box_decompose: cutouts {a['id']!r} and {b['id']!r} overlap")

    # Sort cutouts by (span_start, span_end, bottom, top)
    parsed_cutouts.sort(key=lambda o: (o["span_start"], o["span_end"], o["bottom"], o["top"]))

    # Decomposition
    result: list[dict] = []

    def _make_box(
        prim_id: str,
        segment_label: str,
        along_start: float,
        along_end: float,
        y_bottom: float,
        y_top: float,
    ) -> dict:
        along_len = along_end - along_start
        seg_height = y_top - y_bottom
        cx_along = (along_start + along_end) / 2
        cy = base_y + (y_bottom + y_top) / 2

        if axis == "x":
            dims = {"width": along_len, "height": seg_height, "depth": thickness}
            translation = [cx_along, cy, offset]
        else:  # axis == "z"
            dims = {"width": thickness, "height": seg_height, "depth": along_len}
            translation = [offset, cy, cx_along]

        tags = list(macro_tags)

        prim: dict = type(item)()
        prim.update(
            {
                "type": "box",
                "id": prim_id,
                "dimensions": dims,
                "transform": {"translation": translation},
            }
        )
        if tags:
            prim["tags"] = tags
        if macro_surface is not None:
            prim["surface"] = macro_surface
        if macro_material is not None:
            prim["material"] = macro_material
        if add_provenance_comments:
            _add_provenance_comment(
                prim,
                "id",
                f"from box_decompose:{box_id} segment={segment_label}",
            )
        return prim

    # Collect cut points along the box axis from cutout spans
    cut_points = sorted(
        {o["span_start"] for o in parsed_cutouts} | {o["span_end"] for o in parsed_cutouts}
    )

    # Emit full-height gap segments
    gap_edges = [span_start] + cut_points + [span_end]
    gap_idx = 0
    for k in range(len(gap_edges) - 1):
        seg_start = gap_edges[k]
        seg_end = gap_edges[k + 1]
        if seg_start >= seg_end:
            continue
        # Check if this segment overlaps with any cutout span
        overlaps_cutout = any(
            o["span_start"] <= seg_start and seg_end <= o["span_end"] for o in parsed_cutouts
        )
        if not overlaps_cutout:
            prim_id = f"{box_id}_gap_{gap_idx}"
            result.append(_make_box(prim_id, f"gap_{gap_idx}", seg_start, seg_end, 0.0, height))
            gap_idx += 1

    # Emit below/above segments for each cutout
    for cut in parsed_cutouts:
        cut_id = cut["id"]
        if cut["bottom"] > 0:
            result.append(
                _make_box(
                    f"{box_id}_{cut_id}_below",
                    f"{cut_id}_below",
                    cut["span_start"],
                    cut["span_end"],
                    0.0,
                    cut["bottom"],
                )
            )
        if cut["top"] < height:
            result.append(
                _make_box(
                    f"{box_id}_{cut_id}_above",
                    f"{cut_id}_above",
                    cut["span_start"],
                    cut["span_end"],
                    cut["top"],
                    height,
                )
            )

    return result
