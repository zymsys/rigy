# 8. Materials

*Introduced in v0.6.*

## 8.1 Material Table

Rigy v0.6 introduced an optional top-level `materials` table.

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

---

## 8.2 `base_color` (Required)

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

---

## 8.3 Material References

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

---

## 8.4 Default Material

If no material is specified, the primitive implicitly uses:

```yaml
base_color: [1.0, 1.0, 1.0, 1.0]
```

This default intentionally aligns with the glTF 2.0 default `pbrMetallicRoughness.baseColorFactor`.

The default material is conceptual and MUST NOT require an explicit entry in `materials`.

---

## 8.5 Mesh-Level Material Constraint

Rigy exporters emit **one glTF primitive per Rigy mesh**, merging all Rigy primitives into a single draw call.

To preserve determinism and avoid exporter ambiguity:

> **All primitives within a single Rigy mesh MUST reference the same material ID, or all MUST omit the material field.**

Violation of this rule is a ValidationError (V41).

> **Note:** This rule is based on *material reference identity*, not effective color equivalence. A primitive omitting `material` is not equivalent to explicitly referencing a material whose `base_color` equals the default.

This restriction MAY be relaxed in a future version when per-primitive glTF emission is standardized.

---

## 8.6 Material UV Role References

Materials MAY reference UV roles symbolically:

```yaml
materials:
  cheese:
    base_color: [0.9, 0.8, 0.2, 1.0]
    uses_uv_roles:
      - radial
```

Validation rules:

* If a material references a UV role not exposed by the target asset, compilation MUST fail with a ValidationError (V46).
* `uses_uv_roles` entries MUST be from the UV role vocabulary (V47).
* In v0.7, referencing UV roles had no effect on export output.
* In v0.8+, referenced UV roles MUST resolve to declared UV sets with generators.
* Implementations MUST NOT attempt to infer or synthesize UV data from role references alone.

---

## 8.7 Import Namespacing for Materials

Imported assets introduce a namespace for their materials, consistent with existing import resolution rules.

* Materials defined in an imported asset are referenced as: `<import_id>.<material_id>`
* Materials defined locally are referenced as: `<material_id>`

Material references MUST resolve unambiguously. Failure to resolve a material reference, or a collision caused by ambiguous resolution, is a ValidationError (V42).

---

## 8.8 Validation

| ID | Check | Error Type |
|----|-------|-----------|
| V37 | Duplicate material IDs | ValidationError |
| V38 | Primitive references unknown material ID | ValidationError |
| V39 | `base_color` length != 4 | ValidationError |
| V40 | Any `base_color` component outside `[0.0, 1.0]` | ValidationError |
| V41 | Primitives in the same mesh do not share the exact same material reference | ValidationError |
| V42 | Material ID collision or unresolved reference during import resolution | ValidationError |

**Parse vs Validation Notes:**

- Missing `base_color` or wrong type is a **ParseError** (schema enforcement, consistent with V33/V34)
- Length and range checks occur **post-parse** and are ValidationErrors as defined above

---

**End of Chapter 8**
