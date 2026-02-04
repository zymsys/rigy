# Rigy Compiler Feature: Expanded YAML Emission

*Status: Compiler feature (non-language, non-normative)*
*Applies to: Rigy v0.10+*

## 1. Purpose

The Rigy compiler MAY provide a mode that emits the **expanded (preprocessed) Rigy YAML document** used internally for validation and export.

This feature exists to support debugging, inspection, and LLM-assisted authoring.
It is **observational only** and MUST NOT affect validation behavior or GLB output bytes.

---

## 2. Pipeline Boundary (Normative for This Feature)

The emitted YAML document MUST correspond exactly to the internal document state:

* **After preprocessing steps**:

  1. YAML load with duplicate key detection
  2. `repeat` macro expansion
  3. `params` substitution
  4. `aabb` conversion
  5. `box_decompose` macro expansion
* **Before schema validation and semantic validation**

In other words, the emitted YAML is the **input to schema validation**.

---

## 3. Emitted Document Invariants

The expanded YAML MUST satisfy all post-preprocessing invariants defined in Chapter 10 of the Rigy specification, including:

* MUST NOT contain:

  * `repeat` blocks
  * `params`
  * `$param` tokens
  * `${...}` tokens
  * `aabb`
  * `box_decompose`
  * `macro:` keys of any kind
* All identifiers reflect their final, collision-checked values
* All lists preserve their canonical order (e.g., meshes, primitives)

The expanded YAML is a **conceptual Rigy document**, but is **not** a new interchange format.

---

## 4. Rotation Canonicalization (LLM-Friendly)

For the purposes of expanded YAML emission:

* If a transform has any rotation:

  * The compiler MUST emit `transform.rotation_degrees`
  * The compiler MUST NOT emit `transform.rotation_euler`
* If the authored document used radians (`rotation_euler`), the compiler MUST convert to degrees.
* Angles MUST be emitted as-is after conversion:

  * No clamping
  * No normalization
  * No modulo wrapping

If a transform has no rotation, no rotation field is emitted.

> Rationale: degrees minimize mental mapping for humans and language models.

---

## 5. Comment Preservation and Provenance

### 5.1 Author Comments

By default, the compiler MUST NOT strip author-provided YAML comments when emitting expanded YAML.

* Comments attached to nodes that survive preprocessing SHOULD be preserved.
* If a node is replaced during preprocessing (e.g., a macro item), its comments MAY be attached to the first generated replacement node (best effort).

This requires use of a YAML parser/emitter capable of round-tripping comments.

### 5.2 Provenance Comments (Required)

The compiler MUST add **synthetic provenance comments** to generated or transformed nodes to explain their origin.

Examples (illustrative, not exhaustive):

* `repeat` expansion:

  ```yaml
  - id: picket3  # from repeat: meshes[0].primitives as=i index=3
  ```
* `params` substitution:

  ```yaml
  radius: 0.05  # was $leg_radius
  ```
* `aabb` conversion:

  ```yaml
  dimensions: { x: 4.0, y: 0.1, z: 3.0 }  # derived from aabb(min,max)
  ```
* `box_decompose`:

  ```yaml
  - id: south_wall_gap_0  # from box_decompose:south_wall segment=gap_0
  ```

These comments are **non-semantic** and MUST NOT affect validation or export.

---

## 6. CLI Interface

### 6.1 Flags

* `--emit-expanded-yaml <path | ->`

  * Emits the expanded YAML document
  * `-` writes to stdout

* `--emit-on-error`

  * If specified, emit expanded YAML **after preprocessing completes**, even if schema or semantic validation fails
  * Expanded YAML MUST NOT be emitted if preprocessing itself fails (e.g., duplicate YAML keys)

* `--emit-comments=[keep|drop|provenance]` (optional)

  * `keep` (default): preserve author comments and add provenance comments
  * `drop`: emit no comments
  * `provenance`: emit only synthetic provenance comments

### 6.2 Success and Failure Semantics

* Without `--emit-on-error`:

  * Expanded YAML is emitted only if the compile succeeds
* With `--emit-on-error`:

  * Expanded YAML is emitted if preprocessing succeeds, regardless of later validation errors

---

## 7. Determinism and Scope

* Emitting expanded YAML MUST NOT change:

  * Validation results
  * Error codes
  * GLB output bytes
* Formatting and comments are **non-normative** and do not participate in Rigy determinism.
* The expanded YAML is an **inspection artifact**, not a second canonical serialization and not guaranteed to round-trip.

---

## 8. Summary

This feature exposes the **conceptual post-preprocessing Rigy document** already defined by the specification, without changing the language, semantics, or determinism guarantees.

It exists to make Rigy:

* debuggable by humans
* inspectable by tools
* self-checkable by language models
