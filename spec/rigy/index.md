# Rigy Specification v0.12

**Status:** Specification
**Scope:** Cumulative specification covering all features from v0.1 through v0.12

The key words MUST, MUST NOT, SHOULD, SHALL, and MAY in this document are to be
interpreted as described in [RFC 2119](https://www.ietf.org/rfc/rfc2119.txt).

---

## Table of Contents

1. [Introduction](01-introduction.md) — Goals, non-goals, migration guide
2. [Fundamentals](02-fundamentals.md) — Determinism contract, coordinate system, units
3. [Primitives](03-primitives.md) — Box, sphere, cylinder, capsule, wedge tessellation
4. [Surface Keys](04-surface-keys.md) — Canonical surface identifiers for primitives
5. [Armatures and Skinning](05-armatures-skinning.md) — Bones, bindings, influence resolution
6. [Weight Maps](06-weight-maps.md) — Gradients, overrides, external sources
7. [Skinning Solvers](07-skinning-solvers.md) — LBS, DQS, pose evaluation
8. [Materials](08-materials.md) — Solid-color materials, base_color
9. [UV System](09-uv-system.md) — UV roles, sets, generators
10. [Preprocessing](10-preprocessing.md) — params, repeat, AABB, box_decompose, tags
11. [Symmetry](11-symmetry.md) — Mirror-X expansion
12. [Validation](12-validation.md) — Error model, V01-V78 table
13. [glTF Export](13-gltf-export.md) — Serialization, buffer layout
14. [Conformance](14-conformance.md) — Test suite, categories A-S
15. [Versioning](15-versioning.md) — Version format, trust model

### Appendices

- [A. Examples](appendices/a-examples.md) — Conformance test example
- [B. Fixtures](appendices/b-fixtures.md) — Normative YAML fixtures
- [C. UV Example](appendices/c-uv-example.md) — Complete UV example
- [D. Preprocessing Examples](appendices/d-preprocessing-examples.md) — params and repeat examples

---

## Quick Reference: Feature by Version

| Feature | Version |
|---------|---------|
| Geometric primitives, armatures, per-primitive skinning, symmetry | v0.1 |
| Anchors, imports, instances, attach3, contracts | v0.2 |
| Per-vertex weight maps (gradients, overrides, external sources) | v0.3 |
| Conformance suite, validation table, float64 precision | v0.4 |
| Dual Quaternion Skinning, poses, baked export | v0.5 |
| Solid-color materials | v0.6 |
| UV roles | v0.7 |
| UV generation, TEXCOORD_n export | v0.8 |
| Wedge primitive, surface keys | v0.9 |
| Preprocessing (params, repeat) | v0.10 |
| AABB box syntax, box_decompose, semantic tags | v0.11 |
| Expressions, axis-angle rotations, per-primitive materials | v0.12 |

---

## Overview

Rigy is a YAML-to-glTF compiler for rigged assemblies of geometric primitives. The compile pipeline is:

```
YAML → preprocess → parse → expand symmetry → validate → tessellate → skin → export GLB
```

For a given Rigy input and specification version, a conforming implementation MUST produce byte-identical output artifacts.

---

**End of Rigy Specification v0.12 Index**
