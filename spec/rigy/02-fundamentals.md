# 2. Fundamentals

## 2.1 Determinism Contract

Rigy maintains the following core contract:

> **For a given Rigy input and a given Rigy specification version, a conforming implementation MUST produce byte-identical output artifacts.**

### Superseding v0.1's Relaxation

v0.1 described determinism as "structural, not bit-identical floating-point." v0.3 strengthened this to byte-identical GLB. v0.4 **superseded** v0.1's relaxation. Byte-identical GLB output is the normative requirement for all conforming implementations, retroactive to v0.3.

### Intermediate Arithmetic Precision

Conforming implementations MUST perform intermediate arithmetic in at least IEEE 754 binary64 (float64) precision. Truncation to binary32 (float32) MUST occur only at the serialization boundary (when writing to the GLB binary buffer).

This ensures that two conforming implementations produce identical bytes, regardless of which programming language or library they use.

### DQS Determinism

To ensure conformance for Dual Quaternion Skinning:

* All intermediate calculations MUST use float64 precision.
* Quaternion sign selection MUST follow the hemisphere rule (see [Chapter 7](07-skinning-solvers.md)).
* Final vertex outputs MUST be converted to float32 using IEEE 754 round-to-nearest-even (the default rounding mode). Implementations MUST NOT use truncation or other rounding modes for this conversion.
* Algebraic reorderings that change IEEE results are prohibited in the reference evaluator.

### Material Determinism

Materials in v0.6+:

* MUST NOT affect vertex counts, ordering, or skinning
* MUST NOT affect canonicalization rules
* MUST NOT affect numeric evaluation pipelines

Material data is declarative and does not participate in floating-point computation.

### UV Determinism

UV generation in v0.8+:

* UV data MUST be treated as derived data, equivalent in status to vertex normals.
* A conforming implementation MUST produce byte-identical UV buffers for identical inputs.
* All intermediate UV calculations MUST use IEEE 754 float64 precision.
* Final UV coordinates MUST be serialized as float32.
* UV generation MUST NOT affect vertex ordering, counts, or skinning data.

### Preprocessing Determinism

Preprocessing in v0.10+:

* `params` substitution and `repeat` expansion MUST be deterministic.
* The expanded document MUST be identical regardless of implementation, given the same input.
* Preprocessing MUST NOT introduce floating-point computation; it operates on the YAML object model only.

### Scope of Determinism

* Determinism applies **only to correct behavior as defined by the spec**
* Outputs produced by incorrect behavior are **not protected**
* Tooling-only top-level blocks (currently `geometry_checks`) are non-semantic and MUST NOT affect deterministic output

---

## 2.2 Coordinate System and Units

```yaml
units: meters
coordinate_system:
  up: Y
  forward: -Z
  handedness: right
```

Rigy uses a right-handed coordinate system with **Y-up**, consistent with glTF 2.0.

Any v0.11 macro that needs a vertical base MUST use `base_y`.

---

## 2.3 Scope Boundary

Rigy is a **compile target**, not a domain modeling language.

### Design Principle

Rigy provides deterministic, geometry-level primitives that higher-level tools compose into domain-specific outputs. The specification excludes features encoding domain knowledge because:

1. **Domain specificity fractures interoperability.** A "gable roof" primitive useful in architecture is meaningless in character rigging.

2. **Domain logic belongs in domain tools.** An architectural CAD tool knows what a "gable" is. Rigy does not. The CAD tool emits explicit primitives that any Rigy implementation processes.

3. **Determinism requires simplicity.** Every Rigy feature must produce byte-identical output across implementations. Domain features introduce ambiguity and implementation variance.

### Out of Scope Categories

The following are **permanently out of scope**:

| Category | Examples | Rationale |
|----------|----------|-----------|
| Architectural helpers | `gable_fill`, `stair_run`, `wall_openings` | Domain-specific |
| Furniture helpers | `drawer_stack`, `shelf_unit` | Domain-specific |
| Character helpers | `finger_splay`, `face_rig` | Domain-specific |
| Procedural generators | `tree`, `terrain`, `scatter` | Require randomness |
| Implicit modeling | `fillet`, `chamfer`, `boolean` | Break determinism |
| Semantic shortcuts | `door`, `window`, `hinge` | Encode domain meaning |

### Recommended Pattern

Domain tools SHOULD:

1. Implement domain features internally
2. Expand them to Rigy primitives (box, sphere, cylinder, capsule, wedge)
3. Emit standard Rigy YAML
4. Use `tags` (v0.11) to preserve semantic intent

### Citing This Section

When rejecting out-of-scope feature requests:

> "Per Section 2.3, domain-specific helpers are out of scope. Rigy is a compile target; domain logic belongs in authoring tools that emit explicit primitives."

---

**End of Chapter 2**
