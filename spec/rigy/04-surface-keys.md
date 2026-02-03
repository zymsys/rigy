# 4. Surface Keys

*Introduced in v0.9.*

## 4.1 Definition

A **surface key** is a canonical identifier for a bounded surface patch produced by a primitive's base topology.

A surface is:

- **Intrinsic**: derived from the primitive's definition
- **Bounded**: corresponds to a finite set of triangles
- **Concrete**: directly tied to generated mesh topology
- **Exclusive**: every generated triangle belongs to exactly one surface (when the primitive defines surfaces)

Surfaces are defined by **provenance**: which base patch produced a given triangle.

---

## 4.2 Normative Rules

1. A primitive **MAY** define a list of canonical surface keys.
2. If a primitive defines surface keys:
   - Tessellation **MUST** assign every generated triangle to exactly one surface key.
   - Surface assignment **MUST** be deterministic.
3. A triangle **MUST NOT** belong to more than one surface.
4. Surface keys **MUST NOT** overlap.
5. Surface keys are metadata only in v0.9+ and do not alter geometry.

---

## 4.3 Scope

- `box` **MUST** define surface keys: `+x`, `-x`, `+y`, `-y`, `+z`, `-z`
  Each key corresponds to the face whose outward normal points in the named axis direction.
- `wedge` **MUST** define surface keys: `-z`, `-x`, `slope`, `+y`, `-y`
  See [Chapter 3](03-primitives.md) for surface descriptions.
- All other primitives (e.g., `sphere`, `cylinder`, `capsule`) have **no surface keys** as of v0.11.

Implementations **MUST NOT** treat "no surface keys" as an error. The absence of surface keys means "no surface provenance is defined for this primitive in this spec version."

---

## 4.4 Implementation Invariants (Non-User-Facing)

The following conditions indicate a non-conforming implementation (or a bug), not invalid YAML input:

| ID | Condition |
|----|----------|
| I90 | Primitive defines surface keys but tessellation does not assign all triangles |
| I91 | Triangle assigned to more than one surface |
| I92 | Unknown surface key referenced internally |

---

**End of Chapter 4**
