# Rigy Proposal — Deterministic Implicit Surfaces

## `implicit_surface@1`

**Status:** Draft (unscheduled)
**Category:** Geometry / Tessellation
**Theme:** *Organic form with explicit determinism*

---

## 1. Motivation

Rigy currently supports only closed-form primitives whose surfaces are defined analytically and tessellated deterministically. While this enables architectural and mechanical modeling, it prevents expression of:

* Organic unions (beans, rocks, base creature forms)
* Localized sculpting edits (chips, gouges, dents)

This proposal introduces a **constrained implicit surface system** that defines geometry as an isosurface of a scalar field, sampled and tessellated deterministically at compile time.

The design goal is to enable authoring workflows such as:

> "Nice rock. Now knock a chip out of it here."

…while preserving Rigy's core contract:

> **For a given input document, Rigy version, and conformance suite, a conforming implementation MUST emit byte-identical GLB output.**

---

## 1.1 Lossy but Deterministic (Normative Clarification)

Implicit surfaces are sampled on a finite grid and converted to triangles via a fixed extraction algorithm. This introduces quantization loss relative to the mathematical field definition.

This loss is **intentional and bounded**.

Despite this, all evaluation, traversal, and emission rules are fully specified. Determinism is preserved.

---

## 2. Non-Goals (Initial Scope)

The following are explicitly out of scope for the initial implementation:

* Triangle-mesh boolean operations
* Unbounded signed-distance fields
* Procedural noise or domain warping
* UV generation for implicit topology
* Vertex welding or topology optimization
* Vertex-level skinning inference
* Runtime or dynamic field evaluation

These are deferred to follow-on work (see §15 Future Extensions).

---

## 3. New Primitive: `implicit_surface`

### 3.1 Version Gate (Normative)

Use of `type: implicit_surface`:

* REQUIRES the adopting spec version or later
* MUST raise **ValidationError V67** otherwise

---

### 3.2 Schema

```yaml
- id: <primitive_id>
  type: implicit_surface
  domain:
    aabb:
      min: [x0, y0, z0]
      max: [x1, y1, z1]
    grid:
      nx: <int>
      ny: <int>
      nz: <int>
  iso: <float64>
  ops:
    - op: add | subtract
      field: <field_id>
      strength: <float64>
      ...field parameters...
      transform: <transform>
  extraction:
    algorithm: marching_cubes@1   # optional; defaults to marching_cubes@1
```

---

### 3.3 Required Fields

* `domain.aabb.min`, `domain.aabb.max`

  * Exactly three finite float64 values each
  * `max[i] > min[i]` for all axes
* `domain.grid.nx|ny|nz`

  * Integers ≥ 2
* `iso`

  * Finite float64
* `ops`

  * Non-empty list
* `field` identifiers MUST be from the field vocabulary defined in this proposal

---

### 3.4 Optional Fields

* `material`
* `tags`
* `extraction`

  * If omitted, `marching_cubes@1` is assumed

Material and tag behavior is unchanged from existing primitives.

---

### 3.5 Field Operator Transform Constraints (Normative)

Field operators reuse the standard Rigy `Transform` object, but this proposal constrains it as follows:

**Allowed**

* `translation`
* `rotation_degrees` (or `rotation_euler`, consistent with the existing Transform mutual exclusivity rules)
* `scale` **only if uniform** (`sx == sy == sz`)

**Forbidden (ValidationError V73)**

* Non-uniform scale (`sx`, `sy`, `sz` not all equal)
* Any shear transform (if representable)
* Any transform fields not present in the standard Transform model

**Notes**

* If rotation is present, it MUST follow the same mutual exclusivity rules as existing Transform usage (providing both `rotation_degrees` and `rotation_euler` is a ParseError).
* Uniform scale is applied in operator-local space before translation.

---

## 4. Field Evaluation Model

### 4.1 Field Combination (Normative)

Each operator defines a **bounded scalar contribution** `Ci(x)`.

The total scalar field is:

```
F(x) = Σ Ci(x)
```

The implicit surface is defined by:

```
F(x) = iso
```

---

### 4.2 Operator Polarity (Normative)

The `op` field applies a sign:

* `op: add` → contribution as defined
* `op: subtract` → contribution multiplied by `-1`

This rule applies uniformly to all field types.

---

### 4.3 Practical `iso` Guidance (Non-Normative)

For `metaball_*@1` fields, `iso = 0.0` places the surface at the field's zero boundary and produces little visible blending between adjacent blobs. For organic merging, authors typically use `iso` in the range **0.1–0.5 relative to the dominant `strength`**, depending on overlap distance and desired surface thickness.

Higher `iso` values shrink the surface inward and increase the blending region between overlapping operators. Lower values expand the surface outward and reduce blending.

---

## 5. Field Vocabulary

All field functions defined in this proposal are:

* Bounded
* Compactly supported
* Monotonic with distance
* Evaluated in float64

### 5.1 `metaball_sphere@1`

**Parameters**

* `radius > 0`
* `strength > 0`

**Definition**

Let `r = ||p||` in operator-local space.

```
if r >= radius:
  contribution = 0
else:
  t = 1 - r / radius
  contribution = strength * t * t
```

---

### 5.2 `metaball_capsule@1`

**Parameters**

* `radius > 0`
* `height > 0`
* `strength > 0`

**Geometry (Normative)**

In operator-local space:

```
A = (0, -height/2, 0)
B = (0, +height/2, 0)

t = clamp( dot(p - A, B - A) / ||B - A||², 0, 1 )
q = A + t * (B - A)
d = ||p - q||
```

**Contribution**

```
if d >= radius:
  contribution = 0
else:
  t = 1 - d / radius
  contribution = strength * t * t
```

---

### 5.3 `sdf_sphere@1` (Bounded, Monotonic)

**Parameters**

* `radius > 0`
* `strength > 0`

Let `r = ||p||`, `d = r - radius`.

```
if d >= radius:
  contribution = 0
elif d <= -radius:
  contribution = strength
else:
  contribution = strength * (1 - d / radius) / 2
```

Used with `op: subtract`, this produces a localized carving effect.

---

### 5.4 `sdf_capsule@1`

**Geometry**

Same capsule segment definition as §5.2.

Let:

```
d = ||p - q|| - radius
```

**Contribution**

Identical bounded, monotonic rule as §5.3.

**Note:** For `sdf_capsule@1`, the bounded rule extends influence out to a distance of `2 × radius` from the capsule centerline (since the falloff spans `d ∈ [-radius, +radius]` around the capsule surface).

---

## 6. Domain Sampling

### 6.1 Grid Evaluation (Normative)

For each axis:

```
coord = min + (max - min) * i / (n - 1)
```

Traversal order:

```
for z in 0..nz-1:
  for y in 0..ny-1:
    for x in 0..nx-1:
      sample(x,y,z)
```

All arithmetic MUST be float64.

---

### 6.2 Grid Size Limit (Normative)

To prevent non-deterministic failure modes:

```
nx * ny * nz ≤ 2_000_000
```

Violation → **ValidationError V74**

---

## 7. Surface Extraction — `marching_cubes@1`

### 7.1 Algorithm Identity

`marching_cubes@1` is a **frozen algorithm identifier**.

All of the following are normative and MUST NOT change:

* Lookup tables
* Edge interpolation formula
* Traversal order
* Winding conventions

Future extraction algorithms MUST use a new identifier (e.g., `marching_cubes@2`, `dual_contouring@1`).

---

### 7.2 Cell Traversal

```
for cz in 0..nz-2:
  for cy in 0..ny-2:
    for cx in 0..nx-2:
      process cell
```

---

### 7.3 Corner Ordering (Normative)

```
c0 = (cx,   cy,   cz)
c1 = (cx+1, cy,   cz)
c2 = (cx+1, cy+1, cz)
c3 = (cx,   cy+1, cz)
c4 = (cx,   cy,   cz+1)
c5 = (cx+1, cy,   cz+1)
c6 = (cx+1, cy+1, cz+1)
c7 = (cx,   cy+1, cz+1)
```

Bit `i` is set if `sample(ci) >= iso`.

---

### 7.4 Edge Interpolation (Normative)

For edge AB:

```
t = (iso - vA) / (vB - vA)
```

Rules:

* Computed entirely in float64
* If `vA == vB`, set `t = 0.5`
* Resulting vertex positions are serialized as float32

---

### 7.5 Winding and Orientation (Normative)

* Triangles MUST be emitted CCW
* Outside is defined as `F(x) < iso`
* Normals MUST point outward

---

### 7.6 Lookup Tables (Normative)

The canonical Marching Cubes `EdgeTable[256]` and `TriTable[256][16]` are **normative constants**.

The tables MUST match the Lorensen & Cline (1987) tables as published by Paul Bourke.

The normative `marching_cubes@1` tables are stored at:

```
spec/constants/marching_cubes@1_tables.bin
```

Encoding: `EdgeTable[256]` followed by `TriTable[256][16]`, all values as signed int32 little-endian.

SHA-256: `310452ffcd9e01a0824bb1bcd2dac54447dc4264595239f0a44419b20862754d`

---

### 7.7 Vertex Emission (Normative)

* Vertices are emitted per cell
* No vertex welding is performed
* Indices are sequential per triangle

**Note:**
Although vertices are not welded, normals are computed from the scalar field gradient. Duplicate vertices MAY therefore share identical normals, producing visually smooth shading.

Implementations MUST NOT derive normals from face geometry.

---

## 8. Normal Generation (Normative)

Implicit surfaces ALWAYS use smooth shading.

Normals are computed via central differences of the scalar field.

### 8.1 Finite Difference Step

The epsilon used for sampling is exactly one grid step along the corresponding axis.

---

### 8.2 Boundary Handling

If a sample lies outside the domain AABB:

* Clamp to the nearest valid grid coordinate
* One-sided differences MUST NOT be used

---

### 8.3 Zero Gradient Fallback

If gradient magnitude is zero:

```
normal = [0, 1, 0]
```

---

## 9. UV Behavior (Initial Scope)

Implicit surfaces initially do **not** generate UV coordinates.

* `TEXCOORD_0` is omitted
* Existing UV generators do not apply

This limitation is intentional.

---

## 10. Symmetry Interaction (Normative)

For `implicit_surface` primitives:

* Symmetry expansion operates on the **field operator list**
* Mirrored operators are merged into the same implicit surface
* Surface extraction occurs once, after expansion

This ensures implicit blending across symmetry planes.

---

### 10.1 Domain Expansion Rule (Normative)

After symmetry expansion merges mirrored operators into the same implicit surface, the compiler MUST expand the sampling domain AABB to enclose the full region influenced by the expanded operator set.

For a symmetry mirror about the YZ plane (X mirror):

Let original AABB be:

* `min = (x0, y0, z0)`
* `max = (x1, y1, z1)`

Define mirrored AABB:

* `min' = (-x1, y0, z0)`
* `max' = (-x0, y1, z1)`

Expanded AABB is the union:

* `min_exp = (min(x0, -x1), y0, z0)`
* `max_exp = (max(x1, -x0), y1, z1)`

The compiler MUST use the expanded AABB for grid sampling and extraction.

Grid resolution (`nx`, `ny`, `nz`) remains unchanged. The world-space grid step size MAY change as a result of domain expansion.

---

## 11. Skinning Interaction (Initial Scope)

Implicit surfaces produce baked geometry at compile time.

* They may be rigidly bound via existing mesh-level bindings
* Vertex-level weight inference is out of scope

---

## 12. Empty Surface Case

If no grid cell crosses the iso threshold:

* The primitive emits zero vertices and indices
* This is valid output

---

## 13. Validation Additions

| ID  | Condition                                              |
| --- | ------------------------------------------------------ |
| V67 | implicit_surface used with version predating this feature |
| V68 | Invalid AABB                                           |
| V69 | Invalid grid                                           |
| V70 | Empty ops                                              |
| V71 | Unknown field                                          |
| V72 | Invalid field parameters                               |
| V73 | Forbidden transform                                    |
| V74 | Grid exceeds max cell count                            |
| V75 | Unknown extraction algorithm                           |

---

## 14. Conformance Tests (Implicit Surfaces)

The conformance suite MUST include:

* **S01** — Single metaball sphere
* **S02** — Bean (two overlapping metaballs)
* **S03** — Capsule + sphere union
* **S04** — Rock with chip (subtract `sdf_sphere@1`)
* **S05** — Gouge scrape (subtract `sdf_capsule@1`)
* Negative tests for V67–V75

---

## Appendix A — Example Fixtures (Non-Normative)

The example fixtures for implicit surfaces live under:

```
spec/examples/implicit_surface/
```

* `E-SIG-01_bean.rigy.yaml`
* `E-SIG-02_rock_chip.rigy.yaml`
* `E-SIG-03_rock_gouge.rigy.yaml`
* `E-SIG-04_critter_base_form.rigy.yaml`

These fixtures use `iso: 0.0`; authors should adjust `iso` per the guidance in §4.3 for visible organic blending.

---

## 15. Future Extensions (Non-Normative)

### Follow-on

* Implicit UV projection (`implicit_projective@1`)
* Operator-driven skin weight inference
* Deterministic noise operators

### Later

* Deterministic vertex welding
* Adaptive sampling research

---

### Final note

This proposal establishes a **constrained, deterministic foundation** for organic modeling in Rigy without compromising the project's core principles.

It is intentionally narrow — and intentionally powerful.
