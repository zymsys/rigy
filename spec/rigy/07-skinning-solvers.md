# 7. Skinning Solvers

## 7.1 Solver Selection

The `skinning_solver` field controls which skinning algorithm is used for deformation.

**Allowed values:**

* `lbs` — Linear Blend Skinning (default)
* `dqs` — Dual Quaternion Skinning

If omitted, implementations MUST assume `lbs`.

### Scope

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

## 7.2 Dual Quaternion Skinning (Normative)

### Bone Transform Constraints

For both LBS and DQS:

* Bone transforms MUST be rigid (rotation + translation only).
* Non-uniform scale and shear are **invalid** for DQS evaluation.
* Uniform scale is **also invalid** for DQS evaluation. Rigy does not define scale semantics for dual quaternion blending; all bone transforms must be pure rotation + translation.

If a pose includes invalid transforms:

* Reference evaluators MUST raise the corresponding error (V35 or V36).
* Runtime engines MAY fall back to LBS, but this behavior is non-normative. Such fallback behavior MUST NOT be used in conformance evaluation.

### Dual Quaternion Construction

For each bone:

* Let `qr` be the unit quaternion representing rotation.
* Let `t = (tx, ty, tz)` be the translation vector.
* Let `qt = (0, tx, ty, tz)` be a pure quaternion.
* Dual part: `qd = 0.5 * qt * qr`

The bone transform dual quaternion is:

```
dq = (qr, qd)
```

### Hemisphere Consistency

Before blending, implementations MUST ensure quaternion hemisphere consistency:

* The reference quaternion `qr_ref` MUST be the real part of the influence with the lowest **absolute bone index in the armature's `bones` list** (i.e., the global bone ordering, not the vertex-local influence slot 0-3). This is consistent with the tertiary sort key used for influence canonicalization.
* For each subsequent influence `i`: if `dot(qr_i, qr_ref) < 0`, negate both `qr_i` and `qd_i`.

### Blending Rule

For a vertex with influences `(dq_i, w_i)`:

```
dq_sum = sum(w_i * dq_i)
```

The resulting dual quaternion MUST be normalized using full dual-quaternion normalization:

1. Let `n = sqrt(dot(qr_sum, qr_sum))` using IEEE 754 float64 `sqrt()`, then `rn = 1.0 / n` using float64 division. Implementations MUST NOT substitute fast inverse square root approximations (e.g., Quake III `Q_rsqrt`) or fused `rsqrt` intrinsics, as these produce different bit-level results.
2. `qr' = qr_sum * rn`
3. `qd' = qd_sum * rn - dot(qr', qd_sum * rn) * qr'`

This ensures both `||qr'|| = 1` and `dot(qr', qd') = 0`. Real-part-only normalization (omitting step 3) is **not** sufficient.

### Application

The normalized dual quaternion `(qr', qd')` is applied as follows:

* **Positions (mandatory):** Extract rotation `r = qr'` and translation `t' = 2 * qd' * conjugate(qr')`. Transform each position as `p' = rotate(r, p) + t'`, where `t'` uses only the vector part `(x, y, z)` of the resulting quaternion product.
* **Normals (mandatory for conformance):** Rotate each normal by `qr'` only (no translation). `n' = rotate(qr', n)`. The dual part does not affect normals.

---

## 7.3 Pose Evaluation

Rigy v0.5 introduced an optional pose evaluation block for testing and validation.

```yaml
poses:
  - id: forearm_twist
    bones:
      forearm:
        rotation: [0.9239, 0, 0.3827, 0]   # [w, x, y, z]
        translation: [0, 0, 0]
```

Quaternion component order in YAML is **`[w, x, y, z]`** (scalar-first). This differs from the glTF binary convention of `[x, y, z, w]` (vector-first); see [Chapter 13](13-gltf-export.md) for the serialization rule.

Pose blocks:

* Are **optional** for general content
* Are **normative** for conformance suites
* Do **not** require GLB export unless explicitly requested

---

**End of Chapter 7**
