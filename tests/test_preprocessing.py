"""Tests for v0.10 preprocessing: repeat expansion and params substitution."""

import pytest

from rigy.errors import ParseError
from rigy.preprocessing import preprocess


class TestRepeatExpansion:
    def test_basic_expansion_count3(self):
        data = {
            "version": "0.10",
            "items": [
                {
                    "repeat": {
                        "count": 3,
                        "as": "i",
                        "body": {"id": "item${i}", "value": "${i}"},
                    }
                }
            ],
        }
        result = preprocess(data)
        assert len(result["items"]) == 3
        assert result["items"][0] == {"id": "item0", "value": 0}
        assert result["items"][1] == {"id": "item1", "value": 1}
        assert result["items"][2] == {"id": "item2", "value": 2}

    def test_count_zero_empty_list(self):
        data = {
            "version": "0.10",
            "items": [
                {"repeat": {"count": 0, "as": "i", "body": {"id": "x${i}"}}}
            ],
        }
        result = preprocess(data)
        assert result["items"] == []

    def test_count_one_single_element(self):
        data = {
            "version": "0.10",
            "items": [
                {"repeat": {"count": 1, "as": "i", "body": {"id": "only${i}"}}}
            ],
        }
        result = preprocess(data)
        assert len(result["items"]) == 1
        assert result["items"][0] == {"id": "only0"}

    def test_numeric_substitution_standalone(self):
        """'${i}' alone becomes an int."""
        data = {
            "version": "0.10",
            "items": [
                {"repeat": {"count": 2, "as": "i", "body": {"val": "${i}"}}}
            ],
        }
        result = preprocess(data)
        assert result["items"][0]["val"] == 0
        assert isinstance(result["items"][0]["val"], int)
        assert result["items"][1]["val"] == 1

    def test_string_embedding(self):
        """'picket${i}' becomes 'picket0', etc."""
        data = {
            "version": "0.10",
            "items": [
                {"repeat": {"count": 2, "as": "i", "body": {"id": "picket${i}"}}}
            ],
        }
        result = preprocess(data)
        assert result["items"][0]["id"] == "picket0"
        assert result["items"][1]["id"] == "picket1"
        assert isinstance(result["items"][0]["id"], str)

    def test_list_substitution(self):
        """[${i}, 0, 0] becomes [0, 0, 0] for i=0."""
        data = {
            "version": "0.10",
            "items": [
                {
                    "repeat": {
                        "count": 2,
                        "as": "i",
                        "body": {"pos": ["${i}", 0, 0]},
                    }
                }
            ],
        }
        result = preprocess(data)
        assert result["items"][0]["pos"] == [0, 0, 0]
        assert result["items"][1]["pos"] == [1, 0, 0]

    def test_nested_repeats_in_body_sublists(self):
        data = {
            "version": "0.10",
            "items": [
                {
                    "repeat": {
                        "count": 2,
                        "as": "i",
                        "body": {
                            "id": "outer${i}",
                            "children": [
                                {
                                    "repeat": {
                                        "count": 2,
                                        "as": "j",
                                        "body": {"id": "inner${i}_${j}"},
                                    }
                                }
                            ],
                        },
                    }
                }
            ],
        }
        result = preprocess(data)
        assert len(result["items"]) == 2
        assert len(result["items"][0]["children"]) == 2
        assert result["items"][0]["children"][0]["id"] == "inner0_0"
        assert result["items"][0]["children"][1]["id"] == "inner0_1"
        assert result["items"][1]["children"][0]["id"] == "inner1_0"

    def test_ordering_preserved(self):
        data = {
            "version": "0.10",
            "items": [
                {"id": "before"},
                {"repeat": {"count": 3, "as": "i", "body": {"id": "mid${i}"}}},
                {"id": "after"},
            ],
        }
        result = preprocess(data)
        assert len(result["items"]) == 5
        assert result["items"][0]["id"] == "before"
        assert result["items"][1]["id"] == "mid0"
        assert result["items"][2]["id"] == "mid1"
        assert result["items"][3]["id"] == "mid2"
        assert result["items"][4]["id"] == "after"

    def test_v62_negative_count(self):
        data = {
            "version": "0.10",
            "items": [
                {"repeat": {"count": -1, "as": "i", "body": {"id": "x"}}}
            ],
        }
        with pytest.raises(ParseError, match="V62"):
            preprocess(data)

    def test_v62_float_count(self):
        data = {
            "version": "0.10",
            "items": [
                {"repeat": {"count": 2.5, "as": "i", "body": {"id": "x"}}}
            ],
        }
        with pytest.raises(ParseError, match="V62"):
            preprocess(data)

    def test_v62_string_count(self):
        data = {
            "version": "0.10",
            "items": [
                {"repeat": {"count": "three", "as": "i", "body": {"id": "x"}}}
            ],
        }
        with pytest.raises(ParseError, match="V62"):
            preprocess(data)

    def test_v63_empty_as(self):
        data = {
            "version": "0.10",
            "items": [
                {"repeat": {"count": 1, "as": "", "body": {"id": "x"}}}
            ],
        }
        with pytest.raises(ParseError, match="V63"):
            preprocess(data)

    def test_v63_digit_leading_as(self):
        data = {
            "version": "0.10",
            "items": [
                {"repeat": {"count": 1, "as": "0bad", "body": {"id": "x"}}}
            ],
        }
        with pytest.raises(ParseError, match="V63"):
            preprocess(data)

    def test_v64_missing_body(self):
        data = {
            "version": "0.10",
            "items": [
                {"repeat": {"count": 1, "as": "i"}}
            ],
        }
        with pytest.raises(ParseError, match="V64"):
            preprocess(data)

    def test_v64_extra_keys(self):
        data = {
            "version": "0.10",
            "items": [
                {"repeat": {"count": 1, "as": "i", "body": {"id": "x"}, "extra": True}}
            ],
        }
        with pytest.raises(ParseError, match="V64"):
            preprocess(data)

    def test_v64_repeat_not_sole_key(self):
        """A mapping with 'repeat' plus other keys is not a repeat macro —
        it's a regular mapping that gets passed through (and likely rejected
        by Pydantic downstream). We test that it's NOT treated as a repeat."""
        data = {
            "version": "0.10",
            "items": [
                {"repeat": {"count": 1, "as": "i", "body": {"id": "x"}}, "other_key": True}
            ],
        }
        result = preprocess(data)
        # Not expanded — the item is passed through as-is
        assert len(result["items"]) == 1
        assert "repeat" in result["items"][0]
        assert "other_key" in result["items"][0]

    def test_v64_body_not_mapping(self):
        data = {
            "version": "0.10",
            "items": [
                {"repeat": {"count": 1, "as": "i", "body": "not_a_dict"}}
            ],
        }
        with pytest.raises(ParseError, match="V64"):
            preprocess(data)


class TestParamsSubstitution:
    def test_scalar_number(self):
        data = {
            "version": "0.10",
            "params": {"radius": 0.5},
            "value": "$radius",
        }
        result = preprocess(data)
        assert result["value"] == 0.5
        assert "params" not in result

    def test_scalar_string(self):
        data = {
            "version": "0.10",
            "params": {"name": "hello"},
            "value": "$name",
        }
        result = preprocess(data)
        assert result["value"] == "hello"

    def test_scalar_boolean(self):
        data = {
            "version": "0.10",
            "params": {"flag": True},
            "value": "$flag",
        }
        result = preprocess(data)
        assert result["value"] is True

    def test_type_preserving_float(self):
        data = {
            "version": "0.10",
            "params": {"r": 1.5},
            "value": "$r",
        }
        result = preprocess(data)
        assert result["value"] == 1.5
        assert isinstance(result["value"], float)

    def test_type_preserving_int(self):
        data = {
            "version": "0.10",
            "params": {"n": 42},
            "value": "$n",
        }
        result = preprocess(data)
        assert result["value"] == 42
        assert isinstance(result["value"], int)

    def test_params_key_stripped(self):
        data = {
            "version": "0.10",
            "params": {"x": 1},
            "value": "$x",
        }
        result = preprocess(data)
        assert "params" not in result

    def test_no_recursive_expansion(self):
        """Param values are NOT further expanded."""
        data = {
            "version": "0.10",
            "params": {"a": "$b", "b": 42},
            "value": "$a",
        }
        result = preprocess(data)
        assert result["value"] == "$b"  # literal string, not 42

    def test_v58_list_param_value(self):
        data = {
            "version": "0.10",
            "params": {"dims": [1, 2, 3]},
        }
        with pytest.raises(ParseError, match="V58"):
            preprocess(data)

    def test_v58_dict_param_value(self):
        data = {
            "version": "0.10",
            "params": {"dims": {"x": 1}},
        }
        with pytest.raises(ParseError, match="V58"):
            preprocess(data)

    def test_v58_invalid_identifier_key(self):
        data = {
            "version": "0.10",
            "params": {"0bad": 1},
        }
        with pytest.raises(ParseError, match="V58"):
            preprocess(data)

    def test_v59_undeclared_param(self):
        data = {
            "version": "0.10",
            "params": {"x": 1},
            "value": "$y",
        }
        with pytest.raises(ParseError, match="V59"):
            preprocess(data)

    def test_v59_no_params_block(self):
        """Reference to $param when no params block exists."""
        data = {
            "version": "0.10",
            "value": "$missing",
        }
        with pytest.raises(ParseError, match="V59"):
            preprocess(data)

    def test_v60_embedded_param_in_string(self):
        data = {
            "version": "0.10",
            "params": {"r": 1},
            "value": "leg_$r",
        }
        with pytest.raises(ParseError, match="V60"):
            preprocess(data)

    def test_v60_expression_with_param(self):
        data = {
            "version": "0.10",
            "params": {"r": 1},
            "value": "2 * $r",
        }
        with pytest.raises(ParseError, match="V60"):
            preprocess(data)

    def test_no_params_no_error(self):
        """A spec without params should pass through cleanly."""
        data = {
            "version": "0.10",
            "meshes": [{"id": "m", "primitives": []}],
        }
        result = preprocess(data)
        assert result["meshes"][0]["id"] == "m"


class TestCombined:
    def test_repeat_body_uses_param(self):
        """repeat body with $param — both resolve."""
        data = {
            "version": "0.10",
            "params": {"size": 2.0},
            "items": [
                {
                    "repeat": {
                        "count": 2,
                        "as": "i",
                        "body": {"id": "item${i}", "val": "$size"},
                    }
                }
            ],
        }
        result = preprocess(data)
        assert len(result["items"]) == 2
        assert result["items"][0] == {"id": "item0", "val": 2.0}
        assert result["items"][1] == {"id": "item1", "val": 2.0}

    def test_v65_unresolved_index_token(self):
        """${token} remaining after preprocessing is rejected."""
        data = {
            "version": "0.10",
            "value": "${leftover}",
        }
        with pytest.raises(ParseError, match="V65"):
            preprocess(data)

    def test_index_token_not_confused_with_param(self):
        """${i} inside a repeat body should be consumed, not flagged as V60."""
        data = {
            "version": "0.10",
            "items": [
                {
                    "repeat": {
                        "count": 2,
                        "as": "i",
                        "body": {"id": "x${i}"},
                    }
                }
            ],
        }
        result = preprocess(data)
        assert result["items"][0]["id"] == "x0"

    def test_immutability(self):
        """Preprocessing should not mutate the original data."""
        data = {
            "version": "0.10",
            "params": {"x": 1},
            "value": "$x",
        }
        original_value = data["value"]
        preprocess(data)
        assert data["value"] == original_value
        assert "params" in data  # original not mutated
