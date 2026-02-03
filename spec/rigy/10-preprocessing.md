# 10. Preprocessing

*Introduced in v0.10, extended in v0.11.*

## 10.1 Preprocessing Stage (Normative)

A Rigy v0.11 implementation MUST apply the following preprocessing steps **in this order**:

1. YAML load with duplicate mapping key detection
2. `repeat` macro expansion
3. `params` substitution
4. `aabb` conversion (v0.11)
5. `box_decompose` macro expansion (v0.11)
6. Schema validation (strict everywhere)
7. Semantic validation
8. Export

Stages 2-5 operate on the raw YAML object model (mappings, sequences, scalars).
Stages 6-8 operate on the schema-defined model.

The output of preprocessing MUST be a canonical Rigy document containing:

* no `repeat` blocks
* no `$param` tokens
* no unresolved `${...}` tokens
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
radius: 2 * $r          # expressions not allowed
id: "leg_$r"            # string interpolation not allowed
dimensions: $dims       # non-scalar param
params:
  x: ${i}               # param indirection not allowed
```

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

### Syntax

```yaml
- macro: box_decompose
  id: south_wall
  mesh: walls_mesh
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

### Placement (Normative)

Macro blocks MUST appear as items inside `meshes[].primitives[]`.

### Expansion Order (Normative)

Macro expansion MUST occur:
1. After v0.10 preprocessing (params, repeat)
2. Before primitive validation
3. Before tessellation

A macro item expands **in place**, replacing that item with the generated primitives.

### Validation (Normative)

- `span[0] < span[1]`
- `height > 0`, `thickness > 0`
- `axis` MUST be `x` or `z`
- `mesh` MUST reference an existing mesh ID
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

- `material` — required if the containing mesh has other primitives with materials (V41)
- `surface` — user-defined label
- `tags` — semantic tag list

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

## 10.7 Preprocessing Validation

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
| F114 | `box_decompose` generated ID collides with user-defined ID | ValidationError |
| F115 | `aabb` used with transform (translation/rotation/scale) | ParseError |
| F116 | Invalid cutout ID in `box_decompose` | ParseError |

---

**End of Chapter 10**
