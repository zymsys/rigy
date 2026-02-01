# Rigy v0.5 — Draft Amendment to v0.4

**Status:** Draft (proposed)
**Amends:** Rigy v0.4 (`rigy_spec_v0.4-rc3.md`)

**Theme:** *Same authoring model, better deformation*

This document is an amendment to the Rigy v0.4 specification. All normative definitions from v0.4 (schema, validation rules V01–V34, tessellation profiles, skinning pipeline, error hierarchy, composition, symmetry, and conformance categories A–K) remain in effect unless explicitly overridden below.

Rigy v0.5 introduces alternative skinning solvers—most notably **Dual Quaternion Skinning (DQS)**—while preserving the authoring model established in v0.3 and stabilized in v0.4. No new deformation primitives, modeling constructs, or rig authoring concepts are introduced.

---

## 1. Goals

1. Enable **Dual Quaternion Skinning (DQS)** as a first-class, deterministic skinning solver.
2. Preserve the **existing authoring surface**: bones, weights, gradients, overrides, imports, instances, and `attach3` remain unchanged.
3. Maintain **deterministic evaluation** suitable for byte-for-byte conformance testing.
4. Provide a **normative reference definition** for DQS so independent implementations produce equivalent results.

---

## 2. Non-Goals

Rigy v0.5 does **not** introduce:

- Blendshapes, corrective shapes, or pose-space deformation
- IK systems, constraints, or control rigs
- Animation graphs or timelines
- Freeform transforms or scripting
- Topology or tessellation changes

---

## 3. Skinning Solver Selection

### 3.1 `skinning_solver`

The `skinning_solver` field, reserved in v0.4 (see v0.4 spec §5), is promoted from *reserved* to *active*.

**Allowed values:**
- `lbs` — Linear Blend Skinning (default)
- `dqs` — Dual Quaternion Skinning

If omitted, implementations **MUST** assume `lbs`.

### 3.2 Scope

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

## 4. Bone Transform Constraints

For both LBS and DQS:

- Bone transforms **MUST** be rigid (rotation + translation only).
- Non-uniform scale and shear are **invalid** for DQS evaluation.
- Uniform scale is **also invalid** for DQS evaluation. Rigy does not define scale semantics for dual quaternion blending; all bone transforms must be pure rotation + translation.

The following error codes are appended to the v0.4 Error Table (§7.2):

| ID   | Condition                                      | Severity   |
|------|------------------------------------------------|------------|
| V35  | Non-rigid bone transform in DQS binding (scale, shear, or uniform scale present) | Hard Error |
| V36  | Invalid pose quaternion (non-unit norm, NaN, or Infinity component)               | Hard Error |

If a pose includes invalid transforms:
- Reference evaluators **MUST** raise the corresponding error (V35 or V36).
- Runtime engines MAY fall back to LBS, but this behavior is non-normative. Such fallback behavior **MUST NOT** be used in conformance evaluation.

---

## 5. Dual Quaternion Skinning (Normative)

### 5.1 Dual Quaternion Construction

For each bone:

- Let `qr` be the unit quaternion representing rotation.
- Let `t = (tx, ty, tz)` be the translation vector.
- Let `qt = (0, tx, ty, tz)` be a pure quaternion.
- Dual part: `qd = 0.5 * qt * qr`

The bone transform dual quaternion is:

```
dq = (qr, qd)
```

### 5.2 Hemisphere Consistency

Before blending, implementations **MUST** ensure quaternion hemisphere consistency:

- The reference quaternion `qr_ref` **MUST** be the real part of the influence with the lowest **absolute bone index in the armature's `bones` list** (i.e., the global bone ordering, not the vertex-local influence slot 0–3). This is consistent with the tertiary sort key used for influence canonicalization in v0.4 §9.3.
- For each subsequent influence `i`: if `dot(qr_i, qr_ref) < 0`, negate both `qr_i` and `qd_i`.

### 5.3 Blending Rule

For a vertex with influences `(dq_i, w_i)`:

```
dq_sum = Σ (w_i * dq_i)
```

The resulting dual quaternion **MUST** be normalized using full dual-quaternion normalization:

1. Let `n = sqrt(dot(qr_sum, qr_sum))` using IEEE 754 float64 `sqrt()`, then `rn = 1.0 / n` using float64 division. Implementations **MUST NOT** substitute fast inverse square root approximations (e.g., Quake III `Q_rsqrt`) or fused `rsqrt` intrinsics, as these produce different bit-level results.
2. `qr' = qr_sum * rn`
3. `qd' = qd_sum * rn − dot(qr', qd_sum * rn) * qr'`

This ensures both `‖qr'‖ = 1` and `dot(qr', qd') = 0`. Real-part-only normalization (omitting step 3) is **not** sufficient.

### 5.4 Application

The normalized dual quaternion `(qr', qd')` is applied as follows:

- **Positions (mandatory):** Extract rotation `r = qr'` and translation `t' = 2 * qd' * conjugate(qr')`. Transform each position as `p' = rotate(r, p) + t'`, where `t'` uses only the vector part `(x, y, z)` of the resulting quaternion product.
- **Normals (mandatory for conformance):** Rotate each normal by `qr'` only (no translation). `n' = rotate(qr', n)`. The dual part does not affect normals.

---

## 6. Determinism Requirements

To ensure conformance:

- All intermediate calculations **MUST** use float64 precision.
- Quaternion sign selection **MUST** follow the hemisphere rule above.
- Final vertex outputs **MUST** be converted to float32 using IEEE 754 round-to-nearest-even (the default rounding mode). Implementations **MUST NOT** use truncation or other rounding modes for this conversion.
- Algebraic reorderings that change IEEE results are prohibited in the reference evaluator.
- **Quaternion serialization:** Pose rotations are authored as `[w, x, y, z]` (scalar-first) in YAML. When serialized to GLB binary buffers, implementations **MUST** reorder to `[x, y, z, w]` (vector-first) to match the glTF 2.0 accessor convention for rotation data.

---

## 7. Pose Evaluation (Conformance Only)

Rigy v0.5 introduces an optional pose evaluation block for testing and validation.

```yaml
poses:
  - id: forearm_twist
    bones:
      forearm:
        rotation: [0.9239, 0, 0.3827, 0]   # [w, x, y, z]
        translation: [0, 0, 0]
```

Quaternion component order in YAML is **`[w, x, y, z]`** (scalar-first). This differs from the glTF binary convention of `[x, y, z, w]` (vector-first); see Section 6 for the serialization rule.

Pose blocks:
- Are **optional** for general content
- Are **normative** for conformance suites
- Do **not** require GLB export unless explicitly requested

---

## 8. Conformance Suite Additions

### 8.1 New Test Categories

v0.4 defines categories A through K. v0.5 continues the sequence:

- **L. DQS posed correctness**
- **M. Solver selection and fallback rules**
- **N. Quaternion hemisphere edge cases**

### 8.2 Output Comparison

Conformance fixtures for DQS (categories L–N) **MUST** output **baked GLB** files:

- Vertex `POSITION` attributes contain the final post-skinning coordinates (DQS already applied).
- Vertex `NORMAL` attributes contain the final post-skinning normals.
- The `skin` object and all joint/weight accessors are **removed** from the baked output.
- Bone nodes remain in the hierarchy for reference but carry identity transforms.

This eliminates engine-dependent interpretation of glTF skinning and allows byte-identical comparison of the actual deformation results.

Alternatively, a conformance fixture MAY provide a canonical JSON blob of vertex positions as a secondary reference format.

All conformance comparisons **MUST** be byte-exact.

### 8.3 Initial Conformance Fixtures (Normative)

The following fixtures are required for v0.5. Input YAML and baked GLB outputs will be provided under `conformance/`.

#### L. DQS Posed Correctness

* **L01 — Single-bone DQS identity pose**
  Purpose: Verifies that DQS with an identity rotation and zero translation produces the same vertex positions as LBS. Establishes the baseline that DQS is a strict superset of rigid binding.

* **L02 — Two-bone DQS twist**
  Purpose: Classic forearm twist (candy-wrapper) scenario with two bones and shared vertex influences. Verifies volume-preserving blending behavior that distinguishes DQS from LBS.

#### M. Solver Selection and Fallback Rules

* **M01 — Mixed solver file**
  Purpose: Single file with two bindings — one `lbs`, one `dqs`. Verifies that the implementation dispatches per-binding and produces correct output for both solvers in the same export.

* **M02 — Top-level override**
  Purpose: Top-level `skinning_solver: dqs` with one binding overriding to `lbs`. Verifies that per-binding values take precedence over the top-level default.

#### N. Quaternion Hemisphere Edge Cases

* **N01 — Opposing quaternion signs**
  Purpose: Two bones whose rotation quaternions are in opposite hemispheres (`dot(qr_i, qr_ref) < 0`). Verifies that the negation rule produces correct blended output rather than the characteristic DQS "shortest path" artifact.

* **N02 — Near-antipodal quaternions**
  Purpose: Two bones where `dot(qr_i, qr_ref) ≈ 0` (near the hemisphere boundary). Verifies deterministic sign selection at the boundary and numerical stability of the blending pipeline.

---

## 9. Migration and Compatibility

- **Forward compatibility:** All v0.4-valid files remain valid under v0.5.
- **Backward incompatibility:** A v0.5 file specifying `skinning_solver: dqs` or `rigy_version: "0.5"` is **not** valid v0.4. A v0.4 parser (which uses `extra="forbid"` and rejects unknown field values) **MUST** reject such files with a `ParseError`. Authors should set `rigy_version: "0.5"` when using any v0.5 feature to ensure early rejection by older tooling.
- Authoring data (weights, gradients, overrides) is unchanged.

---

## 10. Roadmap Context (Non-Normative)

Rigy v0.5 intentionally improves deformation quality without expanding the authoring model. This enables future work such as:

- Optional corrective shapes
- Pose-space deformation
- Constraints and control rigs

without destabilizing existing content.

---

**End of Draft v0.5 Specification**