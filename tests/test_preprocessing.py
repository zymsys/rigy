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


class TestToolingTopLevelBlocks:
    def test_geometry_checks_ignored_by_preprocessing(self):
        data = {
            "version": "0.11",
            "params": {"size": 2.0},
            "value": "$size",
            "geometry_checks": {
                "checks": [
                    {"id": "c1", "expr": "$size"},
                    {"id": "c2", "expr": "${leftover}"},
                ]
            },
        }
        result = preprocess(data)
        assert result["value"] == 2.0
        assert result["geometry_checks"]["checks"][0]["expr"] == "$size"
        assert result["geometry_checks"]["checks"][1]["expr"] == "${leftover}"


class TestAabbExpansion:
    def test_basic_conversion(self):
        data = {
            "version": "0.11",
            "meshes": [
                {
                    "id": "m1",
                    "primitives": [
                        {
                            "type": "box",
                            "id": "p1",
                            "aabb": {"min": [0, 0, 0], "max": [2, 1, 3]},
                        }
                    ],
                }
            ],
        }
        result = preprocess(data)
        prim = result["meshes"][0]["primitives"][0]
        assert "aabb" not in prim
        assert prim["dimensions"] == {"width": 2.0, "height": 1.0, "depth": 3.0}
        assert prim["transform"]["translation"] == [1.0, 0.5, 1.5]

    def test_aabb_with_dimensions_rejected(self):
        data = {
            "version": "0.11",
            "meshes": [
                {
                    "id": "m1",
                    "primitives": [
                        {
                            "type": "box",
                            "id": "p1",
                            "aabb": {"min": [0, 0, 0], "max": [1, 1, 1]},
                            "dimensions": {"width": 1, "height": 1, "depth": 1},
                        }
                    ],
                }
            ],
        }
        with pytest.raises(ParseError, match="mutually exclusive"):
            preprocess(data)

    def test_f115_aabb_with_transform(self):
        data = {
            "version": "0.11",
            "meshes": [
                {
                    "id": "m1",
                    "primitives": [
                        {
                            "type": "box",
                            "id": "p1",
                            "aabb": {"min": [0, 0, 0], "max": [1, 1, 1]},
                            "transform": {"translation": [1, 0, 0]},
                        }
                    ],
                }
            ],
        }
        with pytest.raises(ParseError, match="F115"):
            preprocess(data)

    def test_min_ge_max_rejected(self):
        data = {
            "version": "0.11",
            "meshes": [
                {
                    "id": "m1",
                    "primitives": [
                        {
                            "type": "box",
                            "id": "p1",
                            "aabb": {"min": [0, 0, 0], "max": [0, 1, 1]},
                        }
                    ],
                }
            ],
        }
        with pytest.raises(ParseError, match="must be >"):
            preprocess(data)


class TestBoxDecomposeExpansion:
    def test_single_cutout(self):
        data = {
            "version": "0.11",
            "meshes": [
                {
                    "id": "walls",
                    "primitives": [
                        {
                            "macro": "box_decompose",
                            "id": "south",
                            "mesh": "walls",
                            "axis": "x",
                            "span": [0.0, 8.0],
                            "base_y": 0.0,
                            "height": 2.7,
                            "thickness": 0.2,
                            "cutouts": [
                                {
                                    "id": "door",
                                    "span": [3.5, 4.5],
                                    "bottom": 0.0,
                                    "top": 2.1,
                                }
                            ],
                        }
                    ],
                }
            ],
        }
        result = preprocess(data)
        prims = result["meshes"][0]["primitives"]
        ids = [p["id"] for p in prims]
        # Should have gap segments + above (no below since bottom=0)
        assert "south_gap_0" in ids
        assert "south_gap_1" in ids
        assert "south_door_above" in ids
        assert "south_door_below" not in ids
        # All should be boxes
        for p in prims:
            assert p["type"] == "box"

    def test_multiple_cutouts(self):
        data = {
            "version": "0.11",
            "meshes": [
                {
                    "id": "walls",
                    "primitives": [
                        {
                            "macro": "box_decompose",
                            "id": "wall",
                            "mesh": "walls",
                            "axis": "x",
                            "span": [0.0, 10.0],
                            "base_y": 0.0,
                            "height": 3.0,
                            "thickness": 0.2,
                            "cutouts": [
                                {
                                    "id": "door",
                                    "span": [2.0, 3.0],
                                    "bottom": 0.0,
                                    "top": 2.1,
                                },
                                {
                                    "id": "win",
                                    "span": [6.0, 8.0],
                                    "bottom": 0.8,
                                    "top": 2.0,
                                },
                            ],
                        }
                    ],
                }
            ],
        }
        result = preprocess(data)
        prims = result["meshes"][0]["primitives"]
        ids = [p["id"] for p in prims]
        assert "wall_door_above" in ids
        assert "wall_win_below" in ids
        assert "wall_win_above" in ids

    def test_no_cutouts(self):
        data = {
            "version": "0.11",
            "meshes": [
                {
                    "id": "walls",
                    "primitives": [
                        {
                            "macro": "box_decompose",
                            "id": "wall",
                            "mesh": "walls",
                            "axis": "x",
                            "span": [0.0, 5.0],
                            "base_y": 0.0,
                            "height": 2.5,
                            "thickness": 0.2,
                        }
                    ],
                }
            ],
        }
        result = preprocess(data)
        prims = result["meshes"][0]["primitives"]
        assert len(prims) == 1
        assert prims[0]["id"] == "wall_gap_0"
        assert prims[0]["dimensions"]["width"] == 5.0

    def test_overlapping_cutouts_rejected(self):
        data = {
            "version": "0.11",
            "meshes": [
                {
                    "id": "walls",
                    "primitives": [
                        {
                            "macro": "box_decompose",
                            "id": "wall",
                            "mesh": "walls",
                            "axis": "x",
                            "span": [0.0, 10.0],
                            "base_y": 0.0,
                            "height": 3.0,
                            "thickness": 0.2,
                            "cutouts": [
                                {"id": "a", "span": [2.0, 5.0], "bottom": 0.0, "top": 2.0},
                                {"id": "b", "span": [4.0, 7.0], "bottom": 0.0, "top": 2.0},
                            ],
                        }
                    ],
                }
            ],
        }
        with pytest.raises(ParseError, match="overlap"):
            preprocess(data)

    def test_tag_inheritance(self):
        data = {
            "version": "0.11",
            "meshes": [
                {
                    "id": "walls",
                    "primitives": [
                        {
                            "macro": "box_decompose",
                            "id": "wall",
                            "mesh": "walls",
                            "axis": "x",
                            "span": [0.0, 8.0],
                            "base_y": 0.0,
                            "height": 2.7,
                            "thickness": 0.2,
                            "tags": ["exterior"],
                            "cutouts": [
                                {
                                    "id": "win",
                                    "span": [3.0, 5.0],
                                    "bottom": 0.8,
                                    "top": 2.0,
                                }
                            ],
                        }
                    ],
                }
            ],
        }
        result = preprocess(data)
        prims = result["meshes"][0]["primitives"]
        # All segments inherit macro tags
        for p in prims:
            assert "exterior" in p.get("tags", [])

    def test_axis_z(self):
        data = {
            "version": "0.11",
            "meshes": [
                {
                    "id": "walls",
                    "primitives": [
                        {
                            "macro": "box_decompose",
                            "id": "wall",
                            "mesh": "walls",
                            "axis": "z",
                            "span": [0.0, 5.0],
                            "base_y": 0.0,
                            "height": 2.5,
                            "thickness": 0.2,
                        }
                    ],
                }
            ],
        }
        result = preprocess(data)
        prims = result["meshes"][0]["primitives"]
        p = prims[0]
        # axis=z: depth is along Z, width is thickness
        assert p["dimensions"]["depth"] == 5.0
        assert p["dimensions"]["width"] == 0.2

    def test_f116_invalid_cutout_id(self):
        data = {
            "version": "0.11",
            "meshes": [
                {
                    "id": "walls",
                    "primitives": [
                        {
                            "macro": "box_decompose",
                            "id": "wall",
                            "mesh": "walls",
                            "axis": "x",
                            "span": [0.0, 5.0],
                            "base_y": 0.0,
                            "height": 2.5,
                            "thickness": 0.2,
                            "cutouts": [
                                {"id": "0bad", "span": [1.0, 2.0], "bottom": 0.0, "top": 1.0}
                            ],
                        }
                    ],
                }
            ],
        }
        with pytest.raises(ParseError, match="F116"):
            preprocess(data)
