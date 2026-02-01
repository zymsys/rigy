"""Conformance suite test runner."""

from __future__ import annotations

import hashlib
import json
import warnings
from pathlib import Path

import pytest

from rigy.exporter import export_gltf
from rigy.parser import parse_yaml
from rigy.symmetry import expand_symmetry
from rigy.validation import validate

CONFORMANCE_DIR = Path(__file__).parent.parent / "conformance"
MANIFEST_PATH = CONFORMANCE_DIR / "manifest.json"


def _load_manifest() -> list[dict]:
    data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return data["tests"]


def _positive_tests() -> list[dict]:
    return [t for t in _load_manifest() if t["type"] == "positive"]


def _negative_tests() -> list[dict]:
    return [t for t in _load_manifest() if t["type"] == "negative"]


@pytest.mark.parametrize(
    "test_entry",
    _positive_tests(),
    ids=[t["id"] for t in _positive_tests()],
)
def test_conformance_positive(test_entry, tmp_path):
    """Compile input and verify byte-identical output + SHA-256."""
    input_path = CONFORMANCE_DIR / test_entry["input"]
    expected_path = CONFORMANCE_DIR / test_entry["expected_output"]

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        spec = parse_yaml(input_path)
        spec = expand_symmetry(spec)
        validate(spec)
        output_path = tmp_path / "output.glb"
        export_gltf(spec, output_path, yaml_dir=input_path.parent)

    actual_bytes = output_path.read_bytes()
    expected_bytes = expected_path.read_bytes()

    # Check SHA-256
    actual_sha = hashlib.sha256(actual_bytes).hexdigest()
    assert actual_sha == test_entry["expected_sha256"], (
        f"SHA-256 mismatch for {test_entry['id']}: "
        f"expected {test_entry['expected_sha256']}, got {actual_sha}"
    )

    # Check byte-identical
    assert actual_bytes == expected_bytes, (
        f"Byte mismatch for {test_entry['id']}: "
        f"output size {len(actual_bytes)} vs expected {len(expected_bytes)}"
    )


if _negative_tests():

    @pytest.mark.parametrize(
        "test_entry",
        _negative_tests(),
        ids=[t["id"] for t in _negative_tests()],
    )
    def test_conformance_negative(test_entry, tmp_path):
        """Compile input and assert correct error type."""
        from rigy import errors

        input_path = CONFORMANCE_DIR / test_entry["input"]
        expected_error_type = test_entry["expected_error_type"]
        error_cls = getattr(errors, expected_error_type)

        with pytest.raises(error_cls):
            spec = parse_yaml(input_path)
            spec = expand_symmetry(spec)
            validate(spec)
            output_path = tmp_path / "output.glb"
            export_gltf(spec, output_path, yaml_dir=input_path.parent)
