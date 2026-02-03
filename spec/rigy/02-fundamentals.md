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

**End of Chapter 2**
