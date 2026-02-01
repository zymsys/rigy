# Rigy Specification — v0.4-draft

**Status:** Draft
**Theme:** Determinism, Conformance, and Correctness
**Scope:** Formalization release (no new authoring constructs)

The key words MUST, MUST NOT, SHOULD, SHALL, and MAY in this document are to be
interpreted as described in [RFC 2119](https://www.ietf.org/rfc/rfc2119.txt).

---

## 1. Goals of v0.4

Rigy v0.4 is a **stabilization and formalization release**.

This version does **not** introduce new authoring concepts, solvers, or deformation
techniques. Instead, it establishes Rigy as a **deterministic, testable, and corrigible
specification**, suitable for long-term evolution.

The primary goals are:

* Make Rigy *executable* via a normative conformance suite
* Eliminate undefined or ambiguous behavior
* Formalize validation and error handling with an exhaustive rule table
* Establish a clear policy for correcting specification or implementation bugs

### 1.1 Relationship to Prior Versions

Rigy v0.4 is a **strict superset** of v0.3-rc2. All features from v0.1, v0.2, and v0.3
are retained without modification:

* **v0.1** — Geometric primitives, armatures, per-primitive skinning, symmetry
* **v0.2** — Anchors, imports, instances, attach3, contracts (Ricy)
* **v0.3** — Per-vertex weight maps (gradients, overrides, external JSON sources)

v0.4 adds normative constraints, a conformance suite, and an exhaustive validation
table. The only schema addition is the optional `skinning_solver` field (Section 12).

### 1.2 Roadmap Note

The v0.3 roadmap indicated that v0.4 would introduce Dual Quaternion Skinning. This
has been deferred to v0.5. The formalization work in this release is a prerequisite
for safely adding alternative skinning solvers.

---

## 2. Non-Goals

Rigy v0.4 explicitly does **not**:

* Add new skinning solvers (e.g. Dual Quaternion Skinning)
* Add corrective shapes or pose-space deformation
* Introduce runtime evaluation graphs, constraints, or control rigs
* Guarantee backward compatibility with incorrect outputs
* Change the tessellation profile or vertex counts for any primitive type

---

## 3. Migration from v0.3

All v0.3 files are valid v0.4 files. The only schema addition is the optional
`skinning_solver` field (see Section 12), which defaults to `"lbs"` when absent.

* The parser now accepts `version: "0.4"`
* A v0.4 parser MUST accept versions `"0.1"` through `"0.4"`
* A v0.4 parser MUST reject `version` with major version ≥ 1

Behavioral changes from v0.3:

* Non-finite numeric values (NaN, ±Infinity) are now a **hard error** (V32)
* All previously undefined behaviors are resolved (see Section 7.3)

---

## 4. Determinism Contract (Reaffirmed and Strengthened)

Rigy maintains the following core contract:

> **For a given Rigy input and a given Rigy specification version, a conforming
> implementation MUST produce byte-identical output artifacts.**

### 4.1 Superseding v0.1's Relaxation

v0.1 described determinism as "structural, not bit-identical floating-point." v0.3
strengthened this to byte-identical GLB. v0.4 **supersedes** v0.1's relaxation.
Byte-identical GLB output is the normative requirement for all conforming
implementations, retroactive to v0.3.

### 4.2 Intermediate Arithmetic Precision

Conforming implementations MUST perform intermediate arithmetic in at least IEEE 754
binary64 (float64) precision. Truncation to binary32 (float32) MUST occur only at the
serialization boundary (when writing to the GLB binary buffer).

This ensures that two conforming implementations produce identical bytes, regardless
of which programming language or library they use.

### 4.3 Scope of Determinism

* Determinism applies **only to correct behavior as defined by the spec**
* Outputs produced by incorrect behavior are **not protected**

This distinction is foundational to Rigy's evolution model (see Section 9).

---

## 5. Coordinate System and Units

Unchanged from v0.3.

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
| V32 | NaN or ±Infinity in any numeric field | ValidationError | **v0.4** |
| V33 | Unknown fields in strict-mode schema | ParseError | v0.1 |
| V34 | Missing required fields in schema | ParseError | v0.1 |

### 7.3 Soft Errors / Warnings (MUST warn, MAY continue)

Warnings MUST NOT affect output determinism. The output MUST be identical whether or
not the warning is emitted.

| ID | Condition | Since |
|----|-----------|-------|
| W01 | Vertex has more than 4 joint influences (before capping) | v0.3 |
| W02 | Per-primitive weights and weight map both target the same primitive | v0.3 |
| W03 | Armature root bone head not at origin (convention) | v0.2 |

### 7.4 Previously Undefined Behavior (Now Resolved)

Rigy v0.4 removes all previously implicit undefined behavior. Any input condition not
explicitly defined in this spec or prior specs is a **hard error**.

The following behaviors were previously underspecified and are now normatively defined:

| Condition | Resolution |
|-----------|-----------|
| All vertex weights are zero after influence resolution | Fall back to armature root bone, weight 1.0 |
| No bone in armature has `parent: none` | Use the first bone (index 0) as the root (note: in a finite bone set this implies a cycle, so V05 will typically reject first; this rule is a defensive fallback for root-detection logic) |
| Gradient `from` and `to` both yield zero weight for all bones at a vertex | Fall back to armature root bone, weight 1.0 |

---

## 8. Influence Resolution Order (Normative, restated from v0.3)

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

Rigy v0.4 locks down all canonicalization rules required for byte-identical output.
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

## 10. Symmetry Interaction (Restated from v0.3)

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

---

## 11. Conformance Suite (Normative)

### 11.1 Conformance as Part of the Specification

The Rigy specification includes a **normative conformance suite**, consisting of:

* Canonical input files (`.rigy.yaml`)
* Canonical output artifacts (`.glb`)
* A manifest describing expected results

An implementation is **Rigy v0.4 conformant** if and only if it produces byte-identical
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
  "version": "0.4",
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
* `suite_revision` — Integer, incremented when conformance outputs are corrected within the same spec version (see Section 13.2)
* `tests[].id` — Unique test identifier
* `tests[].category` — Letter category (A through K, see below)
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

* Each hard error (V01–V34) SHOULD have at least one negative test
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

All categories MUST include both **positive** and **negative** cases where applicable.

---


### 11.5 Initial Conformance Fixtures (Normative)

Rigy v0.4 defines the following initial conformance inputs. These are the only
required fixtures for v0.4; additional fixtures MAY be added in future suite
revisions.

* **I01 — arm_weight_maps**
  Input file: `arm_weight_maps.rigy.yaml`
  Purpose: validates per-vertex weight maps (gradients and overrides), influence
  resolution order, canonicalization (sort/cap/normalize/pad), and deterministic
  export.

* **E01 — humanoid**
  Input file: `humanoid.rigy.yaml`
  Purpose: validates armature parsing, hierarchy rules, symmetry interaction (if
  present), and deterministic export of joints/weights/IBMs as implemented.

Conforming implementations MUST include these files under `conformance/inputs/` and
MUST include their corresponding canonical outputs under `conformance/outputs/`.

> Note on composition fixtures: the project test suite includes composition-focused inputs (e.g., car/wheel import + attach3) to validate resolver and contract behavior.
> These are intentionally **not** part of the v0.4 normative *binary* conformance set because v0.4 does not standardize a canonical “resolved composition” interchange format.
> Future suite revisions MAY add composition conformance by standardizing a canonical resolved document (or another deterministic intermediate) in addition to GLB outputs.


## 12. Extension Points (Reserved)

Rigy v0.4 reserves the following field for future use:

* `skinning_solver` — If present in a v0.4 file, its value MUST be `"lbs"`. Any other value is a hard error.  If absent, the default is `"lbs"`.

Future extensions MUST:

* Operate on the same authoring data (YAML schema)
* Obey the same determinism and conformance rules
* Introduce new canonical tests upon activation

---

## 13. Binary Output Authority and Bug Correction

### 13.1 Canonical Outputs Are Authoritative — Until Proven Wrong

Canonical binary outputs in the conformance suite are **authoritative** for the
corresponding spec version and suite revision.

However, this authority is **conditional**, not absolute.

### 13.2 Bug Discovery and Correction Policy

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

### 13.3 No Legacy Output Preservation

Rigy explicitly forbids:

* Preserving incorrect outputs for compatibility
* Encoding historical quirks as normative behavior
* Adding special-case logic to reproduce bugs

Once corrected, **incorrect output belongs to the past**.

---

## 14. Versioning and Trust Model

### 14.1 Version String Format

Rigy versions use `MAJOR.MINOR` format (e.g., `"0.4"`). While `MAJOR` is 0, the
project is pre-1.0 and minor versions may introduce breaking changes.

### 14.2 Parser Compatibility

A v0.4 conforming parser:

* MUST accept `version` values `"0.1"`, `"0.2"`, `"0.3"`, and `"0.4"`
* MUST reject `version` with major version ≥ 1
* SHOULD emit a warning for minor versions > 4 within major version 0

### 14.3 Suite Revision Numbering

Within a spec version, conformance suite corrections are tracked by `suite_revision`
(integer, starting at 1). This allows distinguishing "passes the original suite" from
"passes the corrected suite."

### 14.4 Trust Properties

* Determinism is guaranteed **within a version and suite revision**
* Corrections may invalidate earlier outputs
* Version numbers are semantic contracts, not cosmetic labels

---

## 15. Summary

Rigy v0.4 establishes:

* Determinism as executable truth, verified by a normative conformance suite
* An exhaustive validation table replacing ad-hoc error examples
* Precise canonicalization rules for influence sorting, normalization, padding, and serialization
* A principled escape hatch for correcting mistakes (suite revisions)
* A firm refusal to fossilize bugs

This version exists so that future advances (e.g. DQS in v0.5) can be added
**without fear** of destabilizing the foundation.

---

## Appendix A: Conformance Test Example

**Input** (`A01_single_bone_identity.rigy.yaml`):

```yaml
version: "0.4"

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

This appendix embeds the current v0.4 conformance inputs verbatim. Implementations MUST treat the contents below as the normative source for these fixtures.

### I01 — arm_weight_maps.rigy.yaml

```yaml
version: "0.4"
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
version: "0.4"
units: meters
coordinate_system:
  up: Y
  forward: -Z
  handedness: right
tessellation_profile: v0_1_default
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
