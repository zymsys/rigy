# Rigy Specification — v0.11 Amendment (RC2)

**Status:** release candidate 2 / implementation-ready  
**Theme:** deterministic authoring helpers for hard-surface geometry  
**Builds on:** v0.10 (preprocessing, strict schemas, named surfaces, wedges)

---

## 1. Motivation

After implementing v0.10 and repeating an architectural probe (a simple house with doors, windows, and a roof), several remaining pain points
were consistently observed:

- Authoring wall openings requires verbose and error-prone manual segmentation.
- Center-origin primitives force unnecessary arithmetic for edge- and corner-based modeling.
- Semantic intent (“this is a wall / roof / opening frame”) is lost in flat primitive lists.
- Param substitution reduces duplication but does not eliminate derived-geometry fragility.

These issues indicate a need for a small set of **deterministic compile-time helpers** that expand into explicit primitives, preserving Rigy’s
role as a strict, geometry-level intermediate representation.

v0.11 addresses these gaps **without** introducing:
- boolean/CSG operations
- expressions / procedural logic
- runtime evaluation
- non-deterministic behavior

---

## 2. Coordinate System

Rigy uses a right-handed coordinate system with **Y-up**, consistent with glTF 2.0.

Any v0.11 macro that needs a vertical base MUST use `base_y`.

---

## 3. Scope of v0.11

v0.11 introduces three tightly scoped features:

1. Axis-aligned box specification via `aabb` (`min` / `max`)
2. Deterministic box decomposition macro (`box_decompose`)
3. Non-geometric semantic tagging of primitives (`tags`)

All features expand into explicit v0.10-compatible primitives **prior** to validation and tessellation.

---

## 4. Axis-Aligned Box Specification (`aabb`)

### 4.1 Rationale

Architectural modeling is naturally expressed in terms of edges and extents, not center points.

### 4.2 Syntax

```yaml
type: box
aabb:
  min: [x0, y0, z0]
  max: [x1, y1, z1]
```

### 4.3 Semantics (Normative)

- `min` and `max` MUST each contain exactly 3 finite numeric values.
- `max[i]` MUST be strictly greater than `min[i]` for i in {0,1,2}.
- `aabb` and `dimensions` are mutually exclusive.
- If `aabb` is present, the primitive MUST NOT specify:
  - `transform.translation`
  - any rotation field
  - `transform.scale`
- During preprocessing, the implementation MUST convert `aabb` into:
  - `dimensions = max − min`
  - `translation = (min + max) / 2`
- The resulting primitive is treated identically to a standard center-based `box`.

### 4.4 Validation

- Providing both `aabb` and `dimensions` is a ParseError.
- Unknown keys inside `aabb` are a ParseError.
- Any transform translation, rotation, or scale with `aabb` is a ParseError (**F115**).

---

## 5. Macro Placement and Expansion

### 5.1 Placement (Normative)

Macro blocks MUST appear as items inside `meshes[].primitives[]`.

### 5.2 Expansion Order (Normative)

Macro expansion MUST occur:
1. After v0.10 preprocessing (params, repeat)
2. Before primitive validation
3. Before tessellation

### 5.3 In-place Expansion

A macro item expands **in place**, replacing that item with the generated primitives.

---

## 6. Box Decomposition Macro (`box_decompose`)

### 6.1 Concept

`box_decompose` deterministically decomposes a box span with cutout rectangles into explicit box segment primitives.
No geometry subtraction or runtime logic is involved.

### 6.2 Axis / Coordinate Model (Normative)

- `axis`: direction of box length (`x` or `z`)
- height is always along `+y`
- thickness extrudes along the remaining horizontal axis

### 6.3 Syntax

```yaml
- macro: box_decompose
  id: south_wall
  mesh: walls_mesh
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

### 6.4 Validation (Normative)

- `span[0] < span[1]`
- `height > 0`, `thickness > 0`
- `axis` MUST be `x` or `z`
- `mesh` MUST reference an existing mesh ID
- `surface` MUST reference an existing surface name

For each cutout:
- `id` is required and MUST be a valid identifier
- `span[0] < span[1]`
- `bottom < top`
- `0 <= bottom`, `top <= height`
- Cutout MUST lie within box span
- Cutouts MUST NOT overlap in 2D

### 6.5 Output Primitive Type

`box_decompose` MUST expand into **box** primitives only.

### 6.6 Canonical Decomposition Algorithm

Let box span be `[A,B]`.

1. Sort cutouts by `(span.start, span.end, bottom, top)`.
2. Emit full-height gap segments between cutouts.
3. For each cutout:
   - Emit a below segment if `bottom > 0`
   - Emit an above segment if `top < height`
4. Emit no geometry for the cutout void.

### 6.7 Generated Primitive IDs

- Gap segments: `{id}_gap_{n}`
- Below: `{id}_{cutout_id}_below`
- Above: `{id}_{cutout_id}_above`

Collision with any user-defined primitive ID is a ValidationError (**F114**).

### 6.8 Surface and Tags

- All generated primitives inherit the macro's `surface`.
- All inherit macro `tags`.

---

## 7. Semantic Tags (`tags`)

- `tags` is an ordered list of strings.
- Tags do not affect geometry.
- Tags MUST be exported via glTF `extras`:

```json
"extras": { "rigy_tags": ["wall", "exterior"] }
```

---

## 8. Determinism Guarantee

Given identical input, macro expansion, geometry, and exported GLB MUST be byte-identical across implementations.

---

## 9. Non-Goals

v0.11 does not introduce:
- CSG
- expressions
- room topology
- multi-material meshes

---

## 10. Conformance Additions

### Positive Fixtures
- H110_box_aabb_basic
- H111_box_decompose_single_cutout
- H112_box_decompose_multi_cutout

### Negative Fixtures
- F114_macro_id_collision
- F115_aabb_with_transform
- F116_invalid_cutout_id

---

**End of Rigy v0.11 Amendment (RC2)**
