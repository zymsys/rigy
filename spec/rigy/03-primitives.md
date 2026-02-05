# 3. Primitives

## 3.0 Dimension Key Summary

| Primitive | Dimension Keys | Notes |
|-----------|---------------|-------|
| `box` | `x`, `y`, `z` | Also accepts `width`, `height`, `depth` aliases |
| `wedge` | `x`, `y`, `z` | Mathematical naming only |
| `sphere` | `radius` | — |
| `cylinder` | `radius`, `height` | — |
| `capsule` | `radius`, `height` | — |
| `implicit_surface` | `domain`, `ops`, `iso` | See Section 3.7 |

**Rationale**: Use `x/y/z` as the canonical axis-aligned vocabulary for boxes and wedges. `width/height/depth` remains accepted for box compatibility.

---

## 3.1 Tessellation Profile Reference

The `v0_1_default` tessellation profile, as defined in v0.1, remains the only supported profile. The conformance suite depends on the exact vertex and index counts produced by this profile.

| Primitive | Parameters | Vertices | Indices (triangles) |
|-----------|-----------|----------|-------------------|
| box       | — | 24 | 36 (12 tris) |
| sphere    | 16 lat x 32 lon | (16+1) x (32+1) = 561 | 16 x 32 x 6 = 3072 |
| cylinder  | 32 radial | side: 2x33 + caps: 2x(1+33) = 134 | 384 (128 tris) |
| capsule   | 8 hemisphere rings x 32 radial x 8 height | 9x33 + 9x33 + 8x33 = 858 | 4800 (1600 tris) |
| wedge     | — | 18 | 24 (8 tris) |

Implementations MUST produce identical vertex counts for identical input dimensions. In v0.1–v0.11, primitives are tessellated in YAML declaration order and merged into a single glTF primitive per mesh. In v0.12+, each Rigy primitive emits one glTF primitive (see [Section 13.2](13-gltf-export.md#132-bufferview-and-accessor-ordering)).

**Note:** The `implicit_surface` primitive (v0.13) produces a **variable** number of vertices and indices determined by the field definition, grid resolution, and iso threshold. The counts are not fixed by the tessellation profile, but they are fully deterministic: the same input MUST produce the same vertex and index counts.

### Canonical Vertex and Index Emission Order (Normative)

For binary-identical GLB output, implementations MUST emit not only the same vertex and index *counts*, but the same values in the same sequence.

Unless otherwise specified, front faces MUST use **counter-clockwise (CCW)** winding when viewed from outside the primitive in the right-handed coordinate system.

---

## 3.2 Box Primitive (Normative)

The box primitive MUST emit exactly 24 vertices and 36 indices.

**Face emission order** MUST be:

1. +X
2. -X
3. +Y
4. -Y
5. +Z
6. -Z

Each face MUST emit 4 unique vertices in CCW order as viewed from outside the box.

For each face-local vertex quartet `(v0, v1, v2, v3)` in CCW order, indices MUST be emitted as:

* `(v0, v1, v2)`
* `(v0, v2, v3)`

This matches the canonical two-triangle split of a quad.

---

## 3.3 Sphere Primitive (UV Sphere) (Normative)

Given the `v0_1_default` profile parameters `lat_steps = 16` and `lon_steps = 32`, the sphere primitive MUST emit:

* Vertices: `(lat_steps + 1) * (lon_steps + 1) = 561`
* Indices: `lat_steps * lon_steps * 6 = 3072`

Vertices MUST be emitted as a latitude/longitude grid including seam duplication:

* `i_lat` iterates from **north pole to south pole** (theta from `0` to `pi`)
* `i_lon` iterates CCW from the forward axis (-Z), including the seam duplicate at `i_lon = lon_steps`

**Vertex emission loop (normative):**

```
for i_lat in 0..lat_steps:
  for i_lon in 0..lon_steps:
    emit vertex(i_lat, i_lon)
```

**Index emission loop (normative):**

```
for i_lat in 0..lat_steps-1:
  for i_lon in 0..lon_steps-1:
    a = i_lat*(lon_steps+1) + i_lon
    b = a + (lon_steps+1)
    emit (a, b, a+1)
    emit (a+1, b, b+1)
```

---

## 3.4 Cylinder Primitive (Normative)

Given the `v0_1_default` profile parameter `n_radial = 32`, the cylinder primitive MUST emit:

* Vertices: `side: 2 x (n_radial+1) + caps: 2 x (1 + n_radial+1) = 134`
* Indices: `side: n_radial x 6 + caps: 2 x n_radial x 3 = 384`

The cylinder consists of three sections emitted in this order:

1. **Side** — 2 rings (top then bottom), each with `n_radial + 1` vertices (seam duplicate). Normals point radially outward (Y = 0).
2. **Top cap** — 1 center vertex (normal +Y) followed by `n_radial + 1` rim vertices (normal +Y).
3. **Bottom cap** — 1 center vertex (normal -Y) followed by `n_radial + 1` rim vertices (normal -Y).

**Side vertex emission loop (normative):**

```
for row in 0..1:           // 0 = top ring, 1 = bottom ring
  y = half_h if row == 0 else -half_h
  for seg in 0..n_radial:
    angle = 2pi * seg / n_radial
    emit vertex(radius * cos(angle), y, radius * sin(angle))
```

**Side index emission loop (normative):**

```
for seg in 0..n_radial-1:
  top = seg
  bottom = seg + n_radial + 1
  emit (top, bottom, top+1)
  emit (top+1, bottom, bottom+1)
```

**Cap emission (normative):** For each cap (top then bottom), emit center vertex, then `n_radial + 1` rim vertices. Cap triangle fan:

```
for seg in 0..n_radial-1:
  emit (cap_center, cap_start + seg, cap_start + seg + 1)
```

Bottom cap uses the same winding (center, seg, seg+1) with the -Y normal ensuring correct face orientation.

---

## 3.5 Capsule Primitive (Normative)

Given the `v0_1_default` profile parameters `n_radial = 32`, `n_height = 8`, `n_hemisphere_rings = 8`, the capsule primitive MUST emit:

* Vertices: `top_hemi: (n_hemisphere_rings+1) x (n_radial+1) + cylinder: (n_height+1) x (n_radial+1) + bottom_hemi: n_hemisphere_rings x (n_radial+1) = 9x33 + 9x33 + 8x33 = 858`
* Indices: `(total_rows - 1) x n_radial x 6 = 25 x 192 = 4800`

The capsule consists of three sections emitted in this order:

1. **Top hemisphere** — `n_hemisphere_rings + 1` rings (pole to equator), each with `n_radial + 1` vertices (seam duplicate).
2. **Cylinder section** — `n_height + 1` rows (top to bottom), each with `n_radial + 1` vertices. Normals point radially outward (Y = 0).
3. **Bottom hemisphere** — `n_hemisphere_rings` rings (starts at ring 1, equator to pole), each with `n_radial + 1` vertices.

The bottom hemisphere starts at ring 1 (not ring 0) because ring 0 would duplicate the last cylinder row.

**Top hemisphere vertex emission loop (normative):**

```
for ring in 0..n_hemisphere_rings:
  theta = (pi/2) * ring / n_hemisphere_rings    // 0 to pi/2
  y = half_h + radius * cos(theta)
  for seg in 0..n_radial:
    phi = 2pi * seg / n_radial
    emit vertex(radius * sin(theta) * cos(phi), y, radius * sin(theta) * sin(phi))
```

**Cylinder vertex emission loop (normative):**

```
for row in 0..n_height:
  y = half_h - height * row / n_height
  for seg in 0..n_radial:
    phi = 2pi * seg / n_radial
    emit vertex(radius * cos(phi), y, radius * sin(phi))
```

**Bottom hemisphere vertex emission loop (normative):**

```
for ring in 1..n_hemisphere_rings:
  theta = (pi/2) + (pi/2) * ring / n_hemisphere_rings    // pi/2 to pi
  y = -half_h + radius * cos(theta)
  for seg in 0..n_radial:
    phi = 2pi * seg / n_radial
    emit vertex(radius * sin(theta) * cos(phi), y, radius * sin(theta) * sin(phi))
```

**Index emission loop (normative):** All rows are stitched uniformly:

```
total_rows = (n_hemisphere_rings+1) + (n_height+1) + n_hemisphere_rings
for row in 0..total_rows-2:
  for seg in 0..n_radial-1:
    current = row * (n_radial+1) + seg
    next_row = current + n_radial + 1
    emit (current, next_row, current+1)
    emit (current+1, next_row, next_row+1)
```

---

## 3.6 Wedge Primitive (Normative)

*Introduced in v0.9.*

### Description

The `wedge` primitive is a right triangular prism formed by extruding a right triangle in the **XZ** plane along the **Y** axis.

It is defined by three positive dimensions:

- `x` (width, full extent in X)
- `y` (depth, full extent in Y)
- `z` (height, full extent in Z)

All dimensions **MUST** be strictly positive. Dimensions are full extents (not half-extents), consistent with `box`.

The wedge is centered on the origin in all three axes:

- X spans `[-x/2, +x/2]`
- Y spans `[-y/2, +y/2]`
- Z spans `[-z/2, +z/2]`

### Version Gate

A YAML document that uses `type: "wedge"`:

- **MUST** declare `version: "0.9"` (or later).
- A parser conforming to v0.9+ **MUST** reject `type: "wedge"` in documents declaring an earlier version.

Identifiers like `wedge@1` refer to the **spec-defined version** of the primitive. The `@1` suffix is **spec-level notation only**; YAML uses `type: "wedge"`.

### Canonical Conceptual Vertices

Let `hx = x/2`, `hy = y/2`, `hz = z/2`. Define six conceptual vertices:

- `v0 = (-hx, -hy, -hz)`  (A0)
- `v1 = (+hx, -hy, -hz)`  (B0)
- `v2 = (-hx, -hy, +hz)`  (C0)
- `v3 = (-hx, +hy, -hz)`  (A1)
- `v4 = (+hx, +hy, -hz)`  (B1)
- `v5 = (-hx, +hy, +hz)`  (C1)

These are **conceptual** vertices for geometry definition. The emitted vertex buffer duplicates vertices as needed to ensure flat normals and per-surface exclusivity.

At any fixed Y, the cross-section is the right triangle `(A, B, C)` where the right angle is at `A` and the legs run along +X and +Z.

### Visual Reference

**Default orientation (top-down view, Y-up):**

```
            +Z
             ^
             |
    C -------+------- B   (+hz)
     \       |       /
      \      |      /
       \     |     /
        \    |    /
         \   |   /
          \  |  /
           \ | /
    --------A----------> +X
          (-hx)
```

- `A` = right-angle vertex at `(-hx, y, -hz)`
- `B` = vertex at `(+hx, y, -hz)`
- `C` = vertex at `(-hx, y, +hz)`
- Legs extend along +X (A→B) and +Z (A→C)
- Shape extrudes along Y axis from `-hy` to `+hy`
- Triangular faces at `-y` and `+y`; slope face connects B-C edges

### Common Rotation Recipes

Use `rotation_degrees` for authoring these common orientations.
`rotation_euler` (radians) remains available for compatibility.

> **Note (Normative):** Wedge recipe descriptions refer to the wedge's **local frame after rotation but before translation**. They do not describe world-space directions. In v0.12+, authors may also use `rotation_axis_angle` or `rotation_quat` (see [Section 10.9](10-preprocessing.md#109-rotation-authoring-and-canonical-form-v012)) to avoid Euler composition entirely.

| Use Case | rotation_degrees | Notes |
|----------|------------------|-------|
| Default (slope toward +Z) | `[0, 0, 0]` | Hypotenuse faces +Z |
| Slope toward -Z | `[0, 180, 0]` | 180° about Y |
| Slope toward +X | `[0, -90, 0]` | -90° about Y |
| Slope toward -X | `[0, 90, 0]` | 90° about Y |
| Gable fill (triangular face toward +Z) | `[-90, 0, 0]` | -90° about X |
| Gable fill (triangular face toward -Z) | `[90, 0, 0]` | 90° about X |
| Gable left half (local right angle at +X; front -Z) | `[-90, 180, 0]` | Right angle at center, slope toward -X |
| Gable right half (local right angle at -X; front -Z) | `[-90, 0, 0]` | Right angle at center, slope toward +X |

**Gable example** (symmetric front gable from two wedges):

A symmetric gable requires two wedges mirrored about the ridge axis. Each wedge's `x` dimension is half the wall width, `z` is the gable rise, and `y` is the wall thickness. The right angle sits at the ridge (center) and the hypotenuse slopes down to the eave.

```yaml
# Left half — right angle at ridge, hypotenuse slopes down to left eave
- type: wedge
  id: gable_left
  dimensions: { x: 4.0, y: 0.2, z: 1.5 }
  transform:
    rotation_degrees: [-90, 180, 0]  # -90° about X, 180° about Y
    translation: [-2.0, 3.45, 2.9]

# Right half — right angle at ridge, hypotenuse slopes down to right eave
- type: wedge
  id: gable_right
  dimensions: { x: 4.0, y: 0.2, z: 1.5 }
  transform:
    rotation_degrees: [-90, 0, 0]    # -90° about X only
    translation: [2.0, 3.45, 2.9]
```

**Worked example: "Right half" world-space vertices**

Given `gable_right` above with `dimensions: { x: 4.0, y: 0.2, z: 1.5 }`, `rotation_degrees: [-90, 0, 0]`, `translation: [2.0, 3.45, 2.9]`:

* `hx=2.0, hy=0.1, hz=0.75`
* `Rx(-90°)` maps `(x,y,z) → (x, z, -y)`

Pre-transform conceptual vertices and their world-space positions after rotation then translation:

| Vertex | Pre-transform | After Rx(-90°) | + translation | World (x, y, z) |
|--------|---------------|----------------|---------------|-----------------|
| v0 (A0) | (-2.0, -0.1, -0.75) | (-2.0, -0.75, 0.1) | | (0.0, 2.7, 3.0) |
| v1 (B0) | (+2.0, -0.1, -0.75) | (+2.0, -0.75, 0.1) | | (4.0, 2.7, 3.0) |
| v2 (C0) | (-2.0, -0.1, +0.75) | (-2.0, +0.75, 0.1) | | (0.0, 4.2, 3.0) |
| v3 (A1) | (-2.0, +0.1, -0.75) | (-2.0, -0.75, -0.1) | | (0.0, 2.7, 2.8) |
| v4 (B1) | (+2.0, +0.1, -0.75) | (+2.0, -0.75, -0.1) | | (4.0, 2.7, 2.8) |
| v5 (C1) | (-2.0, +0.1, +0.75) | (-2.0, +0.75, -0.1) | | (0.0, 4.2, 2.8) |

The triangular cross-section (A, B, C) now lies in the XY plane: the right-angle corner (A vertices at world X=0) sits at the ridge center, B vertices extend to the right eave (X=4), and C vertices mark the apex (Y=4.2). The slab thickness spans Z=[2.8, 3.0], with the `-y` triangular face (Z=3.0) facing the +Z direction.

### Degree-to-Radian Reference

| Degrees | Radians | Value |
|---------|---------|-------|
| 0° | 0 | `0` |
| 30° | π/6 | `0.5236` |
| 45° | π/4 | `0.7854` |
| 90° | π/2 | `1.5708` |
| 180° | π | `3.1416` |
| 270° | 3π/2 | `4.7124` |
| -90° | -π/2 | `-1.5708` |

### Canonical Triangle Topology (Conceptual)

Triangle winding **MUST** be counter-clockwise (CCW) when viewed from outside the mesh (right-handed coordinate system).

Using the conceptual vertices `v0..v5`, the wedge's conceptual triangle topology is:

- `-y`: `(v0, v1, v2)`
- `+y`: `(v3, v5, v4)`
- `-z`: `(v0, v4, v1)` and `(v0, v3, v4)`
- `-x`: `(v0, v2, v5)` and `(v0, v5, v3)`
- `slope`: `(v1, v5, v2)` and `(v1, v4, v5)`

This topology fixes geometry and face membership.

### Vertex and Index Emission (Normative)

To ensure byte-identical output, the `wedge` primitive **MUST** emit vertices and indices in the deterministic order below.

**Vertex count and index count (normative):**
- Emitted vertices: **18**
- Emitted triangles: **8**
- Emitted indices: **24** (8 x 3), `uint32`

**Flat normals and duplication rule (normative):**
- `wedge` **MUST** be flat-shaded.
- Vertices **MUST NOT** be shared across faces that have different normals.
- Vertices **MAY** be shared within a single face (surface), since all triangles on that face share the same normal.

**Emission order (normative):** emit faces in this order:

1. `-z` (rect)
2. `-x` (rect)
3. `slope` (rect)
4. `-y` (tri)
5. `+y` (tri)

For each face, emit the face's **local vertex list** (positions + normals) followed by its indices, using a running base offset.

**Per-face local vertex lists and indices (normative):**

Let `emit_face(vertices, indices)` mean:
- append the face's vertices to the global vertex buffer
- append the face's indices to the global index buffer, with each index offset by the current global base vertex index
- then advance the base vertex index by `len(vertices)`

All positions below reference the conceptual vertex coordinates. Normals are the face normal.

- Face `-z`:
  - local vertices (4): `[v0, v1, v4, v3]`
  - local indices (6): `(0, 2, 1)`, `(0, 3, 2)`

- Face `-x`:
  - local vertices (4): `[v0, v3, v5, v2]`
  - local indices (6): `(0, 2, 3)`, `(0, 1, 2)`

- Face `slope`:
  - local vertices (4): `[v1, v2, v5, v4]`
  - local indices (6): `(0, 2, 1)`, `(0, 3, 2)`

- Face `-y`:
  - local vertices (3): `[v0, v1, v2]`
  - local indices (3): `(0, 1, 2)`

- Face `+y`:
  - local vertices (3): `[v3, v5, v4]`
  - local indices (3): `(0, 1, 2)`

This emission profile is the canonical wedge tessellation for v0.9+.

### Normals (Normative)

`box` and `wedge` **MUST** generate flat normals:

- For each emitted face, the normal for all vertices of that face is the unit-length face normal derived from its CCW winding.
- Implementations **MUST NOT** average normals across faces.

This pins down wedge slope normals deterministically: they are the face normal computed from the `slope` face triangles and the provided dimensions.

### UV Generators and `wedge`

If the mesh declares UV sets (v0.8+ `uv_sets`), then `wedge` participates under the existing rules:

- Any UV generator declared on a mesh **MUST** be applicable to every primitive type present in that mesh (existing rule).
- Generators applicable to `all` primitives (e.g., `planar_xy@1`) apply to `wedge` without special casing.
- Generators applicable only to specific primitives (e.g., `box_project@1`) are invalid in meshes that contain `wedge`.

No wedge-specific UV generator is defined in v0.9, v0.10, v0.11, or v0.12.

---

## 3.7 Implicit Surface Primitive (Normative)

*Introduced in v0.13.*

### Version Gate

Use of `type: implicit_surface`:

* REQUIRES `version: "0.13"` or later
* MUST raise **ValidationError V79** otherwise

### Schema

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

### Required Fields

* `domain.aabb.min`, `domain.aabb.max`
  * Exactly three finite float64 values each
  * `max[i] > min[i]` for all axes (V80)
* `domain.grid.nx|ny|nz`
  * Integers ≥ 2 (V81)
* `iso`
  * Finite float64
* `ops`
  * Non-empty list (V82)
* `field` identifiers MUST be from the field vocabulary defined in this section (V83)

### Optional Fields

* `material`
* `tags`
* `extraction`
  * If omitted, `marching_cubes@1` is assumed

Material and tag behavior is unchanged from existing primitives.

### Field Operator Transform Constraints (Normative)

Field operators reuse the standard Rigy `Transform` object, but with the following constraints:

**Allowed**

* `translation`
* `rotation_degrees` (or `rotation_euler`, consistent with the existing Transform mutual exclusivity rules)
* In v0.12+, `rotation_axis_angle` and `rotation_quat` are also allowed
* `scale` **only if uniform** (`sx == sy == sz`)

**Forbidden (ValidationError V85)**

* Non-uniform scale (`sx`, `sy`, `sz` not all equal)
* Any shear transform (if representable)
* Any transform fields not present in the standard Transform model

**Notes**

* If rotation is present, it MUST follow the same mutual exclusivity rules as existing Transform usage (providing both `rotation_degrees` and `rotation_euler` is a ParseError).
* Uniform scale is applied in operator-local space before translation.

### Field Evaluation Model

#### Field Combination (Normative)

Each operator defines a **bounded scalar contribution** `Ci(x)`.

The total scalar field is:

```
F(x) = Σ Ci(x)
```

The implicit surface is defined by:

```
F(x) = iso
```

#### Operator Polarity (Normative)

The `op` field applies a sign:

* `op: add` → contribution as defined
* `op: subtract` → contribution multiplied by `-1`

This rule applies uniformly to all field types.

#### Practical `iso` Guidance (Non-Normative)

For `metaball_*@1` fields, `iso = 0.0` places the surface at the field's zero boundary and produces little visible blending between adjacent blobs. For organic merging, authors typically use `iso` in the range **0.1–0.5 relative to the dominant `strength`**, depending on overlap distance and desired surface thickness.

Higher `iso` values shrink the surface inward and increase the blending region between overlapping operators. Lower values expand the surface outward and reduce blending.

### Field Vocabulary

All field functions defined in this section are:

* Bounded
* Compactly supported
* Monotonic with distance
* Evaluated in float64

#### `metaball_sphere@1`

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

#### `metaball_capsule@1`

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

#### `sdf_sphere@1` (Bounded, Monotonic)

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

#### `sdf_capsule@1`

**Geometry**

Same capsule segment definition as `metaball_capsule@1`.

Let:

```
d = ||p - q|| - radius
```

**Contribution**

Identical bounded, monotonic rule as `sdf_sphere@1`.

**Note:** For `sdf_capsule@1`, the bounded rule extends influence out to a distance of `2 × radius` from the capsule centerline (since the falloff spans `d ∈ [-radius, +radius]` around the capsule surface).

### Field Parameter Validation (V84)

All field parameters MUST be strictly positive:

* `radius > 0`
* `strength > 0`
* `height > 0` (for capsule fields)

Non-positive values MUST raise **ValidationError V84**.

### Domain Sampling

#### Grid Evaluation (Normative)

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

#### Grid Size Limit (Normative)

To prevent non-deterministic failure modes:

```
nx * ny * nz ≤ 2_000_000
```

Violation → **ValidationError V86**

### Surface Extraction — `marching_cubes@1`

#### Algorithm Identity

`marching_cubes@1` is a **frozen algorithm identifier**.

All of the following are normative and MUST NOT change:

* Lookup tables
* Edge interpolation formula
* Traversal order
* Winding conventions

Future extraction algorithms MUST use a new identifier (e.g., `marching_cubes@2`, `dual_contouring@1`).

Unknown extraction algorithm identifiers MUST raise **ValidationError V87**.

#### Cell Traversal

```
for cz in 0..nz-2:
  for cy in 0..ny-2:
    for cx in 0..nx-2:
      process cell
```

#### Corner Ordering (Normative)

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

#### Edge Interpolation (Normative)

For edge AB:

```
t = (iso - vA) / (vB - vA)
```

Rules:

* Computed entirely in float64
* If `vA == vB`, set `t = 0.5`
* Resulting vertex positions are serialized as float32

#### Winding and Orientation (Normative)

* Triangles MUST be emitted CCW
* Outside is defined as `F(x) < iso`
* Normals MUST point outward

#### Lookup Tables (Normative)

The canonical Marching Cubes `EdgeTable[256]` and `TriTable[256][16]` are **normative constants**.

The tables MUST match the Lorensen & Cline (1987) tables as published by Paul Bourke.

The normative `marching_cubes@1` tables are stored at:

```
spec/constants/marching_cubes@1_tables.bin
```

Encoding: `EdgeTable[256]` followed by `TriTable[256][16]`, all values as signed int32 little-endian.

SHA-256: `310452ffcd9e01a0824bb1bcd2dac54447dc4264595239f0a44419b20862754d`

#### Vertex Emission (Normative)

* Vertices are emitted per cell
* No vertex welding is performed
* Indices are sequential per triangle

**Note:**
Although vertices are not welded, normals are computed from the scalar field gradient. Duplicate vertices MAY therefore share identical normals, producing visually smooth shading.

Implementations MUST NOT derive normals from face geometry.

### Normal Generation (Normative)

Implicit surfaces ALWAYS use smooth shading.

Normals are computed via central differences of the scalar field.

#### Finite Difference Step

The epsilon used for sampling is exactly one grid step along the corresponding axis.

#### Boundary Handling

If a sample lies outside the domain AABB:

* Clamp to the nearest valid grid coordinate
* One-sided differences MUST NOT be used

#### Zero Gradient Fallback

If gradient magnitude is zero:

```
normal = [0, 1, 0]
```

### UV Behavior

Implicit surfaces do **not** generate UV coordinates.

* `TEXCOORD_0` is omitted
* Existing UV generators do not apply

This limitation is intentional. See [Section 9.2](09-uv-system.md) for UV exclusion rules.

### Skinning Interaction

Implicit surfaces produce baked geometry at compile time.

* They may be rigidly bound via existing mesh-level bindings
* Vertex-level weight inference is out of scope

### Empty Surface Case

If no grid cell crosses the iso threshold:

* The primitive emits zero vertices and indices
* This is valid output

---

**End of Chapter 3**
