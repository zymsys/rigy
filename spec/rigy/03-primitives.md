# 3. Primitives

## 3.0 Dimension Key Summary

| Primitive | Dimension Keys | Notes |
|-----------|---------------|-------|
| `box` | `x`, `y`, `z` | Also accepts `width`, `height`, `depth` aliases |
| `wedge` | `x`, `y`, `z` | Mathematical naming only |
| `sphere` | `radius` | — |
| `cylinder` | `radius`, `height` | — |
| `capsule` | `radius`, `height` | — |

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

**End of Chapter 3**
