# 12. Validation and Error Model

## 12.1 Error Type Hierarchy

Rigy defines six normative error types. Conformance tests validate error **category**, not exact message text.

```
RigyError (base)
+-- ParseError          -- YAML parsing or schema deserialization
+-- ValidationError     -- Semantic rule violations
+-- TessellationError   -- Geometry generation failures
+-- ExportError         -- glTF/GLB assembly failures
+-- ContractError       -- Ricy contract violations
+-- CompositionError    -- Import, instance, or attach3 failures
```

---

## 12.2 Hard Errors (MUST reject)

A conforming implementation MUST fail and MUST NOT emit output for any of the following conditions.

| ID | Check | Error Type | Since |
|----|-------|-----------|-------|
| V01 | Duplicate mesh IDs | ValidationError | v0.1 |
| V02 | Duplicate primitive IDs within a mesh | ValidationError | v0.1 |
| V03 | Duplicate armature IDs | ValidationError | v0.1 |
| V04 | Duplicate bone IDs within an armature | ValidationError | v0.1 |
| V05 | Cyclic bone hierarchy | ValidationError | v0.1 |
| V06 | Zero-length bone (head = tail within epsilon = 1e-9) | ValidationError | v0.1 |
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
| V28 | ID collision across the global identifier namespace (`meshes[].id`, `armatures[].id`, `anchors[].id`, `instances[].id`, and `materials` keys) | ValidationError | v0.2 |
| V29 | attach3 `from` anchor not found in imported asset | ValidationError | v0.2 |
| V30 | attach3 `to` anchor not found in local anchors | ValidationError | v0.2 |
| V31 | Contract violation on imported asset | ContractError | v0.2 |
| V32 | NaN or +/-Infinity in any numeric field | ValidationError | v0.4 |
| V33 | Unknown fields in strict-mode schema | ParseError | v0.1 |
| V34 | Missing required fields in schema | ParseError | v0.1 |
| V35 | Non-rigid bone transform in DQS binding | ValidationError | v0.5 |
| V36 | Invalid pose quaternion (non-unit norm, NaN, or Infinity component) | ValidationError | v0.5 |
| V37 | Duplicate material IDs | ValidationError | v0.6 |
| V38 | Primitive references unknown material ID | ValidationError | v0.6 |
| V39 | `base_color` length != 4 | ValidationError | v0.6 |
| V40 | Any `base_color` component outside `[0.0, 1.0]` | ValidationError | v0.6 |
| V41 | Primitives in the same mesh do not share the same material reference. Enforced only when `version < "0.12"`. **NOT checked for `version >= "0.12"`.** | ValidationError | v0.6 |
| V42 | Material ID collision or unresolved reference during import resolution | ValidationError | v0.6 |
| V43 | `uv_roles` declares a role not in the v0.7 role vocabulary | ValidationError | v0.7 |
| V44 | Duplicate role key in `uv_roles` | ValidationError | v0.7 |
| V45 | `uv_roles.<role>.set` is not a valid UV set token | ValidationError | v0.7 |
| V46 | A material references a UV role not exposed by the target asset | ValidationError | v0.7 |
| V47 | `uses_uv_roles` contains a role not in the v0.7 role vocabulary | ValidationError | v0.7 |
| V50 | UV set declared without a generator | ValidationError | v0.8 |
| V51 | Generator not in v0.8 vocabulary | ValidationError | v0.8 |
| V52 | A UV set generator is not valid for every primitive type in the mesh | ValidationError | v0.8 |
| V53 | `uv_roles` declared but no `uv_sets` present | ValidationError | v0.8 |
| V54 | A `uv_role` references a UV set that is not declared | ValidationError | v0.8 |
| V55 | `uv_sets` contains a gap in indices | ValidationError | v0.8 |
| V56 | Duplicate YAML mapping key detected | ParseError | v0.10 |
| V57 | Unknown field encountered (strict schema) | ParseError | v0.10 |
| V58 | `params` contains non-scalar or invalid value | ParseError | v0.10 |
| V59 | `$param` references unknown parameter | ParseError | v0.10 |
| V60 | Invalid `$param` usage (not whole-scalar) | ParseError | v0.10 |
| V61 | Param type mismatch | ParseError | v0.10 |
| V62 | `repeat.count` invalid | ParseError | v0.10 |
| V63 | `repeat.as` invalid identifier | ParseError | v0.10 |
| V64 | Invalid `repeat` structure or placement | ParseError | v0.10 |
| V65 | Unresolved `${...}` token after preprocessing | ParseError | v0.10 |
| V66 | Identifier collision after preprocessing | ValidationError | v0.10 |
| V67 | Axis vector has length ≤ 1e-12 | ValidationError | v0.12 |
| V68 | Expression parse error (invalid grammar, token, function, or arity) | ValidationError | v0.12 |
| V69 | Expression references an unknown parameter | ValidationError | v0.12 |
| V70 | Expression evaluation produced a non-finite result | ValidationError | v0.12 |
| V71 | Expression domain error (e.g. `sqrt(x)` with `x < 0`) | ValidationError | v0.12 |
| V72 | Multiple rotation authoring forms specified | ValidationError | v0.12 |
| V73 | Non-finite axis / degrees / quaternion component | ValidationError | v0.12 |
| V74 | No material resolved for primitive (v0.12+) | ValidationError | v0.12 |
| V75 | Primitive references unknown material (v0.12+) | ValidationError | v0.12 |
| V76 | `box_decompose.mesh` does not match containing mesh ID | ValidationError | v0.12 |
| V77 | v0.12-only feature used under `version < "0.12"` | ValidationError | v0.12 |
| V78 | Quaternion has length ≤ 1e-12 (zero-length / invalid) | ValidationError | v0.12 |
| V79 | `implicit_surface` used with `version < "0.13"` | ValidationError | v0.13 |
| V80 | Invalid AABB: `max[i] <= min[i]` or non-finite | ValidationError | v0.13 |
| V81 | Invalid grid: `nx`, `ny`, or `nz` < 2 | ValidationError | v0.13 |
| V82 | Empty `ops` list | ValidationError | v0.13 |
| V83 | Unknown field type | ValidationError | v0.13 |
| V84 | Invalid field parameters (non-positive radius/strength/height) | ValidationError | v0.13 |
| V85 | Non-uniform scale on field operator transform | ValidationError | v0.13 |
| V86 | Grid exceeds max cell count (`nx*ny*nz > 2,000,000`) | ValidationError | v0.13 |
| V87 | Unknown extraction algorithm | ValidationError | v0.13 |
| F114 | `box_decompose` generated ID collision | ValidationError | v0.11 |
| F115 | `aabb` used with transform | ParseError | v0.11 |
| F116 | Invalid cutout ID in `box_decompose` | ParseError | v0.11 |

Exception: the tooling-only top-level key `geometry_checks` is allowed and is ignored by validation.

---

## 12.3 Soft Errors / Warnings (MUST warn, MAY continue)

Warnings MUST NOT affect output determinism. The output MUST be identical whether or not the warning is emitted.

| ID | Condition | Since |
|----|-----------|-------|
| W01 | Vertex has more than 4 joint influences (before capping) | v0.3 |
| W02 | Per-primitive weights and weight map both target the same primitive | v0.3 |
| W03 | Armature root bone head not at origin (convention) | v0.2 |

---

## 12.4 Previously Undefined Behavior (Now Resolved)

Rigy v0.4 removed all previously implicit undefined behavior. Any input condition not explicitly defined in this spec or prior specs is a **hard error**.

The following behaviors were previously underspecified and are now normatively defined:

| Condition | Resolution |
|-----------|-----------|
| All vertex weights are zero after influence resolution | Fall back to armature root bone, weight 1.0 |
| No bone in armature has `parent: none` | Use the first bone (index 0) as the root (note: in a finite bone set this implies a cycle, so V05 will typically reject first; this rule is a defensive fallback for root-detection logic) |
| Gradient `from` and `to` both yield zero weight for all bones at a vertex | Fall back to armature root bone, weight 1.0 |

---

**End of Chapter 12**
