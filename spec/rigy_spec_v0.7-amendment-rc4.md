# Rigy v0.7 — Draft Amendment (UV Roles & Schema-Only Semantics)

**Status:** Draft (proposed, revised)  
**Amends:** Rigy v0.6  
**Theme:** *Intentful UV references without UV data or generation*

**Keywords:** The key words MUST, MUST NOT, SHOULD, SHALL, and MAY in this document are to be
interpreted as described in RFC 2119.

---

## 0. Scope Clarification (Normative)

Rigy v0.7 is a **schema- and validation-only release** with respect to UVs.

> **Rigy v0.7 MUST NOT introduce UV coordinate data, UV generation, or UV export.**  
> Files using UV roles remain geometrically identical to v0.6 outputs.  
> Implementations MUST NOT emit `TEXCOORD_n` attributes in GLB output in v0.7.

UV roles introduced here are **semantic references only**. They become *operational*
only when UV coordinate data or generators are introduced in a later version
(anticipated v0.8).

---

## 1. Goals

Rigy v0.7 introduces **UV Roles**: a standardized vocabulary for referring to
texture coordinate *intent* by meaning instead of numeric index.

The goals are to:

1. Standardize a **finite, versioned UV role vocabulary**.
2. Allow assets to declare which UV roles they expose.
3. Allow materials to reference UV roles *by name*, not index.
4. Enable deterministic validation of asset–material compatibility.
5. Avoid premature commitment to unwrap algorithms or texture sampling semantics.

---

## 2. Non-Goals

Rigy v0.7 explicitly does **not** introduce:

- UV coordinates or vertex attributes
- UV unwrapping or projection algorithms
- Texture images, samplers, or PBR parameters
- Changes to GLB binary output
- Runtime-visible rendering differences

---

## 3. UV Roles (Normative)

### 3.1 Definition

A **UV Role** is a semantic identifier describing the *intended usage* of a texture
coordinate layout.

Roles are **author-facing**, **meaningful**, and **independent of UV indices**.

---

### 3.2 Initial UV Role Vocabulary (Normative)

The following roles are defined in Rigy v0.7. This table is **authoritative**.

| Role         | Meaning |
|--------------|---------|
| `albedo`     | Primary surface parameterization intended for base color or low-frequency surface detail. Typically non-overlapping and contiguous. |
| `detail`     | Secondary parameterization intended for high-frequency, tiling detail layered over another map. |
| `directional`| Parameterization with a stable dominant direction (e.g. wood grain, fabric weave). Orientation consistency is required; tiling is permitted. |
| `radial`     | Parameterization organized around a central point or axis (e.g. coins, knobs, dials). Continuity around the center is required; tiling is typically not expected. |
| `decal`      | Localized, non-tiling parameterization intended for labels, stickers, or markings applied to a subset of the surface. |
| `lightmap`   | Reserved role for baked lighting or similar secondary bake data. No semantics defined in v0.7. |

### 3.3 Vocabulary Stability

- This role set is **finite and normative** for v0.7.
- Future minor versions MAY add new roles.
- Existing roles MUST NOT change meaning or be removed.

---

## 4. Asset-Side UV Role Exposure

Meshes or primitives MAY declare which UV roles they expose.

```yaml
uv_roles:
  albedo:
    set: uv0
  detail:
    set: uv0
  decal:
    set: uv1
```

### 4.1 Semantics

- `set` identifies a **UV set token**, not actual UV data.
- UV set tokens are symbolic placeholders in v0.7; they MUST NOT be interpreted as UV coordinate data.

### 4.2 Constraints (Normative)

### 4.3 Scope (Normative)

The `uv_roles` block is a **mesh-level declaration**.

- All primitives within a mesh share the same UV role exposure.
- This aligns with Rigy v0.6’s rule that a mesh compiles to a single glTF primitive.
- Implementations MUST NOT allow per-primitive UV role declarations in v0.7.



- Each role MUST resolve to exactly one UV set token.
- Multiple roles MAY resolve to the same UV set token.
- A role MUST NOT be declared more than once.
- UV set tokens MUST follow the pattern `uv<N>` where `<N>` is a non-negative integer.

Violations are **ValidationError**.

---

## 5. Material-Side UV Role Reference

Materials MAY reference UV roles symbolically.

```yaml
material: cheese
uses_uv_roles:
  - radial
```

### 5.1 Validation Rules (Normative)

- If a material references a UV role not exposed by the target asset, compilation
  **MUST fail** with a ValidationError.
- In v0.7, referencing UV roles has **no effect on export output**.
- Implementations MUST NOT attempt to infer or synthesize UV data.

---

## 6. UV Set Tokens and glTF Mapping (Normative)

- UV set tokens (`uv0`, `uv1`, …) are **schema-level identifiers only** in v0.7.
- They correspond conceptually to glTF attributes `TEXCOORD_0`, `TEXCOORD_1`, etc.
- In v0.7, no `TEXCOORD_n` attributes are emitted, regardless of token usage.
- Numeric ordering of UV set tokens is zero-based and canonical.

---


## 7. Validation Error Codes (Normative)

Rigy v0.7 appends the following validation rules. These codes are in addition to any
prior-version validation rules that remain in effect.

| ID  | Condition | Error Type | Severity |
|-----|-----------|------------|----------|
| V43 | `uv_roles` declares a role not in the v0.7 role vocabulary | ValidationError | Hard Error |
| V44 | Duplicate role key in `uv_roles` (after canonical YAML mapping resolution) | ValidationError | Hard Error |
| V45 | `uv_roles.<role>.set` is not a valid UV set token (`uv<N>`, N ≥ 0) | ValidationError | Hard Error |
| V46 | A material references a UV role not exposed by the target asset | ValidationError | Hard Error |
| V47 | `uses_uv_roles` contains a role not in the v0.7 role vocabulary | ValidationError | Hard Error |

**Notes (Normative):**
- Role identifiers are case-sensitive UTF-8 strings; implementations MUST NOT apply
  locale collation, normalization, or case folding during comparisons.
- If a YAML parser delivers duplicate mapping keys, implementations MUST treat this
  as V44 even if the underlying YAML library would otherwise “last-win”.



## 8. Interaction with Symmetry Expansion (Normative)

During symmetry expansion:

- `uv_roles` declarations MUST be deep-copied verbatim to mirrored meshes.
- Role names and UV set tokens are preserved unchanged.
- No implicit U/V flipping or remapping occurs in v0.7.

Any UV-space mirroring behavior, if introduced, MUST be explicitly defined in a
future version.


**Non-Goal (v0.7):**  
Rigy v0.7 does not define any behavior for adjusting UV orientation under symmetry
(e.g., U-axis flipping for directional textures). Although triangle winding is
reversed during symmetry expansion in v0.6 to preserve normals, UV roles and their
associated set tokens are copied verbatim. Any UV-space mirroring or reorientation
logic MUST be explicitly specified in a future version when UV data exists.

---

## 9. Determinism

UV role resolution and validation:

- MUST be deterministic
- MUST NOT affect vertex ordering, attribute buffers, or binary output
- MUST NOT introduce exporter discretion

---

## 10. Conformance and Examples (Normative)

### 9.1 Positive Example

```yaml
meshes:
  - id: moon
    primitives:
      - id: body
        type: sphere
    uv_roles:
      radial:
        set: uv0
```

Valid under v0.7. Produces identical output to v0.6.

---

### 9.2 Negative Example (Role Not Exposed)

```yaml
material: cheese
uses_uv_roles:
  - radial
```

Applied to a mesh without `radial` in `uv_roles` → **ValidationError**.

---

## 11. Summary

Rigy v0.7 introduces **semantic UV indirection without UV data**.

It standardizes:
- a finite, versioned role vocabulary
- asset-declared UV intent
- material-side validation

It deliberately does **nothing** at runtime or export level.

This creates a stable foundation for deterministic UV data and generation in v0.8
without retrofitting meaning or breaking compatibility.

---

**End of Draft v0.7 Amendment (Revised)**
