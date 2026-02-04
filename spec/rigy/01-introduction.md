# 1. Introduction

## 1.1 Goals

Rigy v0.12 is a **cumulative specification** encompassing all features introduced from v0.1 through v0.12.

### Relationship to Prior Versions

Rigy v0.12 is a **strict superset** of all prior versions. All features are retained:

* **v0.1** — Geometric primitives, armatures, per-primitive skinning, symmetry
* **v0.2** — Anchors, imports, instances, attach3, contracts (Ricy)
* **v0.3** — Per-vertex weight maps (gradients, overrides, external JSON sources)
* **v0.4** — Normative conformance suite, exhaustive validation table, determinism formalization, float64 intermediate precision, NaN/Infinity rejection
* **v0.5** — Dual Quaternion Skinning (DQS), per-binding solver selection, pose evaluation blocks, baked GLB export
* **v0.6** — Solid-color materials, deterministic material export
* **v0.7** — UV roles: semantic UV indirection vocabulary, asset-declared UV intent, material-side UV role validation
* **v0.8** — Deterministic UV generation: spec-level UV generators, `TEXCOORD_n` export, UV set declarations
* **v0.9** — Wedge primitive, primitive surface keys, version gating for new primitives
* **v0.10** — Preprocessing stage: compile-time `params`, `repeat` macro, strict schema enforcement, duplicate YAML key detection
* **v0.11** — AABB box syntax, `box_decompose` macro, semantic tags
* **v0.12** — Numeric expressions, axis–angle rotations, per-primitive materials, `box_decompose.mesh` removal, AABB scope clarification

### Roadmap Note

Future work may include corrective shapes, pose-space deformation, constraints, control rigs, and additional macros. These are not part of v0.12.

---

## 1.2 Non-Goals

### Scope Principle

Rigy is a **compile target for geometry**, not a domain modeling language. Features encoding domain knowledge (architectural, furniture, character-specific) belong in authoring tools that emit Rigy, not in Rigy itself. See [Section 2.3](02-fundamentals.md#23-scope-boundary) for rationale.

### Specific Exclusions

Rigy v0.12 explicitly does **not**:

* Add blendshapes, corrective shapes, or pose-space deformation
* Introduce IK systems, constraints, or control rigs
* Add animation graphs or timelines
* Introduce freeform transforms or scripting
* Change the tessellation profile or vertex counts for any existing primitive type
* Add texture images, samplers, shading models, or lighting semantics
* Add manual UV authoring, seam placement controls, island rotation or packing
* Add per-primitive UV sets
* Guarantee backward compatibility with incorrect outputs
* Introduce conditionals or control flow (bounded compile-time expressions are added in v0.12)
* Add geometry booleans / CSG
* Add implicit modeling operations (e.g., "cut hole")
* Introduce runtime variability

---

## 1.3 Migration

### Parser Compatibility

A v0.12 conforming parser:

* MUST accept `version` values `"0.1"` through `"0.12"`
* MUST reject `version` with major version >= 1
* SHOULD emit a warning for minor versions > 12 within major version 0

### From v0.11

All valid v0.11 documents remain valid v0.12 files.

v0.12 adds:

* Numeric expression scalars (`"=<expr>"`) for any numeric field, evaluated during preprocessing
* `rotation_axis_angle` and `rotation_quat` authoring forms
* All rotation forms canonicalized to `rotation_quat` in preprocessed output
* Mesh-level default `material` field, per-primitive material resolution
* Per-primitive glTF emission (each Rigy primitive → one glTF primitive)
* `box_decompose.mesh` field removed (implicit targeting)
* AABB scope clarified to box-only
* Version gating for all new features (V77)
* Validation rules V67–V78

### From v0.10

All valid v0.10 documents remain valid v0.11 files.

v0.11 adds:

* AABB box syntax (`aabb.min` / `aabb.max`) as an alternative to `dimensions` + `translation`
* `box_decompose` macro for deterministic wall segmentation
* `tags` field for semantic primitive tagging

### From v0.9

v0.10 added:

* Mandatory preprocessing stage
* Top-level `params` for compile-time constants
* `repeat` macro for structural expansion
* Strict schema enforcement everywhere
* Duplicate YAML mapping key detection
* Validation rules V56-V66

### From v0.8

v0.9 added:

* `wedge` primitive with canonical geometry
* Primitive surface keys for `box` and `wedge`
* Version gating: `type: "wedge"` requires `version >= "0.9"`

### From v0.7

v0.8 added:

* `uv_sets` mesh-level block with UV generator references
* UV generators producing `TEXCOORD_n` attributes in GLB output
* Validation rules V50-V55

### From v0.6

v0.7 added:

* UV roles: semantic vocabulary for texture coordinate intent
* `uv_roles` mesh-level declaration
* Material-side `uses_uv_roles` references
* Validation rules V43-V47

### From v0.5

v0.6 added:

* Optional `materials` table
* Optional per-primitive `material` references
* Validation rules V37-V42

### From v0.4

v0.5 added:

* `skinning_solver` promoted from reserved to active
* `poses` block for conformance testing
* Validation rules V35-V36

### From v0.3

v0.4 added:

* Non-finite numeric values (NaN, +/-Infinity) are a hard error (V32)
* All previously undefined behaviors are resolved

---

**End of Chapter 1**
