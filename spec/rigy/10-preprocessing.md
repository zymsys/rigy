# 10. Preprocessing

*Introduced in v0.10, extended in v0.11 and v0.12.*

## 10.1 Preprocessing Stage (Normative)

A Rigy v0.12 implementation MUST apply the following preprocessing steps **in this order**:

1. YAML load with duplicate mapping key detection
2. `repeat` macro expansion
3. `params` substitution
4. Unresolved-token check (reject any `${...}` remaining after step 3)
5. Expression evaluation (v0.12) — see [Section 10.8](#108-expression-scalars-v012)
6. Rotation normalization (v0.12) — see [Section 10.9](#109-rotation-authoring-and-canonical-form-v012)
7. `aabb` conversion (v0.11, box-only)
8. `box_decompose` macro expansion (v0.11)
9. Schema validation (strict everywhere)
10. Semantic validation
11. Export

Stages 2–8 operate on the raw YAML object model (mappings, sequences, scalars).
Stages 9–11 operate on the schema-defined model.

The output of preprocessing MUST be a canonical Rigy document containing:

* no `repeat` blocks
* no `$param` tokens
* no unresolved `${...}` tokens
* no expression strings (no `"=<expr>"` values)
* no `rotation_axis_angle` fields (canonicalized to `rotation_quat`)
* no `rotation_degrees` or `rotation_euler` fields (canonicalized to `rotation_quat` in v0.12+)
* no `aabb` fields (converted to `dimensions` + `translation`)
* no `box_decompose` macros (expanded to explicit primitives)

### Duplicate YAML Mapping Keys (Clarified)

Duplicate YAML mapping keys MUST be detected **globally** and rejected (V56).

This requirement applies to:

* Top-level mappings
* Nested objects
* Maps such as `materials`, `uv_roles`, etc.

Silently accepting "last key wins" behavior is non-conformant.

### Strict Schema Enforcement (Expanded)

All objects defined by the Rigy schema MUST reject unknown keys (V57).

This rule applies universally, including:

* Top-level document keys
* Meshes, primitives, armatures, bones
* Materials and material property maps
* UV role definitions
* Bindings and weight structures

No extension or vendor-specific keys are permitted unless explicitly defined by the specification.

### Tooling-Only Top-Level Allowance

A small, explicit allowlist of tooling-only top-level blocks MAY appear and MUST be ignored by the Rigy compiler for geometry/export behavior.

For v0.12, the allowlist contains exactly:

* `geometry_checks`

`geometry_checks` is:

* optional (never required)
* ignored by validation
* ignored by determinism
* ignored by export

Its contents are non-semantic for Rigy compilation and MUST NOT influence any Rigy behavior.

### `geometry_checks.alignment` — Alignment Assertions

The `alignment` key inside `geometry_checks` defines a list of alignment assertions evaluated by the `rigy inspect --intent-checks` tooling command. Each entry specifies a check type and references derived features of primitives.

```yaml
geometry_checks:
  alignment:
    - check: normal_parallel
      a: gable_front_left.slope_face
      b: roof_left.+y
      label: "left gable slope matches left roof top"
    - check: point_on_line
      point: chimney.apex
      line: roof_left.ridge
      label: "chimney apex sits on roof ridge"
```

**Check types:**

| Check | Parameters | Semantics |
|-------|-----------|-----------|
| `normal_parallel` | `a`, `b` (face feature refs) | Passes when `|cross(n_a, n_b)| < tolerance` |
| `point_on_line` | `point` (point ref), `line` (line ref) | Passes when distance from point to line `< tolerance` |

Each parameter uses the format `primitive_id.feature_name`.

**Derived features by primitive type:**

| Type | Feature | Kind | Description |
|------|---------|------|-------------|
| box | `+x`, `-x`, `+y`, `-y`, `+z`, `-z` | face | Surface face normal and center |
| wedge | `+y`, `-y`, `-x`, `-z`, `slope` | face | Surface face normal and center |
| wedge | `slope_face` | face | Alias for the slope surface |
| wedge | `apex` | point | Centroid of the +y triangle |
| wedge | `ridge` | line | Top edge on the -x face (v3→v5) |

Each check result includes:
- `pass`: `true`, `false`, or `null` (if unresolvable)
- `error`: string (when `pass` is `null`)
- `cross_magnitude` or `distance`: numeric diagnostic value

`tolerance` defaults to `1e-6` for both check types.

---

## 10.2 `params` — Compile-Time Constants (Normative)

*Introduced in v0.10.*

### Definition

A Rigy document MAY define a top-level `params` mapping:

```yaml
params:
  <param_id>: <scalar>
```

Where `<scalar>` MUST be one of:

* number (finite)
* string
* boolean

Lists and mappings are not permitted as param values (V58).

### Param Identifier Grammar (Normative)

A parameter identifier MUST match:

```
^[A-Za-z_][A-Za-z0-9_]*$
```

### Param Reference Grammar (Normative)

A param reference is a **scalar string** whose entire value matches:

```
^\$[A-Za-z_][A-Za-z0-9_]*$
```

Only exact matches are substituted.

### Substitution Rules

* `$param_id` replaces the entire scalar value
* Substitution is type-preserving
* Referencing an undeclared param is an error (V59)
* Param values are literal and are **not** further expanded

### Prohibited Forms

The following are invalid in v0.10+:

```yaml
radius: 2 * $r          # no = prefix; not an expression (use "=2 * $r" in v0.12+)
id: "leg_$r"            # string interpolation not allowed
dimensions: $dims       # non-scalar param
params:
  x: ${i}               # param indirection not allowed
```

> **Note (v0.12):** `radius: "=2 * $r"` is valid in v0.12+ as an expression scalar (see [Section 10.8](#108-expression-scalars-v012)). The bare form `radius: 2 * $r` (without the `=` prefix) remains invalid.

### Post-Preprocessing Rule

After preprocessing, the expanded document MUST NOT contain the key `params`.

---

## 10.3 `repeat` Macro — Pure Expansion (Normative)

*Introduced in v0.10.*

### Purpose

`repeat` provides deterministic duplication of schema objects in list contexts without introducing logic or expressions.

### Allowed Contexts (v0.10+)

A `repeat` macro MAY appear only as a **list element** where a list of objects is expected, including:

* `meshes[].primitives[]`
* `armatures[].bones[]`
* `anchors[]`
* `bindings[]`
* `bindings[].weights[]`
* `bindings[].weight_maps[]`

`repeat` is not permitted inside mapping contexts (e.g., `materials`) (V64).

### Recognition Rule (Normative)

A list element is a `repeat` macro **if and only if** it is a mapping with exactly one key:

```yaml
repeat
```

Any other use of a `repeat` key MUST be rejected (V64).

### Structure

```yaml
- repeat:
    count: <integer >= 0>
    as: <identifier>
    body: <object>
```

Rules:

* `count` MUST be an integer >= 0 (V62)
* `as` MUST be a valid identifier (V63)
* `body` MUST be a single object
* `count: 0` expands to an empty sequence

### Index Token Grammar (Normative)

An index token is a substring matching:

```
\$\{[A-Za-z_][A-Za-z0-9_]*\}
```

### Substitution Semantics

Within a repeat expansion for `as: i`:

* `${i}` is substituted with the current zero-based index
* Substitution occurs during macro expansion only

Numeric vs string behavior:

| Input            | Output (i = 3)       |
| ---------------- | -------------------- |
| `"${i}"`         | `3` (number)         |
| `"picket${i}"`   | `"picket3"` (string) |
| `["${i}", 0, 0]` | `[3, 0, 0]`          |

### Unresolved Tokens

Any `${...}` token remaining after preprocessing MUST be rejected (V65).

### Identifier Collisions After Expansion

After preprocessing, all identifier uniqueness rules apply.

Any identifier collision detected after preprocessing MUST be rejected with error code **V66**, regardless of whether the collision originated from a macro or manual duplication.

---

## 10.4 Axis-Aligned Box Specification (`aabb`)

*Introduced in v0.11.*

### Rationale

Architectural modeling is naturally expressed in terms of edges and extents, not center points.

### Syntax

```yaml
type: box
aabb:
  min: [x0, y0, z0]
  max: [x1, y1, z1]
```

### Scope (v0.12 Clarification)

`aabb` authoring is valid **only** for primitives with `type: box`. Error messages involving AABB constraints MUST explicitly reference `box.aabb`.

### Semantics (Normative)

- `min` and `max` MUST each contain exactly 3 finite numeric values.
- `max[i]` MUST be strictly greater than `min[i]` for i in {0,1,2}.
- `aabb` and `dimensions` are mutually exclusive.
- If `aabb` is present, the primitive MUST NOT specify:
  - `transform.translation`
  - any rotation field
  - `transform.scale`
- During preprocessing, the implementation MUST convert `aabb` into:
  - `dimensions = max - min`
  - `translation = (min + max) / 2`
- The resulting primitive is treated identically to a standard center-based `box`.

### Validation

- Providing both `aabb` and `dimensions` is a ParseError.
- Unknown keys inside `aabb` are a ParseError.
- Any transform translation, rotation, or scale with `aabb` is a ParseError (**F115**).

---

## 10.5 Box Decomposition Macro (`box_decompose`)

*Introduced in v0.11.*

### Concept

`box_decompose` deterministically decomposes a box span with cutout rectangles into explicit box segment primitives. No geometry subtraction or runtime logic is involved.

### Axis / Coordinate Model (Normative)

- `axis`: direction of box length (`x` or `z`)
- height is always along `+y`
- thickness extrudes along the remaining horizontal axis

### Offset Semantics (Normative)

The `offset` parameter specifies the perpendicular displacement of the wall centerline, measured along the axis orthogonal to both the length axis and height (Y).

| `axis` | Wall extends along | Thickness along | `offset` displaces |
|--------|-------------------|-----------------|-------------------|
| `x` | X | Z | Z coordinate |
| `z` | Z | X | X coordinate |

**Example**: For `axis: x`, `thickness: 0.2`, `offset: 3.0`:
- Wall spans along X axis
- Wall has depth 0.2m in Z
- Wall centerline sits at Z=3.0 (spans Z=2.9 to Z=3.1)

> **Tip:** To place a wall with a specific face at coordinate `F`, compute `offset` from `F` and `thickness`:
> - Face on the **positive** side at `F`: `offset = F - thickness/2`
> - Face on the **negative** side at `F`: `offset = F + thickness/2`
>
> For example, a front wall (`axis: x`) with its outer face at Z=−2.5 and `thickness: 0.2` needs `offset: -2.4` (i.e., −2.5 + 0.1).

**Face-Placement Reference** (let `t = thickness`):

For `axis: x` (wall spans X, thickness along Z, offset controls Z):

| Desired constraint | Formula |
|--------------------|---------|
| Place outer face at `Z = Z_outer` (more **negative** Z side, e.g. front wall) | `offset = Z_outer + t/2` |
| Place outer face at `Z = Z_outer` (more **positive** Z side, e.g. back wall) | `offset = Z_outer - t/2` |
| Place centerline at `Z = Zc` | `offset = Zc` |

For `axis: z` (wall spans Z, thickness along X, offset controls X):

| Desired constraint | Formula |
|--------------------|---------|
| Place outer face at `X = X_outer` (more **negative** X side, e.g. left wall) | `offset = X_outer + t/2` |
| Place outer face at `X = X_outer` (more **positive** X side, e.g. right wall) | `offset = X_outer - t/2` |
| Place centerline at `X = Xc` | `offset = Xc` |

### Syntax

```yaml
- macro: box_decompose
  id: south_wall
  material: wall_mat
  surface: exterior_wall

  axis: x
  span: [0.0, 8.0]
  base_y: 0.0
  height: 2.7

  thickness: 0.2
  offset: 0.0

  cutouts:
    - id: front_door
      span: [3.5, 4.5]
      bottom: 0.0
      top: 2.1
```

### `offset_mode` Convenience (v0.12)

As a convenience, `offset_mode` provides named offset presets that compute `offset` from `thickness`:

| `offset_mode` | Computed `offset` | Semantics |
|----------------|-------------------|-----------|
| `centerline` | `0.0` | Wall center sits on the reference line |
| `neg_face` | `+thickness / 2` | Negative-axis face touches the reference line |
| `pos_face` | `-thickness / 2` | Positive-axis face touches the reference line |

`offset` and `offset_mode` are **mutually exclusive**. Specifying both is a ParseError.

If neither `offset` nor `offset_mode` is present, `offset` defaults to `0.0`.

### Placement (Normative)

Macro blocks MUST appear as items inside `meshes[].primitives[]`.

### Expansion Order (Normative)

Macro expansion MUST occur:
1. After v0.10 preprocessing (params, repeat)
2. Before primitive validation
3. Before tessellation

A macro item expands **in place**, replacing that item with the generated primitives.

### `mesh` Field Removal (v0.12)

The `mesh` field inside `box_decompose` is **removed** in v0.12. Expansion target is implicitly the containing mesh.

If `box_decompose.mesh` is present:
- It MUST match the containing mesh ID.
- Otherwise raise **ValidationError V76** (`box_decompose.mesh` mismatch).
- The field is discarded during preprocessing.

### Validation (Normative)

- `span[0] < span[1]`
- `height > 0`, `thickness > 0`
- `axis` MUST be `x` or `z`
- `material` (if present) MUST reference an existing material ID
- `surface` is an optional user-defined label (no registry required)

For each cutout:
- `id` is required and MUST be a valid identifier
- `span[0] < span[1]`
- `bottom < top`
- `0 <= bottom`, `top <= height`
- Cutout MUST lie within box span
- Cutouts MUST NOT overlap in 2D

### Output Primitive Type

`box_decompose` MUST expand into **box** primitives only.

### Canonical Decomposition Algorithm

Let box span be `[A,B]`.

1. Sort cutouts by `(span.start, span.end, bottom, top)`.
2. Emit full-height gap segments between cutouts.
3. For each cutout:
   - Emit a below segment if `bottom > 0`
   - Emit an above segment if `top < height`
4. Emit no geometry for the cutout void.

### Generated Primitive IDs

- Gap segments: `{id}_gap_{n}`
- Below: `{id}_{cutout_id}_below`
- Above: `{id}_{cutout_id}_above`

Collision with any user-defined primitive ID is a ValidationError (**F114**).

### Inherited Fields

All generated primitives inherit the following fields from the macro (when present):

- `surface` — user-defined label
- `tags` — semantic tag list

**Material inheritance (Normative):**

If `box_decompose.material` is present, each generated primitive MUST set `material` to that value.
If `box_decompose.material` is omitted, generated primitives MUST omit `material`, and normal material resolution applies per [Chapter 8](08-materials.md):

```
generated_primitive.material ?? mesh.material
```

If a `materials` table exists and no material resolves via this chain, raise **ValidationError V74**.

---

## 10.6 Semantic Tags (`tags`)

*Introduced in v0.11.*

- `tags` is an ordered list of strings.
- Tags do not affect geometry.
- Tags MUST be exported via glTF `extras`:

```json
"extras": { "rigy_tags": ["wall", "exterior"] }
```

---

## 10.7 Triangle Prism on Plane Macro (`triangle_prism_on_plane`)

*Introduced in v0.12.*

### Concept

`triangle_prism_on_plane` defines a triangular prism (wedge) by specifying a construction plane, two leg vectors lying in that plane, and an extrusion length along the plane normal. The macro expands to a single `wedge` primitive with computed dimensions, rotation quaternion, and translation.

### Syntax

```yaml
- macro: triangle_prism_on_plane
  id: gable_front_left
  material: wall
  plane:
    origin: [0, 3.0, -2.425]
    normal: [0, 0, -1]
  leg_p: [-3.0, 0, 0]
  leg_q: [0, 1.5, 0]
  length: 0.15
```

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | identifier | yes | Primitive ID for the generated wedge |
| `plane.origin` | `[x, y, z]` | yes | Triangle vertex at the right angle |
| `plane.normal` | `[x, y, z]` | yes | Extrusion direction (normalized internally) |
| `leg_p` | `[x, y, z]` | yes | Direction and length of the first leg from origin |
| `leg_q` | `[x, y, z]` | yes | Direction and length of the second leg from origin |
| `length` | number > 0 | yes | Extrusion distance along normal |
| `material` | string | no | Inherited by the generated wedge |
| `tags` | list | no | Inherited by the generated wedge |
| `surface` | string | no | Inherited by the generated wedge |

### Validation

- `leg_p` and `leg_q` MUST be perpendicular to `plane.normal` (within tolerance `1e-6`)
- `leg_p`, `leg_q`, and `plane.normal` MUST have non-zero length
- `length` MUST be positive and finite
- All numeric values MUST be finite

### Expansion Algorithm

1. Normalize the plane normal **N**.
2. Compute `dir_p = normalize(leg_p)`, `dir_q = normalize(leg_q)`.
3. Check handedness: if `cross(dir_p, N) · dir_q < 0`, swap `leg_p` ↔ `leg_q` (and their derived values).
4. Build rotation matrix `R = [dir_p | N | dir_q]` (column vectors), mapping wedge local axes (X, Y, Z) to world axes.
5. Convert `R` to quaternion via Shepperd's method, then canonicalize (normalize, sign rule, quantize).
6. Dimensions: `x = |leg_p|`, `y = length`, `z = |leg_q|` (after any swap).
7. Translation: `origin + leg_p/2 + leg_q/2 + N * length/2`.

### Output

A single wedge primitive with `rotation_quat` and `translation` in its transform.

---

## 10.8 Expression Scalars (v0.12)

*Introduced in v0.12.*

### Scope

Any field defined as a numeric scalar MAY instead be specified as an **expression scalar**: a YAML string beginning with `=`.

```yaml
dimensions: [=sqrt($run*$run + $rise*$rise), 0.1, 4.6]
translation: [0, =$wall_h + $rise/2, 0]
```

**Scope is intentionally unbounded**: expressions are permitted in *any* numeric scalar field in the schema (including, for example, material color components), subject to the same evaluation and determinism rules.

Expression scalars are valid wherever a numeric scalar is accepted, including inside numeric sequences such as `dimensions`, `translation`, and `base_color`.

```yaml
# Expression inside a mapping value
dimensions:
  x: "=sqrt($half_w * $half_w + $rise * $rise)"
  y: $roof_t
  z: $house_depth

# Expression inside a list
translation: [1.0, "=3.0 + $rise", 0.0]
```

If a numeric field is not prefixed with `=`, it is treated as a literal.

Expression scalars require `version: "0.12"` or later (V77).

### Expression Language

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

### Evaluation & Quantization

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

### Expression Errors

| Code | Condition |
|------|-----------|
| **V68** | Expression parse error (invalid grammar, token, function, or arity) |
| **V69** | Expression references an unknown parameter |
| **V70** | Expression evaluation produced a non-finite result |
| **V71** | Expression domain error (e.g. `sqrt(x)` with `x < 0`) |

---

## 10.9 Rotation Authoring and Canonical Form (v0.12)

*Introduced in v0.12.*

### Rotation Forms

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

`rotation_axis_angle` and `rotation_quat` require `version: "0.12"` or later (V77).

### Rotation Validation

| Code | Condition |
|------|-----------|
| **V67** | Axis vector has length ≤ 1e-12 |
| **V72** | Multiple rotation authoring forms specified |
| **V73** | Non-finite axis / degrees / quaternion component |
| **V78** | Quaternion has length ≤ 1e-12 (zero-length / invalid quaternion) |

A zero-length axis MUST NOT be treated as identity.

### Canonical Normalization

During preprocessing step 6, all rotations MUST be normalized to the canonical quaternion form:

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

## 10.10 Preprocessing Validation

| ID | Check | Error Type |
|----|-------|-----------|
| V56 | Duplicate YAML mapping key detected | ParseError |
| V57 | Unknown field encountered (strict schema) | ParseError |
| V58 | `params` contains non-scalar or invalid value | ParseError |
| V59 | `$param` references unknown parameter | ParseError |
| V60 | Invalid `$param` usage (not whole-scalar) | ParseError |
| V61 | Param type mismatch | ParseError |
| V62 | `repeat.count` invalid | ParseError |
| V63 | `repeat.as` invalid identifier | ParseError |
| V64 | Invalid `repeat` structure or placement | ParseError |
| V65 | Unresolved `${...}` token after preprocessing | ParseError |
| V66 | Identifier collision after preprocessing | ValidationError |
| V67 | Axis vector has length ≤ 1e-12 | ValidationError |
| V68 | Expression parse error (invalid grammar, token, function, or arity) | ValidationError |
| V69 | Expression references an unknown parameter | ValidationError |
| V70 | Expression evaluation produced a non-finite result | ValidationError |
| V71 | Expression domain error (e.g. `sqrt(x)` with `x < 0`) | ValidationError |
| V72 | Multiple rotation authoring forms specified | ValidationError |
| V73 | Non-finite axis / degrees / quaternion component | ValidationError |
| V74 | No material resolved for primitive (v0.12+) | ValidationError |
| V75 | Primitive references unknown material (v0.12+) | ValidationError |
| V76 | `box_decompose.mesh` does not match containing mesh ID | ValidationError |
| V77 | v0.12-only feature used under `version < "0.12"` | ValidationError |
| V78 | Quaternion has length ≤ 1e-12 (zero-length / invalid) | ValidationError |
| F114 | `box_decompose` generated ID collides with user-defined ID | ValidationError |
| F115 | `aabb` used with transform (translation/rotation/scale) | ParseError |
| F116 | Invalid cutout ID in `box_decompose` | ParseError |

---

**End of Chapter 10**
