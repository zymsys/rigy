"""v0.10 preprocessing: repeat macro expansion and params substitution.

Operates on raw dicts/lists/scalars from ruamel.yaml, before Pydantic
model construction. Never imports Pydantic models.
"""

from __future__ import annotations

import copy
import re

from rigy.errors import ParseError

_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_PARAM_REF_RE = re.compile(r"^\$([A-Za-z_][A-Za-z0-9_]*)$")
_EMBEDDED_PARAM_RE = re.compile(r"\$[A-Za-z_][A-Za-z0-9_]*")
_INDEX_TOKEN_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")
_UNRESOLVED_TOKEN_RE = re.compile(r"\$\{[A-Za-z_][A-Za-z0-9_]*\}")


def preprocess(data: dict) -> dict:
    """Entry point. Deep-copies data, expands repeats, substitutes params,
    strips the params key, and checks for unresolved tokens."""
    data = copy.deepcopy(data)
    _expand_repeats(data)

    # Validate and substitute params
    raw_params = data.get("params")
    if raw_params is not None:
        params = _validate_params(raw_params)
        _substitute_params(data, params)
        del data["params"]
    else:
        # Even without params, check for stray $param references
        _substitute_params(data, {})

    _check_no_unresolved_tokens(data)
    return data


def _expand_repeats(obj: object) -> None:
    """Recursive walk. In any list, detect repeat macros and expand in-place."""
    if isinstance(obj, dict):
        for value in obj.values():
            _expand_repeats(value)
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
                    expanded.append(instance)
                obj[i : i + 1] = expanded
                # Recurse into newly expanded items
                for e in expanded:
                    _expand_repeats(e)
                i += len(expanded)
            else:
                _expand_repeats(item)
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


def _substitute_params(obj: object, params: dict, _skip_params_key: bool = True) -> object:
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
            obj[key] = _substitute_params(obj[key], params, _skip_params_key=False)
        return obj
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            obj[i] = _substitute_params(item, params, _skip_params_key=False)
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
