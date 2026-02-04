# 15. Versioning

## 15.1 Version String Format

Rigy versions use `MAJOR.MINOR` format (e.g., `"0.11"`). While `MAJOR` is 0, the project is pre-1.0 and minor versions may introduce breaking changes.

---

## 15.2 Parser Compatibility

A v0.12 conforming parser:

* MUST accept `version` values `"0.1"`, `"0.2"`, `"0.3"`, `"0.4"`, `"0.5"`, `"0.6"`, `"0.7"`, `"0.8"`, `"0.9"`, `"0.10"`, `"0.11"`, and `"0.12"`
* MUST reject `version` with major version >= 1
* SHOULD emit a warning for minor versions > 12 within major version 0

---

## 15.3 Binary Output Authority and Bug Correction

### Canonical Outputs Are Authoritative — Until Proven Wrong

Canonical binary outputs in the conformance suite are **authoritative** for the corresponding spec version and suite revision.

However, this authority is **conditional**, not absolute.

### Bug Discovery and Correction Policy

Rigy explicitly rejects *bug-for-bug compatibility*.

If a bug is discovered such that:

* The spec text is incorrect, ambiguous, or incomplete, **or**
* The canonical output does not match the intended semantics of the spec

Then:

1. The spec text MUST be corrected
2. The conformance outputs MUST be regenerated
3. The `suite_revision` in the manifest MUST be incremented
4. The previous outputs are declared **non-canonical**
5. Determinism guarantees apply **only forward**, from the corrected suite revision

This may cause different outputs for the same input across suite revisions. This is **intentional and acceptable**.

### No Legacy Output Preservation

Rigy explicitly forbids:

* Preserving incorrect outputs for compatibility
* Encoding historical quirks as normative behavior
* Adding special-case logic to reproduce bugs

Once corrected, **incorrect output belongs to the past**.

---

## 15.4 Suite Revision Numbering

Within a spec version, conformance suite corrections are tracked by `suite_revision` (integer, starting at 1). This allows distinguishing "passes the original suite" from "passes the corrected suite."

---

## 15.5 Trust Properties

* Determinism is guaranteed **within a version and suite revision**
* Corrections may invalidate earlier outputs
* Version numbers are semantic contracts, not cosmetic labels

---

## 15.6 Extension Points

### What May Be Extended

Future Rigy versions MAY add:

* New geometric primitives (if universally useful, deterministic)
* New skinning solvers (if deterministic, conformance-testable)
* New UV generators (if applicable to multiple primitives)
* New preprocessing macros (if pure structural expansion)

All extensions MUST:

* Operate on the same authoring data (YAML schema)
* Obey the same determinism and conformance rules
* Introduce new canonical tests upon activation

### What Is Out of Scope

The following are **permanently out of scope**:

* Domain-specific primitives or macros (architectural, furniture, character)
* Implicit modeling (CSG, fillets, chamfers)
* Procedural generation (trees, terrain, scatter)
* Runtime variability (conditionals, randomness)
* Animation systems (keyframes, graphs, IK)

See [Section 2.3](02-fundamentals.md#23-scope-boundary) for design rationale.

---

## 15.7 Summary

Rigy v0.12 encompasses all features from v0.1 through v0.12:

* **Geometric primitives and armatures** with deterministic tessellation (v0.1)
* **Composition**: anchors, imports, instances, attach3, contracts (v0.2)
* **Per-vertex weight maps**: gradients, overrides, external sources (v0.3)
* **Formalization**: normative conformance suite, exhaustive validation table V01-V34, determinism contract, float64 precision (v0.4)
* **Dual Quaternion Skinning**: DQS solver, per-binding solver selection, pose evaluation, baked GLB export (v0.5)
* **Solid-color materials**: named materials, linear RGBA, deterministic glTF material export (v0.6)
* **UV roles**: semantic UV indirection vocabulary, asset-declared UV intent, material-side UV role validation (v0.7)
* **Deterministic UV generation**: spec-level UV generators, `TEXCOORD_n` export, UV set declarations, conformance category P (v0.8)
* **Wedge primitive and surface keys**: right triangular prism, flat-shaded, canonical surface provenance for box and wedge (v0.9)
* **Preprocessing**: compile-time `params`, `repeat` macro, strict schema enforcement, duplicate YAML key detection (v0.10)
* **Authoring helpers**: AABB box syntax, `box_decompose` macro, semantic tags (v0.11)
* **Ergonomics**: numeric expressions, axis–angle rotations, per-primitive materials, `box_decompose.mesh` removal, AABB scope clarification (v0.12)

The specification maintains:

* Determinism as executable truth, verified by a normative conformance suite (categories A-S)
* An exhaustive validation table (V01-V78, F114-F116)
* Precise canonicalization rules for all serialization
* A principled escape hatch for correcting mistakes (suite revisions)
* A firm refusal to fossilize bugs

> **Bounded computation under strict quantization — same YAML, same GLB, byte-for-byte.**

---

**End of Chapter 15**
