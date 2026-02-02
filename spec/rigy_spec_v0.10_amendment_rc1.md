# Rigy Specification — v0.10 Amendment (RC1)

**Status:** Draft (Release Candidate 1)
**Applies to:** Rigy Specification v0.1–v0.9 (cumulative)
**Theme:** Authoring safety, repetition, and compile-time constants

This amendment introduces a mandatory preprocessing stage and three compile-time authoring features that reduce duplication and error rates without introducing scripting, expressions, or runtime variability.

---

## 1. Summary of Changes

Rigy v0.10 adds:

1. **Strict schema enforcement everywhere**
   Unknown keys are rejected globally.

2. **Top-level `params` (compile-time constants)**
   Scalar constants substituted deterministically before validation.

3. **`repeat` macro (pure structural expansion)**
   Deterministic duplication of list elements using an index token.

All features resolve fully **before schema validation** and do not alter runtime semantics.

---

## 2. Non-Goals (Normative)

v0.10 explicitly does **not** introduce:

* Expressions, arithmetic, or conditionals
* Scripting or control flow
* Runtime variability
* Geometry booleans / CSG
* Implicit modeling operations (e.g., “cut hole”)
* Changes to tessellation, deformation, UVs, or materials

---

## 3. Preprocessing Stage (New, Normative)

A Rigy v0.10 implementation MUST apply the following preprocessing steps **in this order**:

1. YAML load with duplicate mapping key detection
2. `repeat` macro expansion
3. `params` substitution
4. Schema validation (strict everywhere)
5. Semantic validation
6. Export

Stages 2–3 operate on the raw YAML object model (mappings, sequences, scalars).
Stages 4–6 operate on the schema-defined model.

The output of preprocessing MUST be a canonical Rigy document containing:

* no `repeat` blocks
* no `$param` tokens
* no unresolved `${…}` tokens

---

## 4. Duplicate YAML Mapping Keys (Clarified)

Duplicate YAML mapping keys MUST be detected **globally** and rejected.

This requirement applies to:

* Top-level mappings
* Nested objects
* Maps such as `materials`, `uv_roles`, etc.

Silently accepting “last key wins” behavior is non-conformant.

---

## 5. Strict Schema Enforcement (Expanded)

All objects defined by the Rigy schema MUST reject unknown keys.

This rule applies universally, including:

* Top-level document keys
* Meshes, primitives, armatures, bones
* Materials and material property maps
* UV role definitions
* Bindings and weight structures

No extension or vendor-specific keys are permitted unless explicitly defined by the specification.

---

## 6. `params` — Compile-Time Constants

### 6.1 Definition

A Rigy document MAY define a top-level `params` mapping:

```yaml
params:
  <param_id>: <scalar>
```

Where `<scalar>` MUST be one of:

* number (finite)
* string
* boolean

Lists and mappings are not permitted as param values.

### 6.2 Param Identifier Grammar (Normative)

A parameter identifier MUST match:

```
^[A-Za-z_][A-Za-z0-9_]*$
```

### 6.3 Param Reference Grammar (Normative)

A param reference is a **scalar string** whose entire value matches:

```
^\$[A-Za-z_][A-Za-z0-9_]*$
```

Only exact matches are substituted.

### 6.4 Substitution Rules

* `$param_id` replaces the entire scalar value
* Substitution is type-preserving
* Referencing an undeclared param is an error
* Param values are literal and are **not** further expanded

### 6.5 Prohibited Forms

The following are invalid in v0.10:

```yaml
radius: 2 * $r          # expressions not allowed
id: "leg_$r"            # string interpolation not allowed
dimensions: $dims       # non-scalar param
params:
  x: ${i}               # param indirection not allowed
```

### 6.6 Post-Preprocessing Rule

After preprocessing, the expanded document MUST NOT contain the key `params`.

---

## 7. `repeat` Macro — Pure Expansion

### 7.1 Purpose

`repeat` provides deterministic duplication of schema objects in list contexts without introducing logic or expressions.

### 7.2 Allowed Contexts (v0.10)

A `repeat` macro MAY appear only as a **list element** where a list of objects is expected, including:

* `meshes[].primitives[]`
* `armatures[].bones[]`
* `anchors[]`
* `bindings[]`
* `bindings[].weights[]`
* `bindings[].weight_maps[]`

`repeat` is not permitted inside mapping contexts (e.g., `materials`).

### 7.3 Recognition Rule (Normative)

A list element is a `repeat` macro **if and only if** it is a mapping with exactly one key:

```yaml
repeat
```

Any other use of a `repeat` key MUST be rejected.

### 7.4 Structure

```yaml
- repeat:
    count: <integer ≥ 0>
    as: <identifier>
    body: <object>
```

Rules:

* `count` MUST be an integer ≥ 0
* `as` MUST be a valid identifier
* `body` MUST be a single object
* `count: 0` expands to an empty sequence

### 7.5 Index Token Grammar (Normative)

An index token is a substring matching:

```
\$\{[A-Za-z_][A-Za-z0-9_]*\}
```

### 7.6 Substitution Semantics

Within a repeat expansion for `as: i`:

* `${i}` is substituted with the current zero-based index
* Substitution occurs during macro expansion only

Numeric vs string behavior:

| Input            | Output (i = 3)       |
| ---------------- | -------------------- |
| `"${i}"`         | `3` (number)         |
| `"picket${i}"`   | `"picket3"` (string) |
| `["${i}", 0, 0]` | `[3, 0, 0]`          |

### 7.7 Unresolved Tokens

Any `${…}` token remaining after preprocessing MUST be rejected.

---

## 8. Identifier Collisions After Expansion

After preprocessing, all identifier uniqueness rules apply.

Any identifier collision detected after preprocessing MUST be rejected with error code **V66**, regardless of whether the collision originated from a macro or manual duplication.

---

## 9. Error Codes (v0.10 Additions)

v0.9 is assumed to define errors through **V55**.

v0.10 adds:

| Code    | Condition                                     |
| ------- | --------------------------------------------- |
| **V56** | Duplicate YAML mapping key detected           |
| **V57** | Unknown field encountered (strict schema)     |
| **V58** | `params` contains non-scalar or invalid value |
| **V59** | `$param` references unknown parameter         |
| **V60** | Invalid `$param` usage (not whole-scalar)     |
| **V61** | Param type mismatch                           |
| **V62** | `repeat.count` invalid                        |
| **V63** | `repeat.as` invalid identifier                |
| **V64** | Invalid `repeat` structure or placement       |
| **V65** | Unresolved `${…}` token after preprocessing   |
| **V66** | Identifier collision after preprocessing      |

### 9.1 Error Class Boundaries (Normative)

* **ParseErrors:** V56, V58, V60, V62–V65
* **ValidationErrors:** V57, V59, V61, V66

---

## 10. Conformance Tests (v0.10)

A new conformance category MUST be added covering preprocessing.

### Positive Fixtures

* params substitution (scalar)
* repeat expansion (ordering and IDs)
* repeat + params combined
* equivalence with fully expanded literal file (byte-identical output)

### Negative Fixtures

* duplicate YAML keys (V56)
* unknown fields (V57)
* non-scalar param (V58)
* unknown param (V59)
* illegal param usage (V60)
* param type mismatch (V61)
* invalid repeat forms (V62–V64)
* unresolved index token (V65)
* ID collision post-expansion (V66)

---

## 11. Compatibility

All valid v0.9 documents remain valid **unless** they relied on:

* silently ignored unknown keys
* duplicate YAML mapping keys

Such documents are now correctly rejected.

---

## 12. Roadmap Note (Non-Normative)

With authoring duplication and safety addressed, subsequent probes (e.g., houses) should surface **true modeling gaps** rather than ergonomics issues.

A likely v0.11 exploration:

* **Openings macro (segmentation, not CSG)**
  Deterministic face subdivision for doors and windows.

---

## Appendix A — Minimal Examples

### A.1 `params`

```yaml
version: "0.10"

params:
  leg_radius: 0.05
  leg_height: 0.7

meshes:
  - id: table
    primitives:
      - id: leg0
        type: capsule
        dimensions:
          radius: $leg_radius
          height: $leg_height
```

### A.2 `repeat`

```yaml
version: "0.10"

meshes:
  - id: fence
    primitives:
      - repeat:
          count: 5
          as: i
          body:
            id: picket${i}
            type: box
            dimensions: { width: 0.02, height: 1.0, depth: 0.02 }
            transform:
              translation: [${i}, 0, 0]
```

