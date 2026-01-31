"""Tests for contract parsing and validation."""

import pytest

from rigy.contracts import parse_contract, validate_contract
from rigy.errors import ContractError
from rigy.models import Anchor, RicyContract, RigySpec


class TestParseContract:
    def test_parse_valid_contract(self, tmp_path):
        f = tmp_path / "test.ricy.yaml"
        f.write_text(
            'contract_version: "0.1"\n'
            "required_anchors:\n"
            "  - mount_a\n"
            "  - mount_b\n"
            "required_frame3_sets:\n"
            "  - mount\n"
            "frame3_sets:\n"
            "  mount: [mount_a, mount_b, mount_c]\n"
        )
        contract = parse_contract(f)
        assert contract.contract_version == "0.1"
        assert contract.required_anchors == ["mount_a", "mount_b"]
        assert contract.required_frame3_sets == ["mount"]
        assert contract.frame3_sets["mount"] == ["mount_a", "mount_b", "mount_c"]

    def test_parse_missing_file(self, tmp_path):
        with pytest.raises(ContractError, match="Cannot read"):
            parse_contract(tmp_path / "missing.ricy.yaml")

    def test_parse_invalid_yaml(self, tmp_path):
        f = tmp_path / "bad.ricy.yaml"
        f.write_text("{{{{bad yaml")
        with pytest.raises(ContractError, match="Invalid YAML"):
            parse_contract(f)

    def test_parse_non_dict(self, tmp_path):
        f = tmp_path / "list.ricy.yaml"
        f.write_text("- item1\n- item2\n")
        with pytest.raises(ContractError, match="mapping"):
            parse_contract(f)

    def test_parse_schema_error(self, tmp_path):
        f = tmp_path / "bad_schema.ricy.yaml"
        f.write_text("unknown_field: value\n")
        with pytest.raises(ContractError, match="schema validation"):
            parse_contract(f)

    def test_parse_fixture(self):
        from pathlib import Path

        fixture = Path(__file__).parent / "composition" / "parts" / "wheel.ricy.yaml"
        if not fixture.exists():
            pytest.skip("Fixture not found")
        contract = parse_contract(fixture)
        assert "mount_a" in contract.required_anchors


class TestValidateContract:
    def _make_spec_with_anchors(self, anchor_ids):
        return RigySpec(
            version="0.2",
            anchors=[Anchor(id=aid, translation=(0, 0, 0)) for aid in anchor_ids],
        )

    def test_valid_contract(self):
        spec = self._make_spec_with_anchors(["mount_a", "mount_b", "mount_c"])
        contract = RicyContract(
            contract_version="0.1",
            required_anchors=["mount_a", "mount_b", "mount_c"],
            required_frame3_sets=["mount"],
            frame3_sets={"mount": ["mount_a", "mount_b", "mount_c"]},
        )
        validate_contract(spec, contract)  # should not raise

    def test_missing_required_anchor(self):
        spec = self._make_spec_with_anchors(["mount_a", "mount_b"])
        contract = RicyContract(
            contract_version="0.1",
            required_anchors=["mount_a", "mount_b", "mount_c"],
        )
        with pytest.raises(ContractError, match="mount_c"):
            validate_contract(spec, contract)

    def test_missing_required_frame3_set(self):
        spec = self._make_spec_with_anchors(["mount_a"])
        contract = RicyContract(
            contract_version="0.1",
            required_frame3_sets=["mount"],
            frame3_sets={},  # missing 'mount'
        )
        with pytest.raises(ContractError, match="mount"):
            validate_contract(spec, contract)

    def test_frame3_set_references_missing_anchor(self):
        spec = self._make_spec_with_anchors(["mount_a", "mount_b"])
        contract = RicyContract(
            contract_version="0.1",
            frame3_sets={"mount": ["mount_a", "mount_b", "mount_c"]},
        )
        with pytest.raises(ContractError, match="mount_c"):
            validate_contract(spec, contract)

    def test_empty_contract_passes(self):
        spec = self._make_spec_with_anchors([])
        contract = RicyContract(contract_version="0.1")
        validate_contract(spec, contract)  # should not raise
