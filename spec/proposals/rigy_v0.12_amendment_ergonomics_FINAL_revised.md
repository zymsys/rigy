# Rigy v0.12 Amendment — Ergonomics Pass (Final, Revised)

> This amendment **replaces all prior v0.12 drafts**.
> Its purpose is to materially improve Rigy authoring ergonomics while strictly preserving the **Determinism Contract**.
>
> This document is **normative** unless explicitly marked non-normative.

---

## Summary of Changes

This amendment introduces the following general-purpose improvements:

1. **Numeric expressions** for numeric scalar fields, evaluated during preprocessing.
2. **Deterministic quantization** of computed numeric results.
3. **Axis–angle rotation authoring**, canonically normalized.
4. **Per-primitive materials**, removing the “one material per mesh” constraint (supersedes **V41**).
5. **Removal of the redundant `box_decompose.mesh` field**.
6. **Clarified scope of `aabb` authoring** (box-only).
7. **Version gating** for all new features in this amendment.

---

## 0. Version Gating (Normative)

All features introduced by this amendment require:

- `version: "0.12"` (or higher, if later versions exist).

If a document declares `version` lower than `"0.12"` and contains any of the following v0.12-only features, the compiler MUST raise a ValidationError:

- Expression scalars (`"=<expr>"`) in any numeric field
- `transform.rotation_axis_angle`
- `transform.rotation_quat`
- `mesh.material` (Section 4.1)
- `primitive.material` when used to override `mesh.material` (Section 4.1)
- Any v0.12-only `box_decompose` behavior described in Section 5

**V77 — FeatureRequiresNewerVersion**: raised when a v0.12-only feature is used under `version < "0.12"`.

(Notes: Existing strict-schema unknown-field behavior continues to apply; V77 is for “known but version-gated”.)

---

## 1. Preprocessing Pipeline (Normative)

Rigy compilation MUST perform preprocessing in the following order, producing a fully expanded, literal-only document prior to validation and emission:

1. Repeat expansion  
2. Parameter substitution  
3. **Unresolved-token check** (reject any `${...}` / `${` / `}`-style unresolved templates; existing behavior)  
4. **Expression evaluation** (Section 2)  
5. **Rotation normalization** (Section 3)  
6. **AABB expansion (box-only)**: `box.aabb → box.dimensions + transform.translation` (existing behavior; box-only)  
7. Macro expansion (`box_decompose`, etc.)  
8. Schema validation  
9. Deterministic emission

After preprocessing, the document MUST NOT contain:
- Expression strings
- `rotation_axis_angle`
- `aabb` (it must be expanded away)
- Deprecated or removed fields

---

## 2. Numeric Expressions (Normative)

### 2.1 Expression Scalars and Scope

Any field defined as a numeric scalar MAY instead be specified as an **expression scalar**:

- An expression scalar is a string beginning with `=`

Examples:

```yaml
dimensions: [=sqrt($run*$run + $rise*$rise), 0.1, 4.6]
translation: [0, =$wall_h + $rise/2, 0]
```

**Scope is intentionally unbounded**: expressions are permitted in *any* numeric scalar field in the schema (including, for example, material color components), subject to the same evaluation and determinism rules.

If a numeric field is not prefixed with `=`, it is treated as a literal.

---

### 2.2 Expression Language

Expressions MUST conform to the following grammar:

**Literals**
- Decimal numbers (e.g. `3`, `-0.25`, `4.0`)

**Parameters**
- `$name`, where `name` is a defined parameter

**Operators**
- Unary: `+`, `-`
- Multiplicative: `*`, `/`
- Additive: `+`, `-`

**Grouping**
- Parentheses `(...)`

**Functions**
- `min(a,b)`, `max(a,b)`
- `clamp(x, lo, hi)`
- `abs(x)`
- `sqrt(x)`
- `sin(x)`, `cos(x)`, `tan(x)` (radians)
- `atan2(y, x)` (radians)
- `deg2rad(x)`, `rad2deg(x)`

No other syntax is permitted.

---

### 2.3 Evaluation & Quantization (Determinism Anchor)

Expression evaluation MUST proceed as follows:

1. Parse expression into an AST.
2. Substitute all `$param` references with their numeric values.
3. Evaluate using **IEEE-754 binary64** arithmetic.
4. If any intermediate or final value is non-finite (`NaN`, `±Inf`), raise **ValidationError V70**.
5. Quantize the final value using step `q = 1e-9`:
   ```
   x := round(x / q) * q
   ```
6. Canonicalize `-0.0` to `0.0`.

The quantized value replaces the expression during preprocessing.

---

### 2.4 Expression Errors (Normative)

The following ValidationErrors MUST be raised during preprocessing:

| Code | Condition |
|----|----|
| **V68** | Expression parse error (invalid grammar, token, function, or arity) |
| **V69** | Expression references an unknown parameter |
| **V70** | Expression evaluation produced a non-finite result |
| **V71** | Expression domain error (e.g. `sqrt(x)` with `x < 0`) |

---

## 3. Rotation Authoring and Canonical Form (Normative)

### 3.1 Rotation Forms

`transform` MAY specify rotation using exactly one of the following authoring forms:

- `rotation_degrees` (existing)
- `rotation_euler` (existing, if supported)
- `rotation_axis_angle` (new in v0.12)
- `rotation_quat` (new in v0.12; canonical)

Example axis–angle:

```yaml
transform:
  rotation_axis_angle:
    axis: [0, 0, 1]
    degrees: 26.565051177
```

Example quaternion:

```yaml
transform:
  rotation_quat: [0, 0, 0, 1]
```

### 3.2 Validation

| Code | Condition |
|----|----|
| **V67** | Axis vector has length ≤ 1e-12 |
| **V72** | Multiple rotation authoring forms specified |
| **V73** | Non-finite axis / degrees / quaternion component |
| **V78** | Quaternion has length ≤ 1e-12 (zero-length / invalid quaternion) |

A zero-length axis MUST NOT be treated as identity.

### 3.3 Canonical Normalization (Rotation Normalization Step)

During preprocessing step 5, all rotations MUST be normalized to the canonical quaternion form:

- `transform.rotation_quat: [x, y, z, w]`

Canonicalization rules:

**If rotation is provided as axis–angle:**
1. Normalize the axis vector.
2. Convert degrees → radians.
3. Convert to quaternion `(x,y,z,w)` in float64.
4. Normalize quaternion.
5. If `w < 0`, negate all components.
6. Quantize each component to `1e-12`, canonicalize `-0 → 0`.
7. Write `rotation_quat` and remove `rotation_axis_angle`.

**If rotation is provided as Euler / degrees:**
- The implementation MUST convert it to a quaternion deterministically (same steps 4–6 above), then write `rotation_quat`.
- The original Euler authoring fields MUST NOT remain in the preprocessed output.

**If rotation is provided as quaternion:**
- Validate finite components, validate length > 1e-12, normalize, apply sign rule, quantize, canonicalize -0.

Downstream compilation stages (tessellation, skinning, export) MUST read rotation from `rotation_quat` only.

---

## 4. Per-Primitive Materials (Normative)

> This change **supersedes V41** (“one material per mesh”).

### 4.1 Schema Changes and Resolution

This amendment introduces an optional mesh-level default material:

- `meshes[].material` (NEW in v0.12): optional default material key for primitives in that mesh.
- `primitive.material` (existing in many versions) remains supported as an override.

Resolution order:
```
primitive.material ?? mesh.material
```

If no material resolves, raise **ValidationError V74**.

### 4.2 glTF Emission Mapping

- Each Rigy mesh emits **one glTF mesh**.
- Each Rigy primitive emits **one glTF primitive**.
- **Ordering is preserved**: glTF `primitives[i]` corresponds to Rigy `primitives[i]`.

For debugging/tooling, the Rigy primitive ID MUST be stored in glTF primitive extras:

```json
"extras": { "rigy_id": "<primitive.id>" }
```

### 4.3 Tessellation / Skinning Implications (Normative)

Because a Rigy primitive maps 1:1 to a glTF primitive:

- Each glTF primitive MUST have its own attribute accessors (POSITION, NORMAL, etc.) and its own indices accessor.
- If skinning is enabled, each glTF primitive MUST have its own JOINTS_0 and WEIGHTS_0 accessors.

Implementations MAY pack multiple primitives’ data into shared buffer(s) for efficiency, but MUST expose **separate accessors per glTF primitive** and preserve the ordering contract above.

### 4.4 Material Errors

| Code | Condition |
|----|----|
| **V74** | No material resolved for primitive |
| **V75** | Primitive references unknown material |

---

## 5. `box_decompose.mesh` Removal (Normative)

- The `mesh` field inside `box_decompose` is REMOVED.
- Expansion target is implicitly the containing mesh.

If `box_decompose.mesh` is present:
- It MUST match the containing mesh ID.
- Otherwise raise **ValidationError V76**.
- The field is discarded during preprocessing.

---

## 6. `aabb` Scope Clarification (Normative)

- `aabb` authoring is valid **only** for `primitive.type: box`.
- AABB expansion MUST occur during preprocessing (Step 6), producing `dimensions` and `transform.translation`.
- Error messages involving AABB constraints MUST explicitly reference `box.aabb`.

---

## 7. Conformance Impact (Normative)

This amendment changes conformance expectations in:

- Numeric preprocessing (expressions + quantization)
- Rotation canonicalization (`rotation_quat` canonical form)
- Material emission semantics (multi-material meshes; supersedes V41)
- Macro expansion behavior (`box_decompose` implicit targeting)
- AABB preprocessing placement in the pipeline

New conformance fixtures MUST be added covering:
- Expression evaluation and quantization (including V68–V71)
- Version gating (V77)
- Axis–angle canonicalization and rotation_quat normalization (including V67, V78)
- Mixed-material meshes + extras mapping + separate accessors
- `box_decompose` implicit targeting and mismatch error (V76)
- AABB expansion ordering

---

## Closing Note

This amendment introduces **authoring computation without authoring ambiguity**.
All new features resolve to a literal, canonical Rigy document before validation and emission, preserving Rigy’s core guarantee:

> **Same YAML → same GLB, byte-for-byte.**
