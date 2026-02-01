# Rigy v0.6 — Draft Amendment (RC2)

**Status:** Draft (release candidate 2)
**Amends:** Rigy v0.5
**Theme:** *Solid-color materials, no textures*

This document amends the Rigy v0.5 specification. All definitions, guarantees, validation rules, conformance requirements, and behaviors from v0.1 through v0.5 remain in effect unless explicitly overridden here.

---

## 1. Purpose and Scope

Rigy v0.6 introduces **solid-color materials** as a first-class authoring concept within Rigy.

This release enables authors to:

- Define named materials
- Assign materials to primitives
- Express deterministic color and alpha intent

Rigy v0.6 intentionally does **not** introduce:

- Textures
- UV coordinates or UV evaluation
- Shading models
- Lighting semantics
- Blend modes or render-pipeline behavior

Materials in v0.6 are declarative data only and do not affect geometry, skinning, or determinism guarantees.

---

## 2. Materials (Normative)

### 2.1 Material Table

Rigy v0.6 introduces an optional top-level `materials` table.

```yaml
materials:
  skin:
    base_color: [0.8, 0.6, 0.5, 1.0]
  glass:
    base_color: [0.7, 0.8, 0.9, 0.3]
```

- Keys are **material IDs**
- Material IDs share the same ID namespace and uniqueness rules as other Rigy identifiers
- Duplicate material IDs are a **hard ValidationError**

Materials are defined directly in Rigy. No separate schema or external specification is implied by this amendment.

---

### 2.2 `base_color` (Required)

Each material MUST define `base_color`.

```yaml
base_color: [r, g, b, a]
```

Normative rules:

- Exactly **4 components**
- Components are **linear RGBA**
- Each component MUST be a finite float in `[0.0, 1.0]`

Semantic meaning:

- `rgb` expresses linear surface color
- `a` expresses **coverage**
  - `1.0` = fully opaque
  - `0.0` = fully transparent
  - intermediate values = partial coverage

Alpha expresses coverage only and does **not** imply blending mode, depth sorting, translucency lighting, or render-pipeline behavior.

---

## 3. Material References (Normative)

### 3.1 Primitive-Level Assignment

A primitive MAY reference a material by ID:

```yaml
primitives:
  - id: torso
    type: capsule
    material: skin
```

Rules:

- Referencing an unknown material ID is a **ValidationError**
- Material references apply **per Rigy primitive**
- If omitted, the primitive uses the **implicit default material**

---

### 3.2 Default Material

If no material is specified, the primitive implicitly uses:

```yaml
base_color: [1.0, 1.0, 1.0, 1.0]
```

This default intentionally aligns with the glTF 2.0 default `pbrMetallicRoughness.baseColorFactor`.

The default material is conceptual and MUST NOT require an explicit entry in `materials`.

---

## 4. Mesh-Level Material Constraint (Normative)

Rigy exporters currently emit **one glTF primitive per Rigy mesh**, merging all Rigy primitives into a single draw call.

To preserve determinism and avoid exporter ambiguity:

> **All primitives within a single Rigy mesh MUST reference the same material ID, or all MUST omit the material field.**

Violation of this rule is a **ValidationError**.

> **Note:** This rule is based on *material reference identity*, not effective color equivalence. A primitive omitting `material` is not equivalent to explicitly referencing a material whose `base_color` equals the default.

This restriction MAY be relaxed in a future version when per-primitive glTF emission is standardized.

---

## 5. Symmetry Interaction (Normative)

Material definitions and references interact with symmetry as follows:

- During symmetry expansion, **material references on primitives are preserved unchanged**
- Material IDs are **not renamed or duplicated**
- The `materials` table itself is **not modified or duplicated**

Materials are not spatially dependent and do not participate in symmetry transforms.

---

## 6. Validation Rules (Additive)

The following validation rules are added in v0.6:

| ID   | Condition | Error Type |
|------|----------|------------|
| V37  | Duplicate material IDs | ValidationError |
| V38  | Primitive references unknown material ID | ValidationError |
| V39  | `base_color` length ≠ 4 | ValidationError |
| V40  | Any `base_color` component outside `[0.0, 1.0]` | ValidationError |
| V41  | Primitives in the same mesh do not share the exact same material reference (or lack thereof) | ValidationError |
| V42  | Material ID collision or unresolved reference during import resolution | ValidationError |

### Parse vs Validation Notes

- Missing `base_color` or wrong type is a **ParseError** (schema enforcement, consistent with V33/V34)
- Length and range checks occur **post-parse** and are ValidationErrors as defined above

---

## 7. Determinism Guarantees

Materials in v0.6:

- MUST NOT affect vertex counts, ordering, or skinning
- MUST NOT affect canonicalization rules
- MUST NOT affect numeric evaluation pipelines

Material data is declarative and does not participate in floating-point computation.

---

## 8. glTF Export (Normative)

When exporting to glTF 2.0:

- `base_color` MUST be exported as `pbrMetallicRoughness.baseColorFactor`
- `metallicFactor` MUST be `0.0`
- `roughnessFactor` MUST be `1.0`

### Alpha Mode (Deterministic)

To preserve byte-identical GLB output:

- If `base_color[3] == 1.0`, `alphaMode` MUST be `"OPAQUE"`
- Otherwise, `alphaMode` MUST be `"BLEND"`
- `alphaCutoff` MUST be omitted
- `doubleSided` MUST be `false`

### Numeric Serialization

When serializing `baseColorFactor` into the glTF JSON:

1. Values MUST be computed as **IEEE 754 float32**
2. Values MUST be written using a fixed decimal format with **exactly six digits after the decimal point**, using round-half-even rounding

Example:

```json
"baseColorFactor": [1.000000, 0.300000, 0.666667, 1.000000]
```

This rule ensures cross-platform string identity.

---

## 9. Import Namespacing for Materials (Normative)

Imported assets introduce a namespace for their materials, consistent with existing import resolution rules.

- Materials defined in an imported asset are referenced as:
  - `<import_id>.<material_id>`
- Materials defined locally are referenced as:
  - `<material_id>`

Material references MUST resolve unambiguously. Failure to resolve a material reference, or a collision caused by ambiguous resolution, is a **ValidationError** (V42).

---

## 10. Conformance Suite Additions (Normative)

Rigy v0.6 extends the normative conformance suite with material-related tests.

### New Test Category

**O. Materials**

Required fixtures:

1. **O01 — minimal_material**  
   Single mesh, single primitive, material defined and referenced

2. **O02 — material_with_skinning**  
   Skinned mesh with a valid material

3. **O03 — invalid_material_reference**  
   Primitive references unknown material ID (expected error: V38)

Conformance tests do **not** compare rendered appearance.

---

## 11. Versioning

A v0.6-conforming parser:

- MUST accept `version` values `"0.1"` through `"0.6"`
- MUST reject major versions ≥ 1
- MUST support all features from v0.1–v0.6 cumulatively

---

## 12. Summary

Rigy v0.6 adds:

- Named solid-color materials
- Linear RGBA with alpha coverage
- Deterministic mesh-safe material assignment
- Deterministic glTF material export rules

It does so without expanding the evaluation model or weakening strict schema enforcement.

> **Materials in v0.6 are data, not behavior.**

