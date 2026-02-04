"""Tests for v0.12 amendment: expressions, rotation normalization,
per-primitive materials, box_decompose.mesh removal, version gating."""

import math

import pytest

from rigy.errors import ValidationError
from rigy.models import Material, Mesh, RigySpec
from rigy.parser import parse_yaml
from rigy.preprocessing import preprocess
from rigy.tessellation import tessellate_primitive
from rigy.validation import validate


def _make_spec(**overrides) -> RigySpec:
    base = {
        "version": "0.12",
        "units": "meters",
        "coordinate_system": {"up": "Y", "forward": "-Z", "handedness": "right"},
        "tessellation_profile": "v0_1_default",
    }
    base.update(overrides)
    return RigySpec(**base)


# =====================================================================
# Expression evaluation (Section 2)
# =====================================================================


class TestExpressionEvaluation:
    def test_basic_addition(self):
        data = {"version": "0.12", "value": "=1 + 2"}
        result = preprocess(data)
        assert result["value"] == pytest.approx(3.0)

    def test_basic_subtraction(self):
        data = {"version": "0.12", "value": "=5 - 3"}
        result = preprocess(data)
        assert result["value"] == pytest.approx(2.0)

    def test_basic_multiplication(self):
        data = {"version": "0.12", "value": "=3 * 4"}
        result = preprocess(data)
        assert result["value"] == pytest.approx(12.0)

    def test_basic_division(self):
        data = {"version": "0.12", "value": "=10 / 4"}
        result = preprocess(data)
        assert result["value"] == pytest.approx(2.5)

    def test_operator_precedence(self):
        data = {"version": "0.12", "value": "=2 + 3 * 4"}
        result = preprocess(data)
        assert result["value"] == pytest.approx(14.0)

    def test_parentheses(self):
        data = {"version": "0.12", "value": "=(2 + 3) * 4"}
        result = preprocess(data)
        assert result["value"] == pytest.approx(20.0)

    def test_unary_minus(self):
        data = {"version": "0.12", "value": "=-5"}
        result = preprocess(data)
        assert result["value"] == pytest.approx(-5.0)

    def test_nested_unary(self):
        data = {"version": "0.12", "value": "=--3"}
        result = preprocess(data)
        assert result["value"] == pytest.approx(3.0)

    def test_function_sqrt(self):
        data = {"version": "0.12", "value": "=sqrt(9)"}
        result = preprocess(data)
        assert result["value"] == pytest.approx(3.0)

    def test_function_abs(self):
        data = {"version": "0.12", "value": "=abs(-7)"}
        result = preprocess(data)
        assert result["value"] == pytest.approx(7.0)

    def test_function_min(self):
        data = {"version": "0.12", "value": "=min(3, 7)"}
        result = preprocess(data)
        assert result["value"] == pytest.approx(3.0)

    def test_function_max(self):
        data = {"version": "0.12", "value": "=max(3, 7)"}
        result = preprocess(data)
        assert result["value"] == pytest.approx(7.0)

    def test_function_clamp(self):
        data = {"version": "0.12", "value": "=clamp(10, 0, 5)"}
        result = preprocess(data)
        assert result["value"] == pytest.approx(5.0)

    def test_function_sin(self):
        data = {"version": "0.12", "value": "=sin(0)"}
        result = preprocess(data)
        assert result["value"] == pytest.approx(0.0, abs=1e-9)

    def test_function_cos(self):
        data = {"version": "0.12", "value": "=cos(0)"}
        result = preprocess(data)
        assert result["value"] == pytest.approx(1.0)

    def test_function_deg2rad(self):
        data = {"version": "0.12", "value": "=deg2rad(180)"}
        result = preprocess(data)
        assert result["value"] == pytest.approx(math.pi, abs=1e-8)

    def test_function_rad2deg(self):
        data = {"version": "0.12", "value": "=rad2deg(3.14159265358979)"}
        result = preprocess(data)
        assert result["value"] == pytest.approx(180.0, abs=1e-5)

    def test_function_atan2(self):
        data = {"version": "0.12", "value": "=atan2(1, 1)"}
        result = preprocess(data)
        assert result["value"] == pytest.approx(math.atan2(1, 1))

    def test_combined_param_and_expr(self):
        """Params are substituted before expression eval."""
        data = {
            "version": "0.12",
            "params": {"r": 5.0},
            "value": "$r",
            "computed": "=3 + 2",
        }
        result = preprocess(data)
        assert result["value"] == 5.0
        assert result["computed"] == pytest.approx(5.0)

    def test_expression_in_list(self):
        data = {"version": "0.12", "values": ["=1 + 1", "=2 * 3"]}
        result = preprocess(data)
        assert result["values"][0] == pytest.approx(2.0)
        assert result["values"][1] == pytest.approx(6.0)

    def test_expression_in_nested_dict(self):
        data = {
            "version": "0.12",
            "mesh": {"dims": {"w": "=2 + 3"}},
        }
        result = preprocess(data)
        assert result["mesh"]["dims"]["w"] == pytest.approx(5.0)

    def test_quantization(self):
        """Results are quantized to 1e-9 step."""
        data = {"version": "0.12", "value": "=1 / 3"}
        result = preprocess(data)
        # 1/3 quantized to nearest 1e-9
        assert result["value"] == pytest.approx(0.333333333, abs=1e-9)

    def test_v70_division_by_zero(self):
        data = {"version": "0.12", "value": "=1 / 0"}
        with pytest.raises(ValidationError, match="V70"):
            preprocess(data)

    def test_v71_sqrt_negative(self):
        data = {"version": "0.12", "value": "=sqrt(-1)"}
        with pytest.raises(ValidationError, match="V71"):
            preprocess(data)

    def test_v68_unknown_function(self):
        data = {"version": "0.12", "value": "=badfunction(1)"}
        with pytest.raises(ValidationError, match="V68"):
            preprocess(data)

    def test_v68_bad_syntax(self):
        data = {"version": "0.12", "value": "=@#$"}
        with pytest.raises(ValidationError, match="V68"):
            preprocess(data)

    def test_non_expression_strings_unaffected(self):
        data = {"version": "0.12", "value": "hello"}
        result = preprocess(data)
        assert result["value"] == "hello"

    def test_bare_equals_sign_not_expression(self):
        """A bare '=' is not treated as an expression (no body after =)."""
        data = {"version": "0.12", "value": "="}
        result = preprocess(data)
        assert result["value"] == "="

    def test_expression_with_trailing_garbage(self):
        """Expression with unparseable content raises V68."""
        data = {"version": "0.12", "value": "=1 + @"}
        with pytest.raises(ValidationError, match="V68"):
            preprocess(data)


# =====================================================================
# Rotation normalization (Section 3)
# =====================================================================


class TestRotationNormalization:
    def test_euler_to_quat(self):
        """rotation_euler is converted to rotation_quat in v0.12."""
        data = {
            "version": "0.12",
            "meshes": [
                {
                    "id": "m1",
                    "primitives": [
                        {
                            "type": "box",
                            "id": "p1",
                            "dimensions": {"x": 1, "y": 1, "z": 1},
                            "transform": {"rotation_euler": [0, 0, 0]},
                        }
                    ],
                }
            ],
        }
        result = preprocess(data)
        t = result["meshes"][0]["primitives"][0]["transform"]
        assert "rotation_euler" not in t
        assert "rotation_quat" in t
        # Identity rotation: (0, 0, 0, 1)
        assert t["rotation_quat"][3] == pytest.approx(1.0)
        assert t["rotation_quat"][0] == pytest.approx(0.0, abs=1e-12)

    def test_degrees_to_quat(self):
        """rotation_degrees is converted to rotation_quat in v0.12."""
        data = {
            "version": "0.12",
            "meshes": [
                {
                    "id": "m1",
                    "primitives": [
                        {
                            "type": "box",
                            "id": "p1",
                            "dimensions": {"x": 1, "y": 1, "z": 1},
                            "transform": {"rotation_degrees": [90, 0, 0]},
                        }
                    ],
                }
            ],
        }
        result = preprocess(data)
        t = result["meshes"][0]["primitives"][0]["transform"]
        assert "rotation_degrees" not in t
        assert "rotation_quat" in t
        # 90° around X: quat ≈ (sin(45°), 0, 0, cos(45°))
        qx, qy, qz, qw = t["rotation_quat"]
        assert qx == pytest.approx(math.sin(math.pi / 4), abs=1e-9)
        assert qw == pytest.approx(math.cos(math.pi / 4), abs=1e-9)

    def test_axis_angle_to_quat(self):
        """rotation_axis_angle is converted to rotation_quat."""
        data = {
            "version": "0.12",
            "meshes": [
                {
                    "id": "m1",
                    "primitives": [
                        {
                            "type": "box",
                            "id": "p1",
                            "dimensions": {"x": 1, "y": 1, "z": 1},
                            "transform": {
                                "rotation_axis_angle": {
                                    "axis": [0, 1, 0],
                                    "degrees": 90,
                                }
                            },
                        }
                    ],
                }
            ],
        }
        result = preprocess(data)
        t = result["meshes"][0]["primitives"][0]["transform"]
        assert "rotation_axis_angle" not in t
        assert "rotation_quat" in t
        qx, qy, qz, qw = t["rotation_quat"]
        assert qy == pytest.approx(math.sin(math.pi / 4), abs=1e-9)
        assert qw == pytest.approx(math.cos(math.pi / 4), abs=1e-9)

    def test_quat_passthrough(self):
        """rotation_quat is normalized and canonicalized."""
        data = {
            "version": "0.12",
            "meshes": [
                {
                    "id": "m1",
                    "primitives": [
                        {
                            "type": "box",
                            "id": "p1",
                            "dimensions": {"x": 1, "y": 1, "z": 1},
                            "transform": {"rotation_quat": [0, 0, 0, 1]},
                        }
                    ],
                }
            ],
        }
        result = preprocess(data)
        t = result["meshes"][0]["primitives"][0]["transform"]
        assert t["rotation_quat"] == [0.0, 0.0, 0.0, 1.0]

    def test_sign_rule_w_negative(self):
        """If w < 0, negate all components."""
        data = {
            "version": "0.12",
            "meshes": [
                {
                    "id": "m1",
                    "primitives": [
                        {
                            "type": "box",
                            "id": "p1",
                            "dimensions": {"x": 1, "y": 1, "z": 1},
                            "transform": {"rotation_quat": [0, 0, 0, -1]},
                        }
                    ],
                }
            ],
        }
        result = preprocess(data)
        t = result["meshes"][0]["primitives"][0]["transform"]
        # After negation: (0, 0, 0, 1)
        assert t["rotation_quat"][3] == pytest.approx(1.0)

    def test_v72_multiple_rotation_forms(self):
        """V72: only one rotation form allowed."""
        data = {
            "version": "0.12",
            "meshes": [
                {
                    "id": "m1",
                    "primitives": [
                        {
                            "type": "box",
                            "id": "p1",
                            "dimensions": {"x": 1, "y": 1, "z": 1},
                            "transform": {
                                "rotation_euler": [0, 0, 0],
                                "rotation_degrees": [0, 0, 0],
                            },
                        }
                    ],
                }
            ],
        }
        with pytest.raises(ValidationError, match="V72"):
            preprocess(data)

    def test_v67_zero_length_axis(self):
        """V67: axis vector must have length > 1e-12."""
        data = {
            "version": "0.12",
            "meshes": [
                {
                    "id": "m1",
                    "primitives": [
                        {
                            "type": "box",
                            "id": "p1",
                            "dimensions": {"x": 1, "y": 1, "z": 1},
                            "transform": {
                                "rotation_axis_angle": {
                                    "axis": [0, 0, 0],
                                    "degrees": 45,
                                }
                            },
                        }
                    ],
                }
            ],
        }
        with pytest.raises(ValidationError, match="V67"):
            preprocess(data)

    def test_v73_non_finite_euler(self):
        data = {
            "version": "0.12",
            "meshes": [
                {
                    "id": "m1",
                    "primitives": [
                        {
                            "type": "box",
                            "id": "p1",
                            "dimensions": {"x": 1, "y": 1, "z": 1},
                            "transform": {"rotation_euler": [float("inf"), 0, 0]},
                        }
                    ],
                }
            ],
        }
        with pytest.raises(ValidationError, match="V73"):
            preprocess(data)

    def test_v78_zero_length_quat(self):
        data = {
            "version": "0.12",
            "meshes": [
                {
                    "id": "m1",
                    "primitives": [
                        {
                            "type": "box",
                            "id": "p1",
                            "dimensions": {"x": 1, "y": 1, "z": 1},
                            "transform": {"rotation_quat": [0, 0, 0, 0]},
                        }
                    ],
                }
            ],
        }
        with pytest.raises(ValidationError, match="V78"):
            preprocess(data)

    def test_no_rotation_passthrough(self):
        """Transform without rotation is left alone."""
        data = {
            "version": "0.12",
            "meshes": [
                {
                    "id": "m1",
                    "primitives": [
                        {
                            "type": "box",
                            "id": "p1",
                            "dimensions": {"x": 1, "y": 1, "z": 1},
                            "transform": {"translation": [1, 0, 0]},
                        }
                    ],
                }
            ],
        }
        result = preprocess(data)
        t = result["meshes"][0]["primitives"][0]["transform"]
        assert "rotation_quat" not in t
        assert t["translation"] == [1, 0, 0]

    def test_pre012_rotation_not_normalized(self):
        """Pre-v0.12 specs should NOT have rotation normalization applied."""
        data = {
            "version": "0.11",
            "meshes": [
                {
                    "id": "m1",
                    "primitives": [
                        {
                            "type": "box",
                            "id": "p1",
                            "dimensions": {"x": 1, "y": 1, "z": 1},
                            "transform": {"rotation_degrees": [90, 0, 0]},
                        }
                    ],
                }
            ],
        }
        result = preprocess(data)
        t = result["meshes"][0]["primitives"][0]["transform"]
        # rotation_degrees should still be there (Pydantic model handles conversion)
        assert "rotation_degrees" in t
        assert "rotation_quat" not in t


# =====================================================================
# Quaternion tessellation
# =====================================================================


class TestQuatTessellation:
    def test_rotation_quat_applied_in_tessellation(self):
        """A box rotated via rotation_quat should produce transformed positions."""
        from rigy.models import Primitive, Transform

        # 90° around Y via quaternion
        s = math.sin(math.pi / 4)
        c = math.cos(math.pi / 4)
        prim = Primitive(
            type="box",
            id="p1",
            dimensions={"x": 2, "y": 1, "z": 1},
            transform=Transform(rotation_quat=(0, s, 0, c)),
        )
        md = tessellate_primitive(prim)
        # After 90° Y rotation, X extent becomes Z extent
        assert md.positions[:, 2].max() > 0.9  # was X=1.0, now Z
        assert md.positions[:, 0].max() < 0.6  # was X=1.0, now much smaller in X


# =====================================================================
# Per-primitive materials (Section 4)
# =====================================================================


class TestPerPrimitiveMaterials:
    def test_mesh_material_default(self):
        """mesh.material provides default for all primitives."""
        spec = _make_spec(
            materials={"red": Material(base_color=[1, 0, 0, 1])},
            meshes=[
                {
                    "id": "m1",
                    "material": "red",
                    "primitives": [
                        {"type": "box", "id": "p1", "dimensions": {"x": 1, "y": 1, "z": 1}},
                        {"type": "box", "id": "p2", "dimensions": {"x": 1, "y": 1, "z": 1}},
                    ],
                }
            ],
        )
        validate(spec)  # should not raise

    def test_primitive_overrides_mesh_material(self):
        """primitive.material overrides mesh.material."""
        spec = _make_spec(
            materials={
                "red": Material(base_color=[1, 0, 0, 1]),
                "blue": Material(base_color=[0, 0, 1, 1]),
            },
            meshes=[
                {
                    "id": "m1",
                    "material": "red",
                    "primitives": [
                        {"type": "box", "id": "p1", "dimensions": {"x": 1, "y": 1, "z": 1}},
                        {
                            "type": "box",
                            "id": "p2",
                            "dimensions": {"x": 1, "y": 1, "z": 1},
                            "material": "blue",
                        },
                    ],
                }
            ],
        )
        validate(spec)  # should not raise

    def test_v74_no_material_resolved(self):
        """V74: no material resolved for a primitive in v0.12+."""
        spec = _make_spec(
            meshes=[
                {
                    "id": "m1",
                    "primitives": [
                        {"type": "box", "id": "p1", "dimensions": {"x": 1, "y": 1, "z": 1}},
                    ],
                }
            ],
        )
        with pytest.raises(ValidationError, match="V74"):
            validate(spec)

    def test_v74_partial_material(self):
        """V74: some primitives have materials, some don't (no mesh default)."""
        spec = _make_spec(
            materials={"red": Material(base_color=[1, 0, 0, 1])},
            meshes=[
                {
                    "id": "m1",
                    "primitives": [
                        {
                            "type": "box",
                            "id": "p1",
                            "dimensions": {"x": 1, "y": 1, "z": 1},
                            "material": "red",
                        },
                        {"type": "box", "id": "p2", "dimensions": {"x": 1, "y": 1, "z": 1}},
                    ],
                }
            ],
        )
        with pytest.raises(ValidationError, match="V74"):
            validate(spec)

    def test_v75_unknown_mesh_material(self):
        """V75: mesh.material references unknown material."""
        spec = _make_spec(
            meshes=[
                {
                    "id": "m1",
                    "material": "nonexistent",
                    "primitives": [
                        {"type": "box", "id": "p1", "dimensions": {"x": 1, "y": 1, "z": 1}},
                    ],
                }
            ],
        )
        with pytest.raises(ValidationError, match="V75"):
            validate(spec)

    def test_v41_not_applied_in_v012(self):
        """V41 (inconsistent material) should NOT apply in v0.12+."""
        spec = _make_spec(
            materials={
                "red": Material(base_color=[1, 0, 0, 1]),
                "blue": Material(base_color=[0, 0, 1, 1]),
            },
            meshes=[
                {
                    "id": "m1",
                    "primitives": [
                        {
                            "type": "box",
                            "id": "p1",
                            "dimensions": {"x": 1, "y": 1, "z": 1},
                            "material": "red",
                        },
                        {
                            "type": "box",
                            "id": "p2",
                            "dimensions": {"x": 1, "y": 1, "z": 1},
                            "material": "blue",
                        },
                    ],
                }
            ],
        )
        validate(spec)  # should not raise — V41 is superseded

    def test_v41_still_applies_pre012(self):
        """V41 should still apply for pre-v0.12 specs."""
        spec = RigySpec(
            version="0.11",
            materials={
                "red": Material(base_color=[1, 0, 0, 1]),
                "blue": Material(base_color=[0, 0, 1, 1]),
            },
            meshes=[
                Mesh(
                    id="m1",
                    primitives=[
                        {
                            "type": "box",
                            "id": "p1",
                            "dimensions": {"x": 1, "y": 1, "z": 1},
                            "material": "red",
                        },
                        {
                            "type": "box",
                            "id": "p2",
                            "dimensions": {"x": 1, "y": 1, "z": 1},
                            "material": "blue",
                        },
                    ],
                )
            ],
        )
        with pytest.raises(ValidationError, match="inconsistent material"):
            validate(spec)


# =====================================================================
# Version gating (V77)
# =====================================================================


class TestVersionGating:
    def test_v77_expression_in_old_version(self):
        """V77: expression scalars require version >= 0.12."""
        data = {"version": "0.11", "value": "=1 + 2"}
        with pytest.raises(ValidationError, match="V77"):
            preprocess(data)

    def test_v77_rotation_axis_angle_in_old_version(self):
        data = {
            "version": "0.11",
            "meshes": [
                {
                    "id": "m1",
                    "primitives": [
                        {
                            "type": "box",
                            "id": "p1",
                            "dimensions": {"x": 1, "y": 1, "z": 1},
                            "transform": {
                                "rotation_axis_angle": {"axis": [0, 1, 0], "degrees": 45}
                            },
                        }
                    ],
                }
            ],
        }
        with pytest.raises(ValidationError, match="V77"):
            preprocess(data)

    def test_v77_rotation_quat_in_old_version(self):
        data = {
            "version": "0.11",
            "meshes": [
                {
                    "id": "m1",
                    "primitives": [
                        {
                            "type": "box",
                            "id": "p1",
                            "dimensions": {"x": 1, "y": 1, "z": 1},
                            "transform": {"rotation_quat": [0, 0, 0, 1]},
                        }
                    ],
                }
            ],
        }
        with pytest.raises(ValidationError, match="V77"):
            preprocess(data)

    def test_v77_mesh_material_in_old_version(self):
        """V77: mesh.material requires version >= 0.12."""
        spec = RigySpec(
            version="0.11",
            materials={"red": Material(base_color=[1, 0, 0, 1])},
            meshes=[
                Mesh(
                    id="m1",
                    material="red",
                    primitives=[
                        {
                            "type": "box",
                            "id": "p1",
                            "dimensions": {"x": 1, "y": 1, "z": 1},
                            "material": "red",
                        },
                    ],
                )
            ],
        )
        with pytest.raises(ValidationError, match="V77"):
            validate(spec)


# =====================================================================
# box_decompose.mesh removal (Section 5)
# =====================================================================


class TestBoxDecomposeMeshField:
    def test_v76_mesh_mismatch(self):
        """V76: box_decompose.mesh must match containing mesh ID."""
        data = {
            "version": "0.12",
            "meshes": [
                {
                    "id": "walls",
                    "primitives": [
                        {
                            "macro": "box_decompose",
                            "id": "south",
                            "mesh": "other_mesh",
                            "axis": "x",
                            "span": [0.0, 8.0],
                            "base_y": 0.0,
                            "height": 2.7,
                            "thickness": 0.2,
                        }
                    ],
                }
            ],
        }
        with pytest.raises(ValidationError, match="V76"):
            preprocess(data)

    def test_mesh_field_matching_discarded(self):
        """box_decompose.mesh matching containing mesh is silently discarded."""
        data = {
            "version": "0.12",
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
                        }
                    ],
                }
            ],
        }
        result = preprocess(data)
        # Should expand without error
        prims = result["meshes"][0]["primitives"]
        assert len(prims) >= 1
        for p in prims:
            assert "mesh" not in p

    def test_mesh_field_absent_ok(self):
        """box_decompose without mesh field should work."""
        data = {
            "version": "0.12",
            "meshes": [
                {
                    "id": "walls",
                    "primitives": [
                        {
                            "macro": "box_decompose",
                            "id": "south",
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
        assert len(prims) >= 1

    def test_pre012_mesh_field_ignored(self):
        """Pre-v0.12: mesh field is accepted and ignored (no V76)."""
        data = {
            "version": "0.11",
            "meshes": [
                {
                    "id": "walls",
                    "primitives": [
                        {
                            "macro": "box_decompose",
                            "id": "south",
                            "mesh": "other_mesh",
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
        # Should expand without error (mesh field ignored)
        prims = result["meshes"][0]["primitives"]
        assert len(prims) >= 1


# =====================================================================
# Per-primitive export
# =====================================================================


class TestPerPrimitiveExport:
    def test_v012_produces_multiple_gltf_primitives(self, tmp_path):
        """v0.12 mesh with 2 primitives should produce 2 glTF primitives."""
        from rigy.exporter import export_gltf

        spec = _make_spec(
            materials={
                "red": Material(base_color=[1, 0, 0, 1]),
                "blue": Material(base_color=[0, 0, 1, 1]),
            },
            meshes=[
                {
                    "id": "m1",
                    "primitives": [
                        {
                            "type": "box",
                            "id": "p1",
                            "dimensions": {"x": 1, "y": 1, "z": 1},
                            "material": "red",
                        },
                        {
                            "type": "box",
                            "id": "p2",
                            "dimensions": {"x": 1, "y": 1, "z": 1},
                            "material": "blue",
                        },
                    ],
                }
            ],
        )
        out = tmp_path / "test.glb"
        export_gltf(spec, out)

        import pygltflib

        gltf = pygltflib.GLTF2.load(str(out))
        # Should have 1 mesh with 2 primitives
        assert len(gltf.meshes) == 1
        assert len(gltf.meshes[0].primitives) == 2
        # Each should have different materials
        assert gltf.meshes[0].primitives[0].material != gltf.meshes[0].primitives[1].material
        # Each should have extras.rigy_id
        assert gltf.meshes[0].primitives[0].extras["rigy_id"] == "p1"
        assert gltf.meshes[0].primitives[1].extras["rigy_id"] == "p2"

    def test_pre012_produces_single_gltf_primitive(self, tmp_path):
        """Pre-v0.12 mesh with 2 primitives should produce 1 merged glTF primitive."""
        from rigy.exporter import export_gltf

        spec = RigySpec(
            version="0.6",
            materials={"red": Material(base_color=[1, 0, 0, 1])},
            meshes=[
                Mesh(
                    id="m1",
                    primitives=[
                        {
                            "type": "box",
                            "id": "p1",
                            "dimensions": {"x": 1, "y": 1, "z": 1},
                            "material": "red",
                        },
                        {
                            "type": "box",
                            "id": "p2",
                            "dimensions": {"x": 1, "y": 1, "z": 1},
                            "material": "red",
                        },
                    ],
                )
            ],
        )
        out = tmp_path / "test.glb"
        export_gltf(spec, out)

        import pygltflib

        gltf = pygltflib.GLTF2.load(str(out))
        # Should have 1 mesh with 1 merged primitive
        assert len(gltf.meshes) == 1
        assert len(gltf.meshes[0].primitives) == 1

    def test_v012_mesh_material_default_in_export(self, tmp_path):
        """mesh.material provides default material for primitives without explicit material."""
        from rigy.exporter import export_gltf

        spec = _make_spec(
            materials={
                "red": Material(base_color=[1, 0, 0, 1]),
                "blue": Material(base_color=[0, 0, 1, 1]),
            },
            meshes=[
                {
                    "id": "m1",
                    "material": "red",
                    "primitives": [
                        {"type": "box", "id": "p1", "dimensions": {"x": 1, "y": 1, "z": 1}},
                        {
                            "type": "box",
                            "id": "p2",
                            "dimensions": {"x": 1, "y": 1, "z": 1},
                            "material": "blue",
                        },
                    ],
                }
            ],
        )
        out = tmp_path / "test.glb"
        export_gltf(spec, out)

        import pygltflib

        gltf = pygltflib.GLTF2.load(str(out))
        assert len(gltf.meshes[0].primitives) == 2
        # p1 uses mesh default "red", p2 overrides to "blue"
        mat0 = gltf.meshes[0].primitives[0].material
        mat1 = gltf.meshes[0].primitives[1].material
        assert mat0 is not None
        assert mat1 is not None
        assert gltf.materials[mat0].name == "red"
        assert gltf.materials[mat1].name == "blue"


# =====================================================================
# End-to-end parse + validate for v0.12
# =====================================================================


class TestV012EndToEnd:
    def test_parse_v012_with_expressions_and_axis_angle(self):
        yaml_str = """\
version: "0.12"
units: meters
materials:
  red:
    base_color: [1, 0, 0, 1]
meshes:
  - id: m1
    material: red
    primitives:
      - type: box
        id: p1
        dimensions:
          x: "=2 + 3"
          y: 1
          z: 1
        transform:
          rotation_axis_angle:
            axis: [0, 1, 0]
            degrees: 45
"""
        spec = parse_yaml(yaml_str)
        validate(spec)
        # Expression should be evaluated
        assert spec.meshes[0].primitives[0].dimensions["x"] == pytest.approx(5.0)
        # Rotation should be in quaternion form
        assert spec.meshes[0].primitives[0].transform.rotation_quat is not None
        assert spec.meshes[0].primitives[0].transform.rotation_axis_angle is None


# =====================================================================
# box_decompose.offset_mode
# =====================================================================


class TestBoxDecomposeOffsetMode:
    def _make_box_decompose_data(self, **overrides):
        item = {
            "macro": "box_decompose",
            "id": "wall",
            "axis": "x",
            "span": [0.0, 4.0],
            "base_y": 0.0,
            "height": 2.5,
            "thickness": 0.2,
        }
        item.update(overrides)
        return {
            "version": "0.12",
            "meshes": [{"id": "m1", "primitives": [item]}],
        }

    def test_centerline_mode(self):
        data = self._make_box_decompose_data(offset_mode="centerline")
        result = preprocess(data)
        prim = result["meshes"][0]["primitives"][0]
        # centerline => offset=0.0, so Z translation = 0.0
        assert prim["transform"]["translation"][2] == pytest.approx(0.0)

    def test_neg_face_mode(self):
        data = self._make_box_decompose_data(offset_mode="neg_face")
        result = preprocess(data)
        prim = result["meshes"][0]["primitives"][0]
        # neg_face => offset = thickness/2 = 0.1, so Z translation = 0.1
        assert prim["transform"]["translation"][2] == pytest.approx(0.1)

    def test_pos_face_mode(self):
        data = self._make_box_decompose_data(offset_mode="pos_face")
        result = preprocess(data)
        prim = result["meshes"][0]["primitives"][0]
        # pos_face => offset = -thickness/2 = -0.1, so Z translation = -0.1
        assert prim["transform"]["translation"][2] == pytest.approx(-0.1)

    def test_mutual_exclusivity(self):
        data = self._make_box_decompose_data(offset_mode="centerline", offset=0.5)
        with pytest.raises(Exception, match="mutually exclusive"):
            preprocess(data)

    def test_invalid_offset_mode(self):
        data = self._make_box_decompose_data(offset_mode="invalid")
        with pytest.raises(Exception, match="offset_mode must be"):
            preprocess(data)

    def test_neg_face_z_axis(self):
        """neg_face with axis=z: offset displaces X coordinate."""
        data = self._make_box_decompose_data(axis="z", offset_mode="neg_face")
        result = preprocess(data)
        prim = result["meshes"][0]["primitives"][0]
        # axis=z: offset goes to X coordinate = thickness/2 = 0.1
        assert prim["transform"]["translation"][0] == pytest.approx(0.1)


# =====================================================================
# geometry_checks.alignment
# =====================================================================


class TestAlignmentChecks:
    def _make_spec_with_checks(self, alignment_checks):
        from rigy.inspection import inspect_spec

        spec = _make_spec(
            materials={"mat": Material(base_color=[0.5, 0.5, 0.5, 1.0])},
            meshes=[
                {
                    "id": "m1",
                    "material": "mat",
                    "primitives": [
                        {
                            "type": "box",
                            "id": "box1",
                            "dimensions": {"x": 2.0, "y": 1.0, "z": 1.0},
                            "transform": {"translation": [0, 0.5, 0]},
                        },
                        {
                            "type": "box",
                            "id": "box2",
                            "dimensions": {"x": 2.0, "y": 1.0, "z": 1.0},
                            "transform": {"translation": [0, 1.5, 0]},
                        },
                    ],
                }
            ],
            geometry_checks={"alignment": alignment_checks},
        )
        return inspect_spec(spec, include_intent_checks=True)

    def test_normal_parallel_pass(self):
        """Two boxes stacked — their +y normals should be parallel."""
        result = self._make_spec_with_checks(
            [
                {
                    "check": "normal_parallel",
                    "a": "box1.+y",
                    "b": "box2.+y",
                    "label": "top faces parallel",
                }
            ]
        )
        checks = result["checks"]
        assert len(checks) == 1
        assert checks[0]["pass"] is True
        assert checks[0]["label"] == "top faces parallel"

    def test_normal_parallel_fail(self):
        """Box +y vs +x normals should not be parallel."""
        result = self._make_spec_with_checks(
            [
                {
                    "check": "normal_parallel",
                    "a": "box1.+y",
                    "b": "box1.+x",
                    "label": "should fail",
                }
            ]
        )
        checks = result["checks"]
        assert len(checks) == 1
        assert checks[0]["pass"] is False

    def test_unknown_primitive(self):
        result = self._make_spec_with_checks(
            [
                {
                    "check": "normal_parallel",
                    "a": "nonexistent.+y",
                    "b": "box1.+y",
                    "label": "bad ref",
                }
            ]
        )
        checks = result["checks"]
        assert len(checks) == 1
        assert checks[0]["pass"] is None
        assert "cannot resolve" in checks[0]["error"]

    def test_unknown_feature(self):
        result = self._make_spec_with_checks(
            [
                {
                    "check": "normal_parallel",
                    "a": "box1.nonexistent",
                    "b": "box1.+y",
                    "label": "bad feature",
                }
            ]
        )
        checks = result["checks"]
        assert len(checks) == 1
        assert checks[0]["pass"] is None

    def test_unknown_check_type(self):
        result = self._make_spec_with_checks([{"check": "bogus_check", "label": "unknown"}])
        checks = result["checks"]
        assert len(checks) == 1
        assert checks[0]["pass"] is None
        assert "unknown check type" in checks[0]["error"]

    def test_wedge_derived_features(self):
        """Wedge primitives should expose slope_face, apex, and ridge features."""
        from rigy.inspection import inspect_spec

        spec = _make_spec(
            materials={"mat": Material(base_color=[0.5, 0.5, 0.5, 1.0])},
            meshes=[
                {
                    "id": "m1",
                    "material": "mat",
                    "primitives": [
                        {
                            "type": "wedge",
                            "id": "w1",
                            "dimensions": {"x": 2.0, "y": 1.0, "z": 1.0},
                        },
                    ],
                }
            ],
            geometry_checks={
                "alignment": [
                    {
                        "check": "normal_parallel",
                        "a": "w1.slope_face",
                        "b": "w1.slope_face",
                        "label": "slope self-parallel",
                    },
                ]
            },
        )
        result = inspect_spec(spec, include_intent_checks=True)
        checks = result["checks"]
        assert len(checks) == 1
        assert checks[0]["pass"] is True

    def test_no_checks_empty_array(self):
        """When no alignment checks are defined, checks should be empty array."""
        from rigy.inspection import inspect_spec

        spec = _make_spec(
            materials={"mat": Material(base_color=[0.5, 0.5, 0.5, 1.0])},
            meshes=[
                {
                    "id": "m1",
                    "material": "mat",
                    "primitives": [
                        {
                            "type": "box",
                            "id": "box1",
                            "dimensions": {"x": 1.0, "y": 1.0, "z": 1.0},
                        },
                    ],
                }
            ],
        )
        result = inspect_spec(spec, include_intent_checks=True)
        assert result["checks"] == []

    def test_point_on_line_reports_distance(self):
        """point_on_line reports distance from wedge apex to its own ridge."""
        from rigy.inspection import inspect_spec

        spec = _make_spec(
            materials={"mat": Material(base_color=[0.5, 0.5, 0.5, 1.0])},
            meshes=[
                {
                    "id": "m1",
                    "material": "mat",
                    "primitives": [
                        {
                            "type": "wedge",
                            "id": "w1",
                            "dimensions": {"x": 2.0, "y": 1.0, "z": 1.0},
                        },
                    ],
                }
            ],
            geometry_checks={
                "alignment": [
                    {
                        "check": "point_on_line",
                        "point": "w1.apex",
                        "line": "w1.ridge",
                        "label": "apex vs ridge",
                    },
                ]
            },
        )
        result = inspect_spec(spec, include_intent_checks=True)
        checks = result["checks"]
        assert len(checks) == 1
        # Apex centroid is displaced from the ridge — distance > 0
        assert checks[0]["pass"] is False
        assert "distance" in checks[0]
        assert checks[0]["distance"] > 0.0

    def test_point_on_line_pass(self):
        """point_on_line passes when point is on the line (within tolerance)."""
        from rigy.inspection import inspect_spec

        # Two wedges with same dimensions, same position.
        # The ridge of w1 is a line; a second identical wedge's ridge midpoint
        # lies on that same line. We use a large tolerance to test passing.
        spec = _make_spec(
            materials={"mat": Material(base_color=[0.5, 0.5, 0.5, 1.0])},
            meshes=[
                {
                    "id": "m1",
                    "material": "mat",
                    "primitives": [
                        {
                            "type": "wedge",
                            "id": "w1",
                            "dimensions": {"x": 2.0, "y": 1.0, "z": 1.0},
                        },
                    ],
                }
            ],
            geometry_checks={
                "alignment": [
                    {
                        "check": "point_on_line",
                        "point": "w1.apex",
                        "line": "w1.ridge",
                        "label": "apex near ridge",
                        "tolerance": 1.0,  # Large tolerance to pass
                    },
                ]
            },
        )
        result = inspect_spec(spec, include_intent_checks=True)
        checks = result["checks"]
        assert len(checks) == 1
        assert checks[0]["pass"] is True


# =====================================================================
# triangle_prism_on_plane macro
# =====================================================================


class TestTrianglePrismOnPlane:
    def _make_data(self, **overrides):
        item = {
            "macro": "triangle_prism_on_plane",
            "id": "gable",
            "plane": {
                "origin": [0, 3.0, -2.425],
                "normal": [0, 0, -1],
            },
            "leg_p": [-3.0, 0, 0],
            "leg_q": [0, 1.5, 0],
            "length": 0.15,
        }
        item.update(overrides)
        return {
            "version": "0.12",
            "meshes": [{"id": "m1", "primitives": [item]}],
        }

    def test_basic_expansion(self):
        """Macro expands into a single wedge primitive."""
        data = self._make_data()
        result = preprocess(data)
        prims = result["meshes"][0]["primitives"]
        assert len(prims) == 1
        prim = prims[0]
        assert prim["type"] == "wedge"
        assert prim["id"] == "gable"

    def test_dimensions(self):
        """Dimensions should match leg lengths and extrusion length.

        After handedness swap: dim_x = |leg_q_original| = 1.5,
        dim_y = length = 0.15, dim_z = |leg_p_original| = 3.0.
        (Legs get swapped because cross(dir_p, N) · dir_q < 0.)
        """
        data = self._make_data()
        result = preprocess(data)
        prim = result["meshes"][0]["primitives"][0]
        dims = prim["dimensions"]
        # After swap: leg_p becomes [0,1.5,0] (|1.5|), leg_q becomes [-3,0,0] (|3|)
        assert dims["x"] == pytest.approx(1.5)
        assert dims["y"] == pytest.approx(0.15)
        assert dims["z"] == pytest.approx(3.0)

    def test_translation(self):
        """Translation = origin + leg_p/2 + leg_q/2 + N * length/2."""
        data = self._make_data()
        result = preprocess(data)
        prim = result["meshes"][0]["primitives"][0]
        t = prim["transform"]["translation"]
        # After swap: leg_p = [0,1.5,0], leg_q = [-3,0,0], N = [0,0,-1]
        # = [0,3,-2.425] + [0,0.75,0] + [-1.5,0,0] + [0,0,-0.075]
        # = [-1.5, 3.75, -2.5]
        assert t[0] == pytest.approx(-1.5)
        assert t[1] == pytest.approx(3.75)
        assert t[2] == pytest.approx(-2.5)

    def test_rotation_quat_present(self):
        """Expanded wedge should have rotation_quat."""
        data = self._make_data()
        result = preprocess(data)
        prim = result["meshes"][0]["primitives"][0]
        quat = prim["transform"]["rotation_quat"]
        assert len(quat) == 4
        # Verify it's a unit quaternion
        mag = math.sqrt(sum(q * q for q in quat))
        assert mag == pytest.approx(1.0, abs=1e-9)

    def test_rotation_quat_value(self):
        """Verify the specific quaternion for the gable case."""
        data = self._make_data()
        result = preprocess(data)
        prim = result["meshes"][0]["primitives"][0]
        quat = prim["transform"]["rotation_quat"]
        # Expected: (-0.5, -0.5, 0.5, 0.5)
        assert quat[0] == pytest.approx(-0.5, abs=1e-9)
        assert quat[1] == pytest.approx(-0.5, abs=1e-9)
        assert quat[2] == pytest.approx(0.5, abs=1e-9)
        assert quat[3] == pytest.approx(0.5, abs=1e-9)

    def test_simple_xy_plane(self):
        """Triangle on XY plane (normal +Z), legs along +X and +Y.

        Handedness swap occurs: cross((1,0,0), (0,0,1)) = (0,-1,0),
        dot with (0,1,0) = -1 < 0, so legs swap.
        After swap: dim_x = |leg_q| = 1.0, dim_z = |leg_p| = 2.0.
        """
        data = {
            "version": "0.12",
            "meshes": [
                {
                    "id": "m1",
                    "primitives": [
                        {
                            "macro": "triangle_prism_on_plane",
                            "id": "prism",
                            "plane": {"origin": [0, 0, 0], "normal": [0, 0, 1]},
                            "leg_p": [2.0, 0, 0],
                            "leg_q": [0, 1.0, 0],
                            "length": 0.5,
                        }
                    ],
                }
            ],
        }
        result = preprocess(data)
        prim = result["meshes"][0]["primitives"][0]
        assert prim["type"] == "wedge"
        dims = prim["dimensions"]
        # After handedness swap: x=|leg_q|=1.0, z=|leg_p|=2.0
        assert dims["x"] == pytest.approx(1.0)
        assert dims["y"] == pytest.approx(0.5)
        assert dims["z"] == pytest.approx(2.0)

    def test_material_inheritance(self):
        data = self._make_data(material="wall_mat")
        result = preprocess(data)
        prim = result["meshes"][0]["primitives"][0]
        assert prim["material"] == "wall_mat"

    def test_tags_inheritance(self):
        data = self._make_data(tags=["gable", "exterior"])
        result = preprocess(data)
        prim = result["meshes"][0]["primitives"][0]
        assert prim["tags"] == ["gable", "exterior"]

    def test_surface_inheritance(self):
        data = self._make_data(surface="gable_surface")
        result = preprocess(data)
        prim = result["meshes"][0]["primitives"][0]
        assert prim["surface"] == "gable_surface"

    def test_non_perpendicular_leg_error(self):
        """leg_p not perpendicular to normal should raise."""
        data = self._make_data()
        data["meshes"][0]["primitives"][0]["leg_p"] = [1.0, 0, 1.0]
        with pytest.raises(Exception, match="not perpendicular"):
            preprocess(data)

    def test_zero_length_leg_error(self):
        data = self._make_data()
        data["meshes"][0]["primitives"][0]["leg_p"] = [0, 0, 0]
        with pytest.raises(Exception, match="zero length"):
            preprocess(data)

    def test_zero_length_error(self):
        data = self._make_data(length=0)
        with pytest.raises(Exception, match="length must be > 0"):
            preprocess(data)

    def test_missing_plane_error(self):
        data = self._make_data()
        del data["meshes"][0]["primitives"][0]["plane"]
        with pytest.raises(Exception, match="plane"):
            preprocess(data)

    def test_handedness_swap(self):
        """Swapping leg_p and leg_q should produce the same wedge
        (legs are swapped internally to maintain right-handedness)."""
        data1 = self._make_data()
        data2 = self._make_data()
        # Swap legs
        data2["meshes"][0]["primitives"][0]["leg_p"] = [0, 1.5, 0]
        data2["meshes"][0]["primitives"][0]["leg_q"] = [-3.0, 0, 0]
        result1 = preprocess(data1)
        result2 = preprocess(data2)
        prim1 = result1["meshes"][0]["primitives"][0]
        prim2 = result2["meshes"][0]["primitives"][0]
        # Should produce same dimensions
        assert prim1["dimensions"] == prim2["dimensions"]
        # Same quaternion
        for i in range(4):
            assert prim1["transform"]["rotation_quat"][i] == pytest.approx(
                prim2["transform"]["rotation_quat"][i], abs=1e-9
            )
        # Same translation
        for i in range(3):
            assert prim1["transform"]["translation"][i] == pytest.approx(
                prim2["transform"]["translation"][i], abs=1e-9
            )
