"""Contract (Ricy) parsing and validation."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError as PydanticValidationError

from rigy.errors import ContractError
from rigy.models import RicyContract, RigySpec


def parse_contract(source: Path) -> RicyContract:
    """Parse a .ricy.yaml contract file.

    Args:
        source: Path to the contract YAML file.

    Returns:
        Parsed RicyContract.

    Raises:
        ContractError: On parse or schema errors.
    """
    try:
        text = source.read_text(encoding="utf-8")
    except OSError as e:
        raise ContractError(f"Cannot read contract file: {e}") from e

    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise ContractError(f"Invalid YAML in contract: {e}") from e

    if not isinstance(data, dict):
        raise ContractError("Contract top-level YAML value must be a mapping")

    try:
        return RicyContract(**data)
    except PydanticValidationError as e:
        raise ContractError(f"Contract schema validation failed:\n{e}") from e


def validate_contract(spec: RigySpec, contract: RicyContract) -> None:
    """Validate that a spec satisfies a contract.

    Checks:
    - All required_anchors exist in spec.anchors
    - All required_frame3_sets keys exist in contract.frame3_sets
    - All anchors referenced in frame3_sets values exist in spec.anchors

    Raises:
        ContractError: On any contract violation.
    """
    anchor_ids = {a.id for a in spec.anchors}

    for anchor_id in contract.required_anchors:
        if anchor_id not in anchor_ids:
            raise ContractError(
                f"Contract requires anchor {anchor_id!r} but it is not defined in the asset"
            )

    for frame3_name in contract.required_frame3_sets:
        if frame3_name not in contract.frame3_sets:
            raise ContractError(
                f"Contract requires frame3 set {frame3_name!r} but it is not defined in frame3_sets"
            )

    for set_name, anchor_refs in contract.frame3_sets.items():
        for ref in anchor_refs:
            if ref not in anchor_ids:
                raise ContractError(
                    f"Frame3 set {set_name!r} references anchor {ref!r} "
                    "which is not defined in the asset"
                )
