# Rigy Specification — v0.6-draft

**Status:** Draft
**Theme:** Determinism, Deformation, and Materials
**Scope:** Cumulative specification covering all features from v0.1 through v0.6

The key words MUST, MUST NOT, SHOULD, SHALL, and MAY in this document are to be
interpreted as described in [RFC 2119](https://www.ietf.org/rfc/rfc2119.txt).

---

## 1. Goals of v0.6

Rigy v0.6 is a **cumulative specification** encompassing all features introduced from
v0.1 through v0.6.

### 1.1 Relationship to Prior Versions

Rigy v0.6 is a **strict superset** of all prior versions. All features are retained:

* **v0.1** — Geometric primitives, armatures, per-primitive skinning, symmetry
* **v0.2** — Anchors, imports, instances, attach3, contracts (Ricy)
* **v0.3** — Per-vertex weight maps (gradients, overrides, external JSON sources)
* **v0.4** — Normative conformance suite, exhaustive validation table, determinism formalization, float64 intermediate precision, NaN/Infinity rejection
* **v0.5** — Dual Quaternion Skinning (DQS), per-binding solver selection, pose evaluation blocks, baked GLB export
* **v0.6** — Solid-color materials, deterministic material export

### 1.2 Roadmap Note

Future work may include corrective shapes, pose-space deformation, constraints, and
control rigs. These are not part of v0.6.

---

## 2. Non-Goals

Rigy v0.6 explicitly does **not**:

* Add blendshapes, corrective shapes, or pose-space deformation
* Introduce IK systems, constraints, or control rigs
* Add animation graphs or timelines
* Introduce freeform transforms or scripting
* Change the tessellation profile or vertex counts for any primitive type
* Add textures, UV coordinates, shading models, or lighting semantics
* Guarantee backward compatibility with incorrect outputs

---

## 3. Migration

### 3.1 Parser Compatibility

A v0.6 conforming parser:

* MUST accept `version` values `"0.1"` through `"0.6"`
* MUST reject `version` with major version ≥ 1
* SHOULD emit a warning for minor versions > 6 within major version 0

### 3.2 From v0.5

All v0.5 files are valid v0.6 files. v0.6 adds:

* Optional `materials` table (Section 12)
* Optional per-primitive `material` references
* Validation rules V37–V42

### 3.3 From v0.4

v0.5 added:

* `skinning_solver` promoted from reserved to active (Section 13)
* `poses` block for conformance testing (Section 15)
* Validation rules V35–V36

### 3.4 From v0.3

v0.4 added:

* Non-finite numeric values (NaN, ±Infinity) are a hard error (V32)
* All previously undefined behaviors are resolved (Section 7.4)

---

## 4. Determinism Contract

Rigy maintains the following core contract:

> **For a given Rigy input and a given Rigy specification version, a conforming
> implementation MUST produce byte-identical output artifacts.**

### 4.1 Superseding v0.1's Relaxation

v0.1 described determinism as "structural, not bit-identical floating-point." v0.3
strengthened this to byte-identical GLB. v0.4 **superseded** v0.1's relaxation.
Byte-identical GLB output is the normative requirement for all conforming
implementations, retroactive to v0.3.

### 4.2 Intermediate Arithmetic Precision

Conforming implementations MUST perform intermediate arithmetic in at least IEEE 754
binary64 (float64) precision. Truncation to binary32 (float32) MUST occur only at the
serialization boundary (when writing to the GLB binary buffer).

This ensures that two conforming implementations produce identical bytes, regardless
of which programming language or library they use.

### 4.3 DQS Determinism

To ensure conformance for Dual Quaternion Skinning:

* All intermediate calculations MUST use float64 precision.
* Quaternion sign selection MUST follow the hemisphere rule (Section 14.2).
* Final vertex outputs MUST be converted to float32 using IEEE 754 round-to-nearest-even (the default rounding mode). Implementations MUST NOT use truncation or other rounding modes for this conversion.
* Algebraic reorderings that change IEEE results are prohibited in the reference evaluator.

### 4.4 Material Determinism

Materials in v0.6:

* MUST NOT affect vertex counts, ordering, or skinning
* MUST NOT affect canonicalization rules
* MUST NOT affect numeric evaluation pipelines

Material data is declarative and does not participate in floating-point computation.

### 4.5 Scope of Determinism

* Determinism applies **only to correct behavior as defined by the spec**
* Outputs produced by incorrect behavior are **not protected**

---

## 5. Coordinate System and Units

```yaml
units: meters
coordinate_system:
  up: Y
  forward: -Z
  handedness: right
```

---

## 6. Tessellation Profile Reference

The `v0_1_default` tessellation profile, as defined in v0.1, remains the only
supported profile. The conformance suite depends on the exact vertex and index counts
produced by this profile.

| Primitive | Parameters | Vertices | Indices (triangles) |
|-----------|-----------|----------|-------------------|
| box       | — | 24 | 36 (12 tris) |
| sphere    | 16 lat × 32 lon | (16+1) × (32+1) = 561 | 16 × 32 × 6 = 3072 |
| cylinder  | 32 radial | side: 2×33 + caps: 2×(1+33) = 134 | 384 (128 tris) |
| capsule   | 8 hemisphere rings × 32 radial × 8 height | 9×33 + 9×33 + 8×33 = 858 | 4800 (1600 tris) |

Implementations MUST produce identical vertex counts for identical input dimensions.
Primitives are tessellated in YAML declaration order and merged into a single glTF
primitive per mesh.

### 6.1 Canonical Vertex and Index Emission Order (Normative)

For binary-identical GLB output, implementations MUST emit not only the same vertex
and index *counts*, but the same values in the same sequence.

Unless otherwise specified, front faces MUST use **counter-clockwise (CCW)** winding
when viewed from outside the primitive in the right-handed coordinate system.

### 6.2 Box Primitive (Normative)

The box primitive MUST emit exactly 24 vertices and 36 indices.

**Face emission order** MUST be:

1. +X
2. -X
3. +Y
4. -Y
5. +Z
6. -Z

Each face MUST emit 4 unique vertices in CCW order as viewed from outside the box.

For each face-local vertex quartet `(v0, v1, v2, v3)` in CCW order, indices MUST be
emitted as:

* `(v0, v1, v2)`
* `(v0, v2, v3)`

This matches the canonical two-triangle split of a quad.

### 6.3 Sphere Primitive (UV Sphere) (Normative)

Given the `v0_1_default` profile parameters `lat_steps = 16` and `lon_steps = 32`,
the sphere primitive MUST emit:

* Vertices: `(lat_steps + 1) * (lon_steps + 1) = 561`
* Indices: `lat_steps * lon_steps * 6 = 3072`

Vertices MUST be emitted as a latitude/longitude grid including seam duplication:

* `i_lat` iterates from **north pole to south pole** (theta from `0` to `pi`)
* `i_lon` iterates CCW from the forward axis (-Z), including the seam duplicate at
  `i_lon = lon_steps`

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

### 6.4 Cylinder Primitive (Normative)

Given the `v0_1_default` profile parameter `n_radial = 32`, the cylinder primitive
MUST emit:

* Vertices: `side: 2 × (n_radial+1) + caps: 2 × (1 + n_radial+1) = 134`
* Indices: `side: n_radial × 6 + caps: 2 × n_radial × 3 = 384`

The cylinder consists of three sections emitted in this order:

1. **Side** — 2 rings (top then bottom), each with `n_radial + 1` vertices (seam
   duplicate). Normals point radially outward (Y = 0).
2. **Top cap** — 1 center vertex (normal +Y) followed by `n_radial + 1` rim vertices
   (normal +Y).
3. **Bottom cap** — 1 center vertex (normal -Y) followed by `n_radial + 1` rim vertices
   (normal -Y).

**Side vertex emission loop (normative):**

```
for row in 0..1:           // 0 = top ring, 1 = bottom ring
  y = half_h if row == 0 else -half_h
  for seg in 0..n_radial:
    angle = 2π * seg / n_radial
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

**Cap emission (normative):** For each cap (top then bottom), emit center vertex,
then `n_radial + 1` rim vertices. Cap triangle fan:

```
for seg in 0..n_radial-1:
  emit (cap_center, cap_start + seg, cap_start + seg + 1)
```

Bottom cap uses the same winding (center, seg, seg+1) with the -Y normal ensuring
correct face orientation.

### 6.5 Capsule Primitive (Normative)

Given the `v0_1_default` profile parameters `n_radial = 32`, `n_height = 8`,
`n_hemisphere_rings = 8`, the capsule primitive MUST emit:

* Vertices: `top_hemi: (n_hemisphere_rings+1) × (n_radial+1) + cylinder: (n_height+1) × (n_radial+1) + bottom_hemi: n_hemisphere_rings × (n_radial+1) = 9×33 + 9×33 + 8×33 = 858`
* Indices: `(total_rows - 1) × n_radial × 6 = 25 × 192 = 4800`

The capsule consists of three sections emitted in this order:

1. **Top hemisphere** — `n_hemisphere_rings + 1` rings (pole to equator), each with
   `n_radial + 1` vertices (seam duplicate).
2. **Cylinder section** — `n_height + 1` rows (top to bottom), each with `n_radial + 1`
   vertices. Normals point radially outward (Y = 0).
3. **Bottom hemisphere** — `n_hemisphere_rings` rings (starts at ring 1, equator to pole),
   each with `n_radial + 1` vertices.

The bottom hemisphere starts at ring 1 (not ring 0) because ring 0 would duplicate
the last cylinder row.

**Top hemisphere vertex emission loop (normative):**

```
for ring in 0..n_hemisphere_rings:
  theta = (π/2) * ring / n_hemisphere_rings    // 0 to π/2
  y = half_h + radius * cos(theta)
  for seg in 0..n_radial:
    phi = 2π * seg / n_radial
    emit vertex(radius * sin(theta) * cos(phi), y, radius * sin(theta) * sin(phi))
```

**Cylinder vertex emission loop (normative):**

```
for row in 0..n_height:
  y = half_h - height * row / n_height
  for seg in 0..n_radial:
    phi = 2π * seg / n_radial
    emit vertex(radius * cos(phi), y, radius * sin(phi))
```

**Bottom hemisphere vertex emission loop (normative):**

```
for ring in 1..n_hemisphere_rings:
  theta = (π/2) + (π/2) * ring / n_hemisphere_rings    // π/2 to π
  y = -half_h + radius * cos(theta)
  for seg in 0..n_radial:
    phi = 2π * seg / n_radial
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

## 7. Validation and Error Model (Normative)

### 7.1 Error Type Hierarchy

Rigy defines six normative error types. Conformance tests validate error **category**,
not exact message text.

```
RigyError (base)
├── ParseError          — YAML parsing or schema deserialization
├── ValidationError     — Semantic rule violations
├── TessellationError   — Geometry generation failures
├── ExportError         — glTF/GLB assembly failures
├── ContractError       — Ricy contract violations
└── CompositionError    — Import, instance, or attach3 failures
```

### 7.2 Hard Errors (MUST reject)

A conforming implementation MUST fail and MUST NOT emit output for any of the
following conditions.

| ID | Check | Error Type | Since |
|----|-------|-----------|-------|
| V01 | Duplicate mesh IDs | ValidationError | v0.1 |
| V02 | Duplicate primitive IDs within a mesh | ValidationError | v0.1 |
| V03 | Duplicate armature IDs | ValidationError | v0.1 |
| V04 | Duplicate bone IDs within an armature | ValidationError | v0.1 |
| V05 | Cyclic bone hierarchy | ValidationError | v0.1 |
| V06 | Zero-length bone (head ≈ tail within ε = 1e-9) | ValidationError | v0.1 |
| V07 | Non-positive primitive dimension | ValidationError | v0.1 |
| V08 | Binding references unknown mesh | ValidationError | v0.1 |
| V09 | Binding references unknown armature | ValidationError | v0.1 |
| V10 | Binding references unknown primitive | ValidationError | v0.1 |
| V11 | Binding references unknown bone | ValidationError | v0.1 |
| V12 | Mesh appears in multiple bindings | ValidationError | v0.1 |
| V13 | Per-primitive weight value outside [0.0, 1.0] | ValidationError | v0.1 |
| V14 | Weight map references unknown primitive | ValidationError | v0.3 |
| V15 | Gradient `bone_id` references unknown bone | ValidationError | v0.3 |
| V16 | Override `bone_id` references unknown bone | ValidationError | v0.3 |
| V17 | Gradient weight value outside [0.0, 1.0] | ValidationError | v0.3 |
| V18 | Override weight value outside [0.0, 1.0] | ValidationError | v0.3 |
| V19 | Override vertex index out of bounds for its primitive | ValidationError | v0.3 |
| V20 | External weight file not found or malformed JSON | ValidationError | v0.3 |
| V21 | External weight file `vertex_count` mismatch | ValidationError | v0.3 |
| V22 | External weight file `primitive_id` mismatch | ValidationError | v0.3 |
| V23 | Weight map has none of `gradients`, `overrides`, or `source` | ValidationError | v0.3 |
| V24 | Duplicate anchor IDs | ValidationError | v0.2 |
| V25 | Duplicate instance IDs | ValidationError | v0.2 |
| V26 | Instance references unknown import | ValidationError | v0.2 |
| V27 | Instance references unknown mesh (local instance) | ValidationError | v0.2 |
| V28 | ID collision across mesh/armature/anchor/instance namespaces | ValidationError | v0.2 |
| V29 | attach3 `from` anchor not found in imported asset | ValidationError | v0.2 |
| V30 | attach3 `to` anchor not found in local anchors | ValidationError | v0.2 |
| V31 | Contract violation on imported asset | ContractError | v0.2 |
| V32 | NaN or ±Infinity in any numeric field | ValidationError | v0.4 |
| V33 | Unknown fields in strict-mode schema | ParseError | v0.1 |
| V34 | Missing required fields in schema | ParseError | v0.1 |
| V35 | Non-rigid bone transform in DQS binding (scale, shear, or uniform scale present) | ValidationError | v0.5 |
| V36 | Invalid pose quaternion (non-unit norm, NaN, or Infinity component) | ValidationError | v0.5 |
| V37 | Duplicate material IDs | ValidationError | v0.6 |
| V38 | Primitive references unknown material ID | ValidationError | v0.6 |
| V39 | `base_color` length ≠ 4 | ValidationError | v0.6 |
| V40 | Any `base_color` component outside `[0.0, 1.0]` | ValidationError | v0.6 |
| V41 | Primitives in the same mesh do not share the exact same material reference (or lack thereof) | ValidationError | v0.6 |
| V42 | Material ID collision or unresolved reference during import resolution | ValidationError | v0.6 |

#### Parse vs Validation Notes (V37–V42)

- Missing `base_color` or wrong type is a **ParseError** (schema enforcement, consistent with V33/V34)
- Length and range checks occur **post-parse** and are ValidationErrors as defined above

### 7.3 Soft Errors / Warnings (MUST warn, MAY continue)

Warnings MUST NOT affect output determinism. The output MUST be identical whether or
not the warning is emitted.

| ID | Condition | Since |
|----|-----------|-------|
| W01 | Vertex has more than 4 joint influences (before capping) | v0.3 |
| W02 | Per-primitive weights and weight map both target the same primitive | v0.3 |
| W03 | Armature root bone head not at origin (convention) | v0.2 |

### 7.4 Previously Undefined Behavior (Now Resolved)

Rigy v0.4 removed all previously implicit undefined behavior. Any input condition not
explicitly defined in this spec or prior specs is a **hard error**.

The following behaviors were previously underspecified and are now normatively defined:

| Condition | Resolution |
|-----------|-----------|
| All vertex weights are zero after influence resolution | Fall back to armature root bone, weight 1.0 |
| No bone in armature has `parent: none` | Use the first bone (index 0) as the root (note: in a finite bone set this implies a cycle, so V05 will typically reject first; this rule is a defensive fallback for root-detection logic) |
| Gradient `from` and `to` both yield zero weight for all bones at a vertex | Fall back to armature root bone, weight 1.0 |

---

## 8. Influence Resolution Order (Normative, from v0.3)

For a given vertex, influences are resolved in the following priority (last wins):

1. **Default binding** — rigidly bound to the armature root bone (weight 1.0)
2. **Per-primitive weights** — from `bindings[].weights[].bones`
3. **External weight file** — from `weight_maps[].source`
4. **Gradients** — from `weight_maps[].gradients`, in declaration order
5. **Overrides** — from `weight_maps[].overrides`, in declaration order

At each stage, the new influences **fully replace** the previous ones for the affected
vertices. There is no additive blending between stages.

---

## 9. Canonicalization Rules (Normative)

These rules apply **before** output generation and are **normative**.

### 9.1 Vertex Ordering

Vertices MUST follow the canonical tessellation order defined by the `v0_1_default`
profile. Primitives are tessellated in YAML declaration order and merged sequentially
into a single vertex buffer per mesh.

### 9.2 Influence Sorting

For each vertex, the influence list MUST be sorted using a three-part key:

1. **Primary:** weight, descending (largest first)
2. **Secondary:** `bone_id` string, ascending (lexicographic)
3. **Tertiary:** bone index (position in armature's bones list), ascending

The tertiary key is a defensive tiebreaker. Since bone IDs are unique within an
armature (V04), the tertiary key is never reached in valid input, but MUST be
applied for implementation correctness.

**String ordering rule (normative):**

When comparing `bone_id` strings for sorting (secondary key), implementations MUST:

* Treat `bone_id` as UTF-8 encoded text
* Compare strings by **bytewise lexicographic ordering of UTF-8 encoded bytes**
* MUST NOT apply locale-specific collation, Unicode normalization, or case folding

Invalid UTF-8 `bone_id` values are a hard error (ValidationError).

### 9.3 Influence Capping and Normalization

After sorting:

1. Retain only the first 4 influences (discard the rest)
2. Compute `total_w = sum of retained weights`
3. If `total_w > 0`: divide each retained weight by `total_w`
4. If `total_w == 0`: replace the entire influence list with `[(root_bone_index, 1.0)]`

### 9.4 Influence Padding

After capping and normalization, if fewer than 4 influences remain, pad with
`(joint_index=0, weight=0.0)` until exactly 4 slots are filled. The result is
always a 4-element JOINTS_0 and 4-element WEIGHTS_0 per vertex.

### 9.5 Gradient Interpolation Formula

Gradient evaluation for a vertex at position `p` along axis `a` with range `[r0, r1]`:

```
t = clamp((p[a] - r0) / (r1 - r0), 0.0, 1.0)
```

For each bone `b` present in the union of `from` and `to` bone sets:

```
w_b = w_from_b * (1.0 - t) + w_to_b * t
```

where `w_from_b` and `w_to_b` default to 0.0 if bone `b` is not listed in the
respective set. Bones with `w_b > 0` are retained; bones with `w_b == 0` are
discarded.

The formula `w_from * (1.0 - t) + w_to * t` is **normative**. The algebraically
equivalent form `w_from + t * (w_to - w_from)` produces different IEEE 754 results
and MUST NOT be used.

### 9.6 Floating-Point Serialization

All vertex attributes (positions, normals) and skinning data (weights) written to GLB
buffers MUST be serialized as **IEEE 754 little-endian float32** (`binary32`).

Joint indices MUST be serialized as **little-endian uint16**.

Triangle indices MUST be serialized as **little-endian uint32**.

Inverse bind matrices MUST be serialized as float32, in **column-major** order (the
numpy row-major matrix is transposed before serialization).

**Quaternion serialization:** Pose rotations are authored as `[w, x, y, z]`
(scalar-first) in YAML. When serialized to GLB binary buffers, implementations MUST
reorder to `[x, y, z, w]` (vector-first) to match the glTF 2.0 accessor convention
for rotation data.

### 9.7 BufferView and Accessor Ordering

For each mesh (in YAML declaration order), buffer data MUST be emitted in this order:

1. Position data (float32 × 3 × N vertices)
2. Normal data (float32 × 3 × N vertices)
3. Index data (uint32 × M indices)
4. If the mesh is skinned:
   a. Joint indices (uint16 × 4 × N vertices)
   b. Weights (float32 × 4 × N vertices)
   c. Inverse bind matrices (float32 × 4 × 4 × J joints, column-major)

Each data block corresponds to one bufferView and one accessor, appended in the same
order to their respective glTF arrays.

### 9.8 Vertex Attribute Order

Mesh primitives MUST emit attributes in the following order:

* `POSITION`
* `NORMAL`
* `JOINTS_0` (if skinned)
* `WEIGHTS_0` (if skinned)

### 9.9 Binary Buffer Alignment

glTF 2.0 requires accessor alignment. Padding bytes between bufferViews, if needed,
MUST be zero-filled. Padding bytes are included in determinism checks (they are part
of the GLB binary blob).

---

## 10. Symmetry Interaction (from v0.3)

Symmetry expansion operates **before validation**, **before weight-map evaluation**,
and **before glTF emission**.

The rules from v0.3 remain normative:

* Deep-copy all primitives, bones, anchors, and ID-bearing objects
* Apply rename rules deterministically (e.g., `_L` → `_R`)
* Preserve stable output ordering: original items first, then mirrored items
* Negate X coordinates in positions, bone heads, bone tails
* Reverse triangle winding to preserve outward-facing normals
* Gradient `axis: x` MUST invert its range: `[a, b]` → `[-b, -a]`
* Other axes (`y`, `z`) preserve their range values
* External weight file paths are **not** mirrored (both sides reference the same file)

### 10.1 Materials and Symmetry

During symmetry expansion:

* Material references on primitives are **preserved unchanged**
* Material IDs are **not renamed or duplicated**
* The `materials` table itself is **not modified or duplicated**

Materials are not spatially dependent and do not participate in symmetry transforms.

---

## 11. Conformance Suite (Normative)

### 11.1 Conformance as Part of the Specification

The Rigy specification includes a **normative conformance suite**, consisting of:

* Canonical input files (`.rigy.yaml`)
* Canonical output artifacts (`.glb`)
* A manifest describing expected results

An implementation is **Rigy v0.6 conformant** if and only if it produces byte-identical
outputs for all positive conformance tests and rejects all negative conformance tests
with the correct error category.

### 11.2 Conformance Directory Structure

```
/conformance/
  manifest.json
  /inputs/
    *.rigy.yaml
  /outputs/
    *.glb
  /docs/
    *.md
```

### 11.3 Manifest Schema

```json
{
  "version": "0.6",
  "suite_revision": 1,
  "tests": [
    {
      "id": "A01_single_bone_identity",
      "category": "A",
      "type": "positive",
      "input": "inputs/A01_single_bone_identity.rigy.yaml",
      "expected_output": "outputs/A01_single_bone_identity.glb",
      "expected_sha256": "e3b0c44298fc1c149afbf4c8996fb924...",
      "description": "Single mesh, single bone, identity transform"
    },
    {
      "id": "F01_missing_bone_ref",
      "category": "F",
      "type": "negative",
      "input": "inputs/F01_missing_bone_ref.rigy.yaml",
      "expected_error_type": "ValidationError",
      "description": "Binding references a bone not in the armature"
    }
  ]
}
```

**Fields:**

* `version` — Spec version this suite targets
* `suite_revision` — Integer, incremented when conformance outputs are corrected within the same spec version (see Section 18.2)
* `tests[].id` — Unique test identifier
* `tests[].category` — Letter category (A through O, see below)
* `tests[].type` — `"positive"` (must produce output) or `"negative"` (must reject)
* `tests[].input` — Path to input YAML, relative to conformance root
* `tests[].expected_output` — Path to canonical GLB (positive tests only)
* `tests[].expected_sha256` — SHA-256 hex digest of the complete GLB file bytes (positive tests only)
* `tests[].expected_error_type` — Normative error category for negative tests
* `tests[].description` — Human-readable test description

### 11.4 Conformance Test Categories

#### A. Single-Bone Bind

* One mesh, one bone, identity transform
* Verifies baseline vertex binding, ordering, and binary layout

#### B. Multi-Bone Linear Blend

* Two or more bones with shared vertex influences
* Verifies weighted blending correctness and influence sorting

#### C. Gradient Influence Resolution

* Gradients with overlapping regions
* Verifies the normative interpolation formula (Section 9.5)
* Verifies deterministic bone ordering in the output

#### D. Maximum Influence Enforcement

* Inputs exceeding the 4-influence limit
* Verifies pruning, normalization, and padding rules (Sections 9.2–9.4)

#### E. Hierarchy Transform Propagation

* Parent/child bone relationships
* Verifies correct parent-relative translation in bone nodes
* Verifies inverse bind matrix computation

#### F. Validation Failure Cases

* Each hard error (V01–V42) SHOULD have at least one negative test
* Verifies the correct error type is raised and no output is produced

#### G. Symmetry Expansion

* Mirror-X with prefix substitution
* Verifies primitive duplication, bone duplication, X-negation
* Verifies gradient axis-x range inversion
* Verifies vertex count preservation and winding reversal

#### H. Composition

* Import resolution with namespace prefixing
* attach3 frame construction (rigid, uniform, affine modes)
* Local mesh instances
* Contract validation (positive: satisfied; negative: violated)

#### I. Weight Maps

* Gradient evaluation along each axis (x, y, z)
* External JSON source loading
* Override application after gradients
* Full 5-layer influence resolution (default → per-primitive → JSON → gradient → override)

#### J. Tessellation Profiles

* Each primitive type (box, sphere, cylinder, capsule) with known dimensions
* Verifies exact vertex count and index count
* Verifies deterministic vertex positioning

#### K. Edge Cases

* Unbound mesh (no binding, no armature)
* Root bone not at origin (warning case)
* Multiple armatures in a single file
* Mesh with single primitive vs. multiple primitives

#### L. DQS Posed Correctness

* DQS with identity and non-trivial poses
* Verifies volume-preserving blending behavior that distinguishes DQS from LBS

#### M. Solver Selection and Fallback Rules

* Mixed solver files (LBS and DQS in the same export)
* Per-binding override of top-level solver default

#### N. Quaternion Hemisphere Edge Cases

* Opposing quaternion signs and hemisphere consistency
* Near-antipodal quaternions and numerical stability

#### O. Materials

* Material definition, reference, and default behavior
* Material interaction with skinning
* Invalid material reference rejection

All categories MUST include both **positive** and **negative** cases where applicable.

### 11.5 DQS Conformance Output Format

Conformance fixtures for DQS (categories L–N) MUST output **baked GLB** files:

* Vertex `POSITION` attributes contain the final post-skinning coordinates (DQS already applied).
* Vertex `NORMAL` attributes contain the final post-skinning normals.
* The `skin` object and all joint/weight accessors are **removed** from the baked output.
* Bone nodes remain in the hierarchy for reference but carry identity transforms.

This eliminates engine-dependent interpretation of glTF skinning and allows byte-identical comparison of the actual deformation results.

Alternatively, a conformance fixture MAY provide a canonical JSON blob of vertex positions as a secondary reference format.

All conformance comparisons MUST be byte-exact.

### 11.6 Initial Conformance Fixtures (Normative)

#### Categories A–K (from v0.4)

* **I01 — arm_weight_maps**
  Input file: `arm_weight_maps.rigy.yaml`
  Purpose: validates per-vertex weight maps (gradients and overrides), influence
  resolution order, canonicalization (sort/cap/normalize/pad), and deterministic
  export.

* **E01 — humanoid**
  Input file: `humanoid.rigy.yaml`
  Purpose: validates armature parsing, hierarchy rules, symmetry interaction (if
  present), and deterministic export of joints/weights/IBMs as implemented.

> Note on composition fixtures: the project test suite includes composition-focused inputs (e.g., car/wheel import + attach3) to validate resolver and contract behavior.
> These are intentionally **not** part of the normative *binary* conformance set because the spec does not standardize a canonical "resolved composition" interchange format.
> Future suite revisions MAY add composition conformance by standardizing a canonical resolved document (or another deterministic intermediate) in addition to GLB outputs.

#### Category L — DQS Posed Correctness (from v0.5)

* **L01 — Single-bone DQS identity pose**
  Purpose: Verifies that DQS with an identity rotation and zero translation produces the same vertex positions as LBS. Establishes the baseline that DQS is a strict superset of rigid binding.

* **L02 — Two-bone DQS twist**
  Purpose: Classic forearm twist (candy-wrapper) scenario with two bones and shared vertex influences. Verifies volume-preserving blending behavior that distinguishes DQS from LBS.

#### Category M — Solver Selection and Fallback Rules (from v0.5)

* **M01 — Mixed solver file**
  Purpose: Single file with two bindings — one `lbs`, one `dqs`. Verifies that the implementation dispatches per-binding and produces correct output for both solvers in the same export.

* **M02 — Top-level override**
  Purpose: Top-level `skinning_solver: dqs` with one binding overriding to `lbs`. Verifies that per-binding values take precedence over the top-level default.

#### Category N — Quaternion Hemisphere Edge Cases (from v0.5)

* **N01 — Opposing quaternion signs**
  Purpose: Two bones whose rotation quaternions are in opposite hemispheres (`dot(qr_i, qr_ref) < 0`). Verifies that the negation rule produces correct blended output rather than the characteristic DQS "shortest path" artifact.

* **N02 — Near-antipodal quaternions**
  Purpose: Two bones where `dot(qr_i, qr_ref) ≈ 0` (near the hemisphere boundary). Verifies deterministic sign selection at the boundary and numerical stability of the blending pipeline.

#### Category O — Materials (from v0.6)

* **O01 — minimal_material**
  Single mesh, single primitive, material defined and referenced.

* **O02 — material_with_skinning**
  Skinned mesh with a valid material.

* **O03 — invalid_material_reference**
  Primitive references unknown material ID (expected error: V38).

Conformance tests do **not** compare rendered appearance.

---

## 12. Materials (Normative)

### 12.1 Material Table

Rigy v0.6 introduces an optional top-level `materials` table.

```yaml
materials:
  skin:
    base_color: [0.8, 0.6, 0.5, 1.0]
  glass:
    base_color: [0.7, 0.8, 0.9, 0.3]
```

* Keys are **material IDs**
* Material IDs share the same ID namespace and uniqueness rules as other Rigy identifiers
* Duplicate material IDs are a hard ValidationError (V37)

### 12.2 `base_color` (Required)

Each material MUST define `base_color`.

```yaml
base_color: [r, g, b, a]
```

Normative rules:

* Exactly **4 components**
* Components are **linear RGBA**
* Each component MUST be a finite float in `[0.0, 1.0]`

Semantic meaning:

* `rgb` expresses linear surface color
* `a` expresses **coverage**
  * `1.0` = fully opaque
  * `0.0` = fully transparent
  * intermediate values = partial coverage

Alpha expresses coverage only and does **not** imply blending mode, depth sorting, translucency lighting, or render-pipeline behavior.

### 12.3 Material References

A primitive MAY reference a material by ID:

```yaml
primitives:
  - id: torso
    type: capsule
    material: skin
```

Rules:

* Referencing an unknown material ID is a ValidationError (V38)
* Material references apply **per Rigy primitive**
* If omitted, the primitive uses the **implicit default material**

### 12.4 Default Material

If no material is specified, the primitive implicitly uses:

```yaml
base_color: [1.0, 1.0, 1.0, 1.0]
```

This default intentionally aligns with the glTF 2.0 default `pbrMetallicRoughness.baseColorFactor`.

The default material is conceptual and MUST NOT require an explicit entry in `materials`.

### 12.5 Mesh-Level Material Constraint

Rigy exporters emit **one glTF primitive per Rigy mesh**, merging all Rigy primitives into a single draw call.

To preserve determinism and avoid exporter ambiguity:

> **All primitives within a single Rigy mesh MUST reference the same material ID, or all MUST omit the material field.**

Violation of this rule is a ValidationError (V41).

> **Note:** This rule is based on *material reference identity*, not effective color equivalence. A primitive omitting `material` is not equivalent to explicitly referencing a material whose `base_color` equals the default.

This restriction MAY be relaxed in a future version when per-primitive glTF emission is standardized.

### 12.6 Import Namespacing for Materials

Imported assets introduce a namespace for their materials, consistent with existing import resolution rules.

* Materials defined in an imported asset are referenced as: `<import_id>.<material_id>`
* Materials defined locally are referenced as: `<material_id>`

Material references MUST resolve unambiguously. Failure to resolve a material reference, or a collision caused by ambiguous resolution, is a ValidationError (V42).

---

## 13. Skinning Solver Selection

### 13.1 `skinning_solver`

The `skinning_solver` field controls which skinning algorithm is used for deformation.

**Allowed values:**

* `lbs` — Linear Blend Skinning (default)
* `dqs` — Dual Quaternion Skinning

If omitted, implementations MUST assume `lbs`.

### 13.2 Scope

`skinning_solver` MAY be specified at the **top level** and/or **per binding**.

A per-binding value overrides the top-level value. If neither is specified, the solver defaults to `lbs`.

```yaml
# Top-level default applies to all bindings that don't override it
skinning_solver: dqs

bindings:
  - mesh_id: body_mesh
    armature_id: humanoid_armature
    # inherits dqs from top level

  - mesh_id: cloth_mesh
    armature_id: humanoid_armature
    skinning_solver: lbs   # overrides top-level dqs
```

---

## 14. Dual Quaternion Skinning (Normative)

### 14.1 Bone Transform Constraints

For both LBS and DQS:

* Bone transforms MUST be rigid (rotation + translation only).
* Non-uniform scale and shear are **invalid** for DQS evaluation.
* Uniform scale is **also invalid** for DQS evaluation. Rigy does not define scale semantics for dual quaternion blending; all bone transforms must be pure rotation + translation.

If a pose includes invalid transforms:

* Reference evaluators MUST raise the corresponding error (V35 or V36).
* Runtime engines MAY fall back to LBS, but this behavior is non-normative. Such fallback behavior MUST NOT be used in conformance evaluation.

### 14.2 Dual Quaternion Construction

For each bone:

* Let `qr` be the unit quaternion representing rotation.
* Let `t = (tx, ty, tz)` be the translation vector.
* Let `qt = (0, tx, ty, tz)` be a pure quaternion.
* Dual part: `qd = 0.5 * qt * qr`

The bone transform dual quaternion is:

```
dq = (qr, qd)
```

### 14.3 Hemisphere Consistency

Before blending, implementations MUST ensure quaternion hemisphere consistency:

* The reference quaternion `qr_ref` MUST be the real part of the influence with the lowest **absolute bone index in the armature's `bones` list** (i.e., the global bone ordering, not the vertex-local influence slot 0–3). This is consistent with the tertiary sort key used for influence canonicalization in Section 9.2.
* For each subsequent influence `i`: if `dot(qr_i, qr_ref) < 0`, negate both `qr_i` and `qd_i`.

### 14.4 Blending Rule

For a vertex with influences `(dq_i, w_i)`:

```
dq_sum = Σ (w_i * dq_i)
```

The resulting dual quaternion MUST be normalized using full dual-quaternion normalization:

1. Let `n = sqrt(dot(qr_sum, qr_sum))` using IEEE 754 float64 `sqrt()`, then `rn = 1.0 / n` using float64 division. Implementations MUST NOT substitute fast inverse square root approximations (e.g., Quake III `Q_rsqrt`) or fused `rsqrt` intrinsics, as these produce different bit-level results.
2. `qr' = qr_sum * rn`
3. `qd' = qd_sum * rn − dot(qr', qd_sum * rn) * qr'`

This ensures both `‖qr'‖ = 1` and `dot(qr', qd') = 0`. Real-part-only normalization (omitting step 3) is **not** sufficient.

### 14.5 Application

The normalized dual quaternion `(qr', qd')` is applied as follows:

* **Positions (mandatory):** Extract rotation `r = qr'` and translation `t' = 2 * qd' * conjugate(qr')`. Transform each position as `p' = rotate(r, p) + t'`, where `t'` uses only the vector part `(x, y, z)` of the resulting quaternion product.
* **Normals (mandatory for conformance):** Rotate each normal by `qr'` only (no translation). `n' = rotate(qr', n)`. The dual part does not affect normals.

---

## 15. Pose Evaluation

Rigy v0.5 introduced an optional pose evaluation block for testing and validation.

```yaml
poses:
  - id: forearm_twist
    bones:
      forearm:
        rotation: [0.9239, 0, 0.3827, 0]   # [w, x, y, z]
        translation: [0, 0, 0]
```

Quaternion component order in YAML is **`[w, x, y, z]`** (scalar-first). This differs from the glTF binary convention of `[x, y, z, w]` (vector-first); see Section 9.6 for the serialization rule.

Pose blocks:

* Are **optional** for general content
* Are **normative** for conformance suites
* Do **not** require GLB export unless explicitly requested

---

## 16. glTF Export (Normative)

### 16.1 Material Export

When exporting to glTF 2.0:

* `base_color` MUST be exported as `pbrMetallicRoughness.baseColorFactor`
* `metallicFactor` MUST be `0.0`
* `roughnessFactor` MUST be `1.0`

#### Alpha Mode (Deterministic)

To preserve byte-identical GLB output:

* If `base_color[3] == 1.0`, `alphaMode` MUST be `"OPAQUE"`
* Otherwise, `alphaMode` MUST be `"BLEND"`
* `alphaCutoff` MUST be omitted
* `doubleSided` MUST be `false`

#### Numeric Serialization

When serializing `baseColorFactor` into the glTF JSON:

1. Values MUST be computed as **IEEE 754 float32**
2. Values MUST be written using a fixed decimal format with **exactly six digits after the decimal point**, using round-half-even rounding

Example:

```json
"baseColorFactor": [1.000000, 0.300000, 0.666667, 1.000000]
```

This rule ensures cross-platform string identity.

---

## 17. Extension Points (Reserved)

Future extensions MUST:

* Operate on the same authoring data (YAML schema)
* Obey the same determinism and conformance rules
* Introduce new canonical tests upon activation

---

## 18. Binary Output Authority and Bug Correction

### 18.1 Canonical Outputs Are Authoritative — Until Proven Wrong

Canonical binary outputs in the conformance suite are **authoritative** for the
corresponding spec version and suite revision.

However, this authority is **conditional**, not absolute.

### 18.2 Bug Discovery and Correction Policy

Rigy explicitly rejects *bug-for-bug compatibility*.

If a bug is discovered such that:

* The spec text is incorrect, ambiguous, or incomplete, **or**
* The canonical output does not match the intended semantics of the spec

Then:

1. The spec text MUST be corrected
2. The conformance outputs MUST be regenerated
3. The `suite_revision` in the manifest MUST be incremented
4. The previous outputs are declared **non-canonical**
5. Determinism guarantees apply **only forward**, from the corrected suite revision

This may cause different outputs for the same input across suite revisions. This is
**intentional and acceptable**.

### 18.3 No Legacy Output Preservation

Rigy explicitly forbids:

* Preserving incorrect outputs for compatibility
* Encoding historical quirks as normative behavior
* Adding special-case logic to reproduce bugs

Once corrected, **incorrect output belongs to the past**.

---

## 19. Versioning and Trust Model

### 19.1 Version String Format

Rigy versions use `MAJOR.MINOR` format (e.g., `"0.6"`). While `MAJOR` is 0, the
project is pre-1.0 and minor versions may introduce breaking changes.

### 19.2 Parser Compatibility

A v0.6 conforming parser:

* MUST accept `version` values `"0.1"`, `"0.2"`, `"0.3"`, `"0.4"`, `"0.5"`, and `"0.6"`
* MUST reject `version` with major version ≥ 1
* SHOULD emit a warning for minor versions > 6 within major version 0

### 19.3 Suite Revision Numbering

Within a spec version, conformance suite corrections are tracked by `suite_revision`
(integer, starting at 1). This allows distinguishing "passes the original suite" from
"passes the corrected suite."

### 19.4 Trust Properties

* Determinism is guaranteed **within a version and suite revision**
* Corrections may invalidate earlier outputs
* Version numbers are semantic contracts, not cosmetic labels

---

## 20. Summary

Rigy v0.6 encompasses all features from v0.1 through v0.6:

* **Geometric primitives and armatures** with deterministic tessellation (v0.1)
* **Composition**: anchors, imports, instances, attach3, contracts (v0.2)
* **Per-vertex weight maps**: gradients, overrides, external sources (v0.3)
* **Formalization**: normative conformance suite, exhaustive validation table V01–V34, determinism contract, float64 precision (v0.4)
* **Dual Quaternion Skinning**: DQS solver, per-binding solver selection, pose evaluation, baked GLB export (v0.5)
* **Solid-color materials**: named materials, linear RGBA, deterministic glTF material export (v0.6)

The specification maintains:

* Determinism as executable truth, verified by a normative conformance suite (categories A–O)
* An exhaustive validation table (V01–V42)
* Precise canonicalization rules for all serialization
* A principled escape hatch for correcting mistakes (suite revisions)
* A firm refusal to fossilize bugs

> **Materials in v0.6 are data, not behavior.**

---

## Appendix A: Conformance Test Example

**Input** (`A01_single_bone_identity.rigy.yaml`):

```yaml
version: "0.6"

meshes:
  - id: cube
    primitives:
      - id: body
        type: box
        dimensions:
          width: 1.0
          height: 1.0
          depth: 1.0

armatures:
  - id: skeleton
    bones:
      - id: root
        head: [0, 0, 0]
        tail: [0, 1, 0]
        parent: none

bindings:
  - mesh_id: cube
    armature_id: skeleton
    weights:
      - primitive_id: body
        bones:
          - bone_id: root
            weight: 1.0
```

**Expected behavior:**
* 24 vertices, 36 indices (box tessellation)
* All vertices bound to joint 0 (root) with weight 1.0
* JOINTS_0: all `[0, 0, 0, 0]`
* WEIGHTS_0: all `[1.0, 0.0, 0.0, 0.0]`
* One inverse bind matrix: identity (root bone at origin)
* Byte-identical GLB on every run


---

## Appendix B. Normative Conformance Fixtures

This appendix embeds the current v0.6 conformance inputs verbatim. Implementations MUST treat the contents below as the normative source for these fixtures.

### I01 — arm_weight_maps.rigy.yaml

```yaml
version: "0.6"
units: meters
coordinate_system:
  up: Y
  forward: -Z
  handedness: right
tessellation_profile: v0_1_default
meshes:
- id: arm_mesh
  primitives:
  - type: capsule
    id: upper_arm
    dimensions:
      radius: 0.05
      height: 0.25
    transform:
      translation:
      - 0
      - 1.0
      - 0
  - type: capsule
    id: forearm
    dimensions:
      radius: 0.04
      height: 0.25
    transform:
      translation:
      - 0
      - 0.65
      - 0
armatures:
- id: arm_armature
  bones:
  - id: shoulder
    parent: none
    head:
    - 0
    - 1.15
    - 0
    tail:
    - 0
    - 0.9
    - 0
  - id: elbow
    parent: shoulder
    head:
    - 0
    - 0.9
    - 0
    tail:
    - 0
    - 0.65
    - 0
  - id: wrist
    parent: elbow
    head:
    - 0
    - 0.65
    - 0
    tail:
    - 0
    - 0.5
    - 0
bindings:
- mesh_id: arm_mesh
  armature_id: arm_armature
  weights:
  - primitive_id: upper_arm
    bones:
    - bone_id: shoulder
      weight: 1.0
  - primitive_id: forearm
    bones:
    - bone_id: elbow
      weight: 1.0
  weight_maps:
  - primitive_id: upper_arm
    gradients:
    - axis: y
      range:
      - 0.88
      - 1.02
      from:
      - bone_id: elbow
        weight: 1.0
      to:
      - bone_id: shoulder
        weight: 1.0
```

### E01 — humanoid.rigy.yaml

```yaml
version: "0.6"
units: meters
coordinate_system:
  up: Y
  forward: -Z
  handedness: right
tessellation_profile: v0_1_default
materials:
  skin:
    base_color: [0.8, 0.6, 0.5, 1.0]
meshes:
- id: humanoid_mesh
  name: Humanoid
  primitives:
  - type: capsule
    id: torso
    dimensions:
      radius: 0.15
      height: 0.3
    transform:
      translation:
      - 0
      - 1.15
      - 0
    material: skin
  - type: sphere
    id: head
    dimensions:
      radius: 0.12
    transform:
      translation:
      - 0
      - 1.6
      - 0
    material: skin
  - type: capsule
    id: legL_upper
    dimensions:
      radius: 0.07
      height: 0.25
    transform:
      translation:
      - 0.12
      - 0.65
      - 0
    material: skin
  - type: capsule
    id: legL_lower
    dimensions:
      radius: 0.05
      height: 0.28
    transform:
      translation:
      - 0.12
      - 0.24
      - 0
    material: skin
armatures:
- id: humanoid_armature
  name: HumanoidArmature
  bones:
  - id: root
    parent: none
    head:
    - 0
    - 0.9
    - 0
    tail:
    - 0
    - 0.95
    - 0
    roll: 0.0
  - id: spine
    parent: root
    head:
    - 0
    - 0.95
    - 0
    tail:
    - 0
    - 1.4
    - 0
    roll: 0.0
  - id: neck
    parent: spine
    head:
    - 0
    - 1.4
    - 0
    tail:
    - 0
    - 1.6
    - 0
    roll: 0.0
  - id: legL_upper
    parent: root
    head:
    - 0.12
    - 0.9
    - 0
    tail:
    - 0.12
    - 0.48
    - 0
    roll: 0.0
  - id: legL_lower
    parent: legL_upper
    head:
    - 0.12
    - 0.48
    - 0
    tail:
    - 0.12
    - 0.05
    - 0
    roll: 0.0
bindings:
- mesh_id: humanoid_mesh
  armature_id: humanoid_armature
  weights:
  - primitive_id: torso
    bones:
    - bone_id: spine
      weight: 1.0
  - primitive_id: head
    bones:
    - bone_id: neck
      weight: 1.0
  - primitive_id: legL_upper
    bones:
    - bone_id: legL_upper
      weight: 1.0
  - primitive_id: legL_lower
    bones:
    - bone_id: legL_lower
      weight: 1.0
symmetry:
  mirror_x:
    prefix_from: legL_
    prefix_to: legR_
```
