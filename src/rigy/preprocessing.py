"""v0.10–v0.12 preprocessing: repeat/params, expressions, rotation, AABB, macros.

Operates on raw dicts/lists/scalars from ruamel.yaml, before Pydantic
model construction. Never imports Pydantic models.
"""

from __future__ import annotations

import copy
import math
import re

from rigy.errors import ParseError, ValidationError

_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_PARAM_REF_RE = re.compile(r"^\$([A-Za-z_][A-Za-z0-9_]*)$")
_EMBEDDED_PARAM_RE = re.compile(r"\$[A-Za-z_][A-Za-z0-9_]*")
_INDEX_TOKEN_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")
_UNRESOLVED_TOKEN_RE = re.compile(r"\$\{[A-Za-z_][A-Za-z0-9_]*\}")
_MISSING = object()
_EXPR_RE = re.compile(r"^=(.+)$")


def preprocess(data: dict, add_provenance_comments: bool = False) -> dict:
    """Entry point. Deep-copies data, expands repeats, substitutes params,
    strips the params key, checks for unresolved tokens, evaluates
    expressions, normalizes rotations, then expands AABB and macros."""
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
        params = {}
        # Even without params, check for stray $param references
        _substitute_params(data, {}, add_provenance_comments=add_provenance_comments)

    _check_no_unresolved_tokens(data)

    # v0.12 steps: expression evaluation and rotation normalization
    version = _parse_version(data.get("version", "0.1"))
    _check_v012_version_gates(data, version)
    if version >= (0, 12):
        _evaluate_expressions(data, params)
        _normalize_rotations(data)

    _expand_aabb(data, add_provenance_comments=add_provenance_comments)
    _expand_macros(data, add_provenance_comments=add_provenance_comments)
    if geometry_checks is not _MISSING:
        data["geometry_checks"] = geometry_checks
    return data


def _parse_version(version_str: str) -> tuple[int, int]:
    """Parse 'M.N' into (M, N). Returns (0, 1) on parse failure."""
    parts = str(version_str).split(".")
    if len(parts) == 2:
        try:
            return (int(parts[0]), int(parts[1]))
        except ValueError:
            pass
    return (0, 1)


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
        # Check for embedded $param (prohibited), but skip expression
        # scalars (=...) — those handle $param via the expression evaluator.
        if not obj.startswith("=") and _EMBEDDED_PARAM_RE.search(obj):
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
    version = _parse_version(data.get("version", "0.1"))
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
                    # V76: validate mesh field for v0.12+
                    if version >= (0, 12) and "mesh" in item:
                        if item["mesh"] != mesh_id:
                            raise ValidationError(
                                f"V76: box_decompose.mesh {item['mesh']!r} does not match "
                                f"containing mesh {mesh_id!r}"
                            )
                        del item["mesh"]
                    expanded = _expand_box_decompose(
                        item,
                        mesh_id,
                        add_provenance_comments=add_provenance_comments,
                    )
                elif macro_type == "triangle_prism_on_plane":
                    expanded = _expand_triangle_prism_on_plane(
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

    offset_mode = item.get("offset_mode")
    if offset_mode is not None and "offset" in item:
        raise ParseError("box_decompose: 'offset' and 'offset_mode' are mutually exclusive")

    if offset_mode is not None:
        if offset_mode not in ("centerline", "neg_face", "pos_face"):
            raise ParseError(
                f"box_decompose: offset_mode must be 'centerline'|'neg_face'|'pos_face', "
                f"got {offset_mode!r}"
            )
        if offset_mode == "centerline":
            offset = 0.0
        elif offset_mode == "neg_face":
            offset = thickness / 2.0
        else:  # pos_face
            offset = -thickness / 2.0
    else:
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


# ---------------------------------------------------------------------------
# v0.12 version gating (V77)
# ---------------------------------------------------------------------------


def _check_v012_version_gates(data: dict, version: tuple[int, int]) -> None:
    """V77: Reject v0.12-only features in specs with version < 0.12."""
    if version >= (0, 12):
        return

    # Check for expression scalars (=expr)
    _check_no_expressions(data, "top-level")

    # Check for rotation_axis_angle / rotation_quat in transforms
    for mesh in data.get("meshes", []):
        if not isinstance(mesh, dict):
            continue
        if "material" in mesh:
            raise ValidationError(
                f"V77: mesh.material requires version >= 0.12, "
                f"but spec declares version {data.get('version')!r}"
            )
        for prim in mesh.get("primitives", []):
            if not isinstance(prim, dict):
                continue
            transform = prim.get("transform")
            if isinstance(transform, dict):
                if "rotation_axis_angle" in transform:
                    raise ValidationError(
                        f"V77: rotation_axis_angle requires version >= 0.12, "
                        f"but spec declares version {data.get('version')!r}"
                    )
                if "rotation_quat" in transform:
                    raise ValidationError(
                        f"V77: rotation_quat requires version >= 0.12, "
                        f"but spec declares version {data.get('version')!r}"
                    )


def _check_no_expressions(obj: object, context: str) -> None:
    """Check that no expression scalars (=expr) exist in the data."""
    if isinstance(obj, str):
        if _EXPR_RE.match(obj):
            raise ValidationError("V77: expression scalars require version >= 0.12")
    elif isinstance(obj, dict):
        for value in obj.values():
            _check_no_expressions(value, context)
    elif isinstance(obj, list):
        for item in obj:
            _check_no_expressions(item, context)


# ---------------------------------------------------------------------------
# Expression evaluation (v0.12)
# ---------------------------------------------------------------------------

# Tokenizer for expression language
_EXPR_TOKEN_RE = re.compile(
    r"""
    (\d+\.?\d*(?:[eE][+-]?\d+)?)  # NUMBER
    |(\$[A-Za-z_][A-Za-z0-9_]*)   # PARAM
    |([A-Za-z_][A-Za-z0-9_]*)     # IDENT (function name)
    |(\+)                          # PLUS
    |(-)                           # MINUS
    |(\*)                          # STAR
    |(/)                           # SLASH
    |(\()                          # LPAREN
    |(\))                          # RPAREN
    |(,)                           # COMMA
    |(\s+)                         # WHITESPACE (skip)
    """,
    re.VERBOSE,
)

_EXPR_FUNCTIONS: dict[str, tuple[int, object]] = {
    "min": (2, min),
    "max": (2, max),
    "clamp": (3, lambda x, lo, hi: max(lo, min(hi, x))),
    "abs": (1, abs),
    "sqrt": (1, None),  # special handling for domain check
    "sin": (1, math.sin),
    "cos": (1, math.cos),
    "tan": (1, math.tan),
    "atan2": (2, math.atan2),
    "deg2rad": (1, math.radians),
    "rad2deg": (1, math.degrees),
}


class _Token:
    __slots__ = ("kind", "value")

    def __init__(self, kind: str, value: object = None):
        self.kind = kind
        self.value = value


def _tokenize_expr(expr: str) -> list[_Token]:
    """Tokenize an expression string into tokens."""
    tokens: list[_Token] = []
    pos = 0
    while pos < len(expr):
        m = _EXPR_TOKEN_RE.match(expr, pos)
        if m is None:
            raise ValidationError(
                f"V68: unexpected character in expression at position {pos}: {expr!r}"
            )
        pos = m.end()
        if m.group(1) is not None:  # NUMBER
            tokens.append(_Token("NUMBER", float(m.group(1))))
        elif m.group(2) is not None:  # PARAM
            tokens.append(_Token("PARAM", m.group(2)[1:]))  # strip $
        elif m.group(3) is not None:  # IDENT
            tokens.append(_Token("IDENT", m.group(3)))
        elif m.group(4) is not None:
            tokens.append(_Token("PLUS"))
        elif m.group(5) is not None:
            tokens.append(_Token("MINUS"))
        elif m.group(6) is not None:
            tokens.append(_Token("STAR"))
        elif m.group(7) is not None:
            tokens.append(_Token("SLASH"))
        elif m.group(8) is not None:
            tokens.append(_Token("LPAREN"))
        elif m.group(9) is not None:
            tokens.append(_Token("RPAREN"))
        elif m.group(10) is not None:
            tokens.append(_Token("COMMA"))
        # group(11) is whitespace, skip
    tokens.append(_Token("EOF"))
    return tokens


class _ExprParser:
    """Recursive descent parser for the expression language."""

    def __init__(self, tokens: list[_Token], params: dict[str, float]):
        self.tokens = tokens
        self.pos = 0
        self.params = params

    def _peek(self) -> _Token:
        return self.tokens[self.pos]

    def _advance(self) -> _Token:
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def _expect(self, kind: str) -> _Token:
        tok = self._advance()
        if tok.kind != kind:
            raise ValidationError(f"V68: expected {kind}, got {tok.kind} in expression")
        return tok

    def parse(self) -> float:
        result = self._additive()
        if self._peek().kind != "EOF":
            raise ValidationError(f"V68: unexpected token after expression: {self._peek().kind}")
        return result

    def _additive(self) -> float:
        left = self._multiplicative()
        while self._peek().kind in ("PLUS", "MINUS"):
            op = self._advance()
            right = self._multiplicative()
            if op.kind == "PLUS":
                left = left + right
            else:
                left = left - right
        return left

    def _multiplicative(self) -> float:
        left = self._unary()
        while self._peek().kind in ("STAR", "SLASH"):
            op = self._advance()
            right = self._unary()
            if op.kind == "STAR":
                left = left * right
            else:
                if right == 0.0:
                    raise ValidationError("V70: division by zero in expression")
                left = left / right
        return left

    def _unary(self) -> float:
        if self._peek().kind == "MINUS":
            self._advance()
            return -self._unary()
        if self._peek().kind == "PLUS":
            self._advance()
            return self._unary()
        return self._atom()

    def _atom(self) -> float:
        tok = self._peek()
        if tok.kind == "NUMBER":
            self._advance()
            return tok.value
        if tok.kind == "PARAM":
            self._advance()
            name = tok.value
            if name not in self.params:
                raise ValidationError(f"V69: expression references unknown parameter: ${name}")
            val = self.params[name]
            if not isinstance(val, (int, float)):
                raise ValidationError(f"V69: expression parameter ${name} is not numeric: {val!r}")
            return float(val)
        if tok.kind == "IDENT":
            return self._function_call()
        if tok.kind == "LPAREN":
            self._advance()
            result = self._additive()
            self._expect("RPAREN")
            return result
        raise ValidationError(f"V68: unexpected token in expression: {tok.kind}")

    def _function_call(self) -> float:
        name_tok = self._advance()
        name = name_tok.value
        if name not in _EXPR_FUNCTIONS:
            raise ValidationError(f"V68: unknown function in expression: {name!r}")
        arity, fn = _EXPR_FUNCTIONS[name]
        self._expect("LPAREN")
        args: list[float] = []
        if self._peek().kind != "RPAREN":
            args.append(self._additive())
            while self._peek().kind == "COMMA":
                self._advance()
                args.append(self._additive())
        self._expect("RPAREN")
        if len(args) != arity:
            raise ValidationError(
                f"V68: function {name!r} expects {arity} arguments, got {len(args)}"
            )
        # Special handling for sqrt domain check
        if name == "sqrt":
            if args[0] < 0:
                raise ValidationError(f"V71: sqrt({args[0]}) — domain error (negative argument)")
            return math.sqrt(args[0])
        return fn(*args)


def _quantize_expr_result(value: float) -> float:
    """Quantize to step 1e-9, canonicalize -0 → 0."""
    if not math.isfinite(value):
        raise ValidationError(f"V70: expression produced non-finite result: {value}")
    q = 1e-9
    result = round(value / q) * q
    if result == 0.0:
        result = 0.0  # canonicalize -0
    return result


def _evaluate_expressions(data: dict, params: dict | None = None) -> None:
    """Walk the entire data tree and evaluate expression scalars (=expr).

    Params are passed through so that expression strings like
    ``"=sqrt($run * $run + $rise * $rise)"`` can resolve ``$param``
    references.  Whole-scalar ``$param`` refs are already substituted
    by ``_substitute_params``; expression strings are skipped by that
    phase and resolved here instead.
    """
    numeric_params: dict[str, float] = {}
    for k, v in (params or {}).items():
        if isinstance(v, (int, float)):
            numeric_params[k] = float(v)
    _eval_expr_recursive(data, numeric_params)


def _eval_expr_recursive(obj: object, params: dict[str, float]) -> object:
    """Recursive walk: replace expression scalars with evaluated values."""
    if isinstance(obj, str):
        m = _EXPR_RE.match(obj)
        if m:
            expr_body = m.group(1)
            tokens = _tokenize_expr(expr_body)
            parser = _ExprParser(tokens, params)
            result = parser.parse()
            # Check for non-finite intermediate (final check)
            return _quantize_expr_result(result)
        return obj
    elif isinstance(obj, dict):
        for key in list(obj.keys()):
            obj[key] = _eval_expr_recursive(obj[key], params)
        return obj
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            obj[i] = _eval_expr_recursive(item, params)
        return obj
    return obj


# ---------------------------------------------------------------------------
# Rotation normalization (v0.12)
# ---------------------------------------------------------------------------


def _normalize_rotations(data: dict) -> None:
    """Walk meshes[].primitives[] transforms and normalize rotation to rotation_quat."""
    for mesh in data.get("meshes", []):
        if not isinstance(mesh, dict):
            continue
        for prim in mesh.get("primitives", []):
            if not isinstance(prim, dict):
                continue
            transform = prim.get("transform")
            if not isinstance(transform, dict):
                continue
            _normalize_transform_rotation(transform)


def _normalize_transform_rotation(transform: dict) -> None:
    """Convert any rotation form in a transform dict to rotation_quat."""
    has_euler = "rotation_euler" in transform
    has_degrees = "rotation_degrees" in transform
    has_axis_angle = "rotation_axis_angle" in transform
    has_quat = "rotation_quat" in transform

    count = sum([has_euler, has_degrees, has_axis_angle, has_quat])
    if count == 0:
        return
    if count > 1:
        raise ValidationError("V72: multiple rotation authoring forms specified in transform")

    if has_axis_angle:
        aa = transform["rotation_axis_angle"]
        if not isinstance(aa, dict):
            raise ValidationError("V73: rotation_axis_angle must be a mapping")
        axis = aa.get("axis")
        degrees = aa.get("degrees")
        if not isinstance(axis, (list, tuple)) or len(axis) != 3:
            raise ValidationError("V73: rotation_axis_angle.axis must be a list of 3 numbers")
        if not isinstance(degrees, (int, float)):
            raise ValidationError("V73: rotation_axis_angle.degrees must be a number")

        ax, ay, az = float(axis[0]), float(axis[1]), float(axis[2])
        deg = float(degrees)

        # V73: check finite
        if not (
            math.isfinite(ax) and math.isfinite(ay) and math.isfinite(az) and math.isfinite(deg)
        ):
            raise ValidationError(
                "V73: non-finite axis or degrees component in rotation_axis_angle"
            )

        # V67: check axis length
        axis_len = math.sqrt(ax * ax + ay * ay + az * az)
        if axis_len <= 1e-12:
            raise ValidationError("V67: axis vector has length <= 1e-12")

        # Normalize axis
        ax /= axis_len
        ay /= axis_len
        az /= axis_len

        # Convert to quaternion
        rad = math.radians(deg)
        half = rad / 2.0
        s = math.sin(half)
        c = math.cos(half)
        qx, qy, qz, qw = ax * s, ay * s, az * s, c

        quat = _canonicalize_quat(qx, qy, qz, qw)
        del transform["rotation_axis_angle"]
        transform["rotation_quat"] = list(quat)

    elif has_degrees:
        rx, ry, rz = [math.radians(float(v)) for v in transform["rotation_degrees"]]

        # V73: check finite
        for v in transform["rotation_degrees"]:
            if not math.isfinite(float(v)):
                raise ValidationError("V73: non-finite rotation_degrees component")

        quat = _euler_to_quat(rx, ry, rz)
        quat = _canonicalize_quat(*quat)
        del transform["rotation_degrees"]
        transform["rotation_quat"] = list(quat)

    elif has_euler:
        rx, ry, rz = [float(v) for v in transform["rotation_euler"]]

        # V73: check finite
        for v in transform["rotation_euler"]:
            if not math.isfinite(float(v)):
                raise ValidationError("V73: non-finite rotation_euler component")

        quat = _euler_to_quat(rx, ry, rz)
        quat = _canonicalize_quat(*quat)
        del transform["rotation_euler"]
        transform["rotation_quat"] = list(quat)

    elif has_quat:
        q = transform["rotation_quat"]
        if not isinstance(q, (list, tuple)) or len(q) != 4:
            raise ValidationError("V73: rotation_quat must be a list of 4 numbers")
        qx, qy, qz, qw = [float(v) for v in q]

        # V73: check finite
        if not all(math.isfinite(v) for v in (qx, qy, qz, qw)):
            raise ValidationError("V73: non-finite rotation_quat component")

        # V78: check length
        length = math.sqrt(qx * qx + qy * qy + qz * qz + qw * qw)
        if length <= 1e-12:
            raise ValidationError("V78: quaternion has length <= 1e-12")

        quat = _canonicalize_quat(qx, qy, qz, qw)
        transform["rotation_quat"] = list(quat)


def _euler_to_quat(rx: float, ry: float, rz: float) -> tuple[float, float, float, float]:
    """Convert Euler XYZ angles (radians) to quaternion (x, y, z, w)."""
    # Q = Qz * Qy * Qx
    cx, sx = math.cos(rx / 2), math.sin(rx / 2)
    cy, sy = math.cos(ry / 2), math.sin(ry / 2)
    cz, sz = math.cos(rz / 2), math.sin(rz / 2)

    qw = cx * cy * cz + sx * sy * sz
    qx = sx * cy * cz - cx * sy * sz
    qy = cx * sy * cz + sx * cy * sz
    qz = cx * cy * sz - sx * sy * cz

    return (qx, qy, qz, qw)


def _canonicalize_quat(
    qx: float,
    qy: float,
    qz: float,
    qw: float,
) -> tuple[float, float, float, float]:
    """Normalize, apply sign rule (w<0 negate), quantize to 1e-12, canonicalize -0."""
    length = math.sqrt(qx * qx + qy * qy + qz * qz + qw * qw)
    if length <= 1e-12:
        raise ValidationError("V78: quaternion has length <= 1e-12")

    qx /= length
    qy /= length
    qz /= length
    qw /= length

    # Sign rule: if w < 0, negate all
    if qw < 0:
        qx, qy, qz, qw = -qx, -qy, -qz, -qw

    # Quantize to 1e-12
    q_step = 1e-12
    qx = round(qx / q_step) * q_step
    qy = round(qy / q_step) * q_step
    qz = round(qz / q_step) * q_step
    qw = round(qw / q_step) * q_step

    # Canonicalize -0
    if qx == 0.0:
        qx = 0.0
    if qy == 0.0:
        qy = 0.0
    if qz == 0.0:
        qz = 0.0
    if qw == 0.0:
        qw = 0.0

    return (qx, qy, qz, qw)


# ---------------------------------------------------------------------------
# Rotation matrix → quaternion (Shepperd's method)
# ---------------------------------------------------------------------------


def _rotation_matrix_to_quat(R: list[list[float]]) -> tuple[float, float, float, float]:
    """Convert 3x3 rotation matrix to (x, y, z, w) quaternion via Shepperd's method."""
    trace = R[0][0] + R[1][1] + R[2][2]
    if trace > 0:
        s = 0.5 / math.sqrt(trace + 1.0)
        w = 0.25 / s
        x = (R[2][1] - R[1][2]) * s
        y = (R[0][2] - R[2][0]) * s
        z = (R[1][0] - R[0][1]) * s
    elif R[0][0] > R[1][1] and R[0][0] > R[2][2]:
        s = 2.0 * math.sqrt(1.0 + R[0][0] - R[1][1] - R[2][2])
        w = (R[2][1] - R[1][2]) / s
        x = 0.25 * s
        y = (R[0][1] + R[1][0]) / s
        z = (R[0][2] + R[2][0]) / s
    elif R[1][1] > R[2][2]:
        s = 2.0 * math.sqrt(1.0 + R[1][1] - R[0][0] - R[2][2])
        w = (R[0][2] - R[2][0]) / s
        x = (R[0][1] + R[1][0]) / s
        y = 0.25 * s
        z = (R[1][2] + R[2][1]) / s
    else:
        s = 2.0 * math.sqrt(1.0 + R[2][2] - R[0][0] - R[1][1])
        w = (R[1][0] - R[0][1]) / s
        x = (R[0][2] + R[2][0]) / s
        y = (R[1][2] + R[2][1]) / s
        z = 0.25 * s
    return (x, y, z, w)


# ---------------------------------------------------------------------------
# triangle_prism_on_plane macro (v0.12)
# ---------------------------------------------------------------------------


def _expand_triangle_prism_on_plane(
    item: dict,
    mesh_id: str,
    add_provenance_comments: bool = False,
) -> list[dict]:
    """Expand a triangle_prism_on_plane macro into a single wedge primitive.

    The macro specifies a triangular prism (wedge) via a construction plane
    and two leg vectors lying in that plane, plus an extrusion length along
    the plane normal.
    """
    prim_id = item.get("id")
    if not prim_id or not isinstance(prim_id, str) or not _IDENTIFIER_RE.match(prim_id):
        raise ParseError("triangle_prism_on_plane: 'id' is required and must be a valid identifier")

    plane = item.get("plane")
    if not isinstance(plane, dict):
        raise ParseError("triangle_prism_on_plane: 'plane' is required and must be a mapping")

    origin = plane.get("origin")
    normal = plane.get("normal")
    if not isinstance(origin, list) or len(origin) != 3:
        raise ParseError("triangle_prism_on_plane: plane.origin must be a list of 3 numbers")
    if not isinstance(normal, list) or len(normal) != 3:
        raise ParseError("triangle_prism_on_plane: plane.normal must be a list of 3 numbers")

    origin = [float(v) for v in origin]
    normal = [float(v) for v in normal]

    for v in origin + normal:
        if not math.isfinite(v):
            raise ParseError("triangle_prism_on_plane: non-finite value in plane origin/normal")

    leg_p = item.get("leg_p")
    leg_q = item.get("leg_q")
    if not isinstance(leg_p, list) or len(leg_p) != 3:
        raise ParseError("triangle_prism_on_plane: leg_p must be a list of 3 numbers")
    if not isinstance(leg_q, list) or len(leg_q) != 3:
        raise ParseError("triangle_prism_on_plane: leg_q must be a list of 3 numbers")

    leg_p = [float(v) for v in leg_p]
    leg_q = [float(v) for v in leg_q]

    for v in leg_p + leg_q:
        if not math.isfinite(v):
            raise ParseError("triangle_prism_on_plane: non-finite value in leg_p/leg_q")

    length = item.get("length")
    if not isinstance(length, (int, float)):
        raise ParseError("triangle_prism_on_plane: 'length' is required and must be a number")
    length = float(length)
    if length <= 0 or not math.isfinite(length):
        raise ParseError(f"triangle_prism_on_plane: length must be > 0 and finite, got {length}")

    # Normalize the plane normal
    n_len = math.sqrt(normal[0] ** 2 + normal[1] ** 2 + normal[2] ** 2)
    if n_len < 1e-12:
        raise ParseError("triangle_prism_on_plane: plane.normal has zero length")
    N = [normal[i] / n_len for i in range(3)]

    # Compute leg magnitudes
    len_p = math.sqrt(leg_p[0] ** 2 + leg_p[1] ** 2 + leg_p[2] ** 2)
    len_q = math.sqrt(leg_q[0] ** 2 + leg_q[1] ** 2 + leg_q[2] ** 2)
    if len_p < 1e-12:
        raise ParseError("triangle_prism_on_plane: leg_p has zero length")
    if len_q < 1e-12:
        raise ParseError("triangle_prism_on_plane: leg_q has zero length")

    dir_p = [leg_p[i] / len_p for i in range(3)]
    dir_q = [leg_q[i] / len_q for i in range(3)]

    # Verify dir_p ⊥ N and dir_q ⊥ N (within tolerance)
    tol = 1e-6
    dot_pn = abs(dir_p[0] * N[0] + dir_p[1] * N[1] + dir_p[2] * N[2])
    dot_qn = abs(dir_q[0] * N[0] + dir_q[1] * N[1] + dir_q[2] * N[2])
    if dot_pn > tol:
        raise ParseError(
            f"triangle_prism_on_plane: leg_p is not perpendicular to plane normal "
            f"(dot={dot_pn:.6g})"
        )
    if dot_qn > tol:
        raise ParseError(
            f"triangle_prism_on_plane: leg_q is not perpendicular to plane normal "
            f"(dot={dot_qn:.6g})"
        )

    # Wedge canonical layout:
    #   X = along base (bottom edge connecting two right-angle vertices)
    #   Y = extrusion height
    #   Z = perpendicular from base to right-angle vertex
    #
    # We map: wedge_x ↔ dir_p, wedge_y ↔ N, wedge_z ↔ dir_q
    #
    # Check handedness: if cross(dir_p, N) · dir_q < 0, swap legs
    cross_pn = [
        dir_p[1] * N[2] - dir_p[2] * N[1],
        dir_p[2] * N[0] - dir_p[0] * N[2],
        dir_p[0] * N[1] - dir_p[1] * N[0],
    ]
    dot_cross_q = cross_pn[0] * dir_q[0] + cross_pn[1] * dir_q[1] + cross_pn[2] * dir_q[2]

    if dot_cross_q < 0:
        # Swap legs to get right-handed frame
        dir_p, dir_q = dir_q, dir_p
        len_p, len_q = len_q, len_p
        leg_p, leg_q = leg_q, leg_p

    # Build rotation matrix R = [dir_p | N | dir_q] (columns)
    # R maps local (x,y,z) to world: col0=dir_p, col1=N, col2=dir_q
    R = [
        [dir_p[0], N[0], dir_q[0]],
        [dir_p[1], N[1], dir_q[1]],
        [dir_p[2], N[2], dir_q[2]],
    ]

    # Convert rotation matrix to quaternion
    raw_quat = _rotation_matrix_to_quat(R)
    quat = _canonicalize_quat(*raw_quat)

    # Dimensions
    dim_x = len_p
    dim_y = length
    dim_z = len_q

    # Translation: origin + leg_p/2 + leg_q/2 + N * length/2
    translation = [
        origin[0] + leg_p[0] / 2.0 + leg_q[0] / 2.0 + N[0] * length / 2.0,
        origin[1] + leg_p[1] / 2.0 + leg_q[1] / 2.0 + N[1] * length / 2.0,
        origin[2] + leg_p[2] / 2.0 + leg_q[2] / 2.0 + N[2] * length / 2.0,
    ]

    prim: dict = type(item)()
    prim["type"] = "wedge"
    prim["id"] = prim_id
    prim["dimensions"] = {"x": dim_x, "y": dim_y, "z": dim_z}
    prim["transform"] = {
        "rotation_quat": list(quat),
        "translation": translation,
    }

    # Inherit optional fields
    macro_material = item.get("material")
    if macro_material is not None:
        prim["material"] = macro_material

    macro_tags = item.get("tags")
    if isinstance(macro_tags, list):
        prim["tags"] = list(macro_tags)

    macro_surface = item.get("surface")
    if macro_surface is not None:
        prim["surface"] = macro_surface

    if add_provenance_comments:
        _add_provenance_comment(prim, "id", f"from triangle_prism_on_plane:{prim_id}")

    return [prim]
