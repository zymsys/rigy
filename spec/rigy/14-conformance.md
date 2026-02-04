# 14. Conformance

## 14.1 Conformance as Part of the Specification

The Rigy specification includes a **normative conformance suite**, consisting of:

* Canonical input files (`.rigy.yaml`)
* Canonical output artifacts (`.glb`)
* A manifest describing expected results

An implementation is **Rigy v0.12 conformant** if and only if it produces byte-identical outputs for all positive conformance tests and rejects all negative conformance tests with the correct error category.

---

## 14.2 Conformance Directory Structure

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

---

## 14.3 Manifest Schema

```json
{
  "version": "0.12",
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
* `suite_revision` — Integer, incremented when conformance outputs are corrected within the same spec version
* `tests[].id` — Unique test identifier
* `tests[].category` — Letter category (A through R, see below)
* `tests[].type` — `"positive"` (must produce output) or `"negative"` (must reject)
* `tests[].input` — Path to input YAML, relative to conformance root
* `tests[].expected_output` — Path to canonical GLB (positive tests only)
* `tests[].expected_sha256` — SHA-256 hex digest of the complete GLB file bytes (positive tests only)
* `tests[].expected_error_type` — Normative error category for negative tests
* `tests[].description` — Human-readable test description

---

## 14.4 Conformance Test Categories

### A. Single-Bone Bind

* One mesh, one bone, identity transform
* Verifies baseline vertex binding, ordering, and binary layout

### B. Multi-Bone Linear Blend

* Two or more bones with shared vertex influences
* Verifies weighted blending correctness and influence sorting

### C. Gradient Influence Resolution

* Gradients with overlapping regions
* Verifies the normative interpolation formula
* Verifies deterministic bone ordering in the output

### D. Maximum Influence Enforcement

* Inputs exceeding the 4-influence limit
* Verifies pruning, normalization, and padding rules

### E. Hierarchy Transform Propagation

* Parent/child bone relationships
* Verifies correct parent-relative translation in bone nodes
* Verifies inverse bind matrix computation

### F. Validation Failure Cases

* Each hard error (V01-V78, F114-F116) SHOULD have at least one negative test
* Verifies the correct error type is raised and no output is produced

### G. Symmetry Expansion

* Mirror-X with prefix substitution
* Verifies primitive duplication, bone duplication, X-negation
* Verifies gradient axis-x range inversion
* Verifies vertex count preservation and winding reversal

### H. Composition

* Import resolution with namespace prefixing
* attach3 frame construction (rigid, uniform, affine modes)
* Local mesh instances
* Contract validation (positive: satisfied; negative: violated)

### I. Weight Maps

* Gradient evaluation along each axis (x, y, z)
* External JSON source loading
* Override application after gradients
* Full 5-layer influence resolution

### J. Tessellation Profiles

* Each primitive type (box, sphere, cylinder, capsule, wedge) with known dimensions
* Verifies exact vertex count and index count
* Verifies deterministic vertex positioning

### K. Edge Cases

* Unbound mesh (no binding, no armature)
* Root bone not at origin (warning case)
* Multiple armatures in a single file
* Mesh with single primitive vs. multiple primitives

### L. DQS Posed Correctness

* DQS with identity and non-trivial poses
* Verifies volume-preserving blending behavior that distinguishes DQS from LBS

### M. Solver Selection and Fallback Rules

* Mixed solver files (LBS and DQS in the same export)
* Per-binding override of top-level solver default

### N. Quaternion Hemisphere Edge Cases

* Opposing quaternion signs and hemisphere consistency
* Near-antipodal quaternions and numerical stability

### O. Materials

* Material definition, reference, and default behavior
* Material interaction with skinning
* Invalid material reference rejection

### P. UV Generation

* UV generator evaluation for each primitive type
* Verifies byte-identical `TEXCOORD_n` buffers
* Verifies symmetry interaction with UV sets
* Verifies multi-UV-set export

### Q. Wedge and Surface Keys

* Wedge geometry with known dimensions
* Verifies exact vertex count (18) and index count (24)
* Verifies surface key assignment for box and wedge
* Verifies flat normal generation
* Verifies version gating (`type: "wedge"` rejected in v0.8 documents)

### R. Preprocessing

* `params` substitution (scalar types preserved)
* `repeat` expansion (ordering and IDs)
* `repeat` + `params` combined
* Equivalence with fully expanded literal file (byte-identical output)
* AABB box syntax (v0.11)
* `box_decompose` macro (v0.11)
* Semantic tags (v0.11)
* Negative: duplicate YAML keys (V56), unknown fields (V57), non-scalar param (V58), unknown param (V59), illegal param usage (V60), param type mismatch (V61), invalid repeat forms (V62-V64), unresolved index token (V65), ID collision post-expansion (V66), macro ID collision (F114), AABB with transform (F115), invalid cutout ID (F116)

### S. v0.12 Features

* Expression evaluation and quantization
* Axis–angle rotation canonicalization and `rotation_quat` normalization
* Per-primitive materials with mixed-material meshes
* `box_decompose` implicit mesh targeting
* Version gating (V77)
* Per-primitive glTF emission with `rigy_id` extras
* Negative: expression errors (V68–V71), rotation errors (V67, V72, V73, V78), material resolution errors (V74, V75), box_decompose mesh mismatch (V76), version gating (V77)

All categories MUST include both **positive** and **negative** cases where applicable.

---

## 14.5 DQS Conformance Output Format

Conformance fixtures for DQS (categories L-N) MUST output **baked GLB** files:

* Vertex `POSITION` attributes contain the final post-skinning coordinates (DQS already applied).
* Vertex `NORMAL` attributes contain the final post-skinning normals.
* The `skin` object and all joint/weight accessors are **removed** from the baked output.
* Bone nodes remain in the hierarchy for reference but carry identity transforms.

This eliminates engine-dependent interpretation of glTF skinning and allows byte-identical comparison of the actual deformation results.

All conformance comparisons MUST be byte-exact.

---

## 14.6 v0.11 Conformance Additions

### Positive Fixtures

* **H110_box_aabb_basic** — Box with AABB syntax
* **H111_box_decompose_single_cutout** — Wall with one door cutout
* **H112_box_decompose_multi_cutout** — Wall with multiple cutouts

### Negative Fixtures

* **F114_macro_id_collision** — Generated ID collides with user ID
* **F115_aabb_with_transform** — AABB combined with transform (rejected)
* **F116_invalid_cutout_id** — Invalid cutout identifier

---

## 14.7 v0.12 Conformance Additions

### Positive Fixtures

* **S01_expression_basic** — Expression scalars with arithmetic and `sqrt()`
* **S02_expression_params** — Expressions referencing `$param` values
* **S03_axis_angle_rotation** — `rotation_axis_angle` canonicalized to `rotation_quat`
* **S04_rotation_quat_normalize** — `rotation_quat` normalization and sign convention
* **S05_per_primitive_material** — Mixed-material mesh with per-primitive glTF emission
* **S06_mesh_default_material** — Mesh-level `material` default with primitive override
* **S07_box_decompose_implicit** — `box_decompose` without explicit `mesh` field

### Negative Fixtures

* **V67_zero_axis** — Zero-length rotation axis
* **V68_expr_parse_error** — Invalid expression syntax
* **V69_expr_unknown_param** — Expression references undefined parameter
* **V70_expr_non_finite** — Expression produces NaN or Infinity
* **V71_expr_domain_error** — `sqrt()` of negative number
* **V72_multiple_rotations** — Multiple rotation forms on same transform
* **V73_non_finite_rotation** — Non-finite rotation component
* **V74_unresolved_material** — No material resolves when materials table exists
* **V75_unknown_material** — Primitive references undefined material
* **V76_mesh_mismatch** — `box_decompose.mesh` mismatches containing mesh
* **V77_version_gating** — v0.12 feature used in v0.11 document
* **V78_zero_quaternion** — Zero-length quaternion

---

**End of Chapter 14**
