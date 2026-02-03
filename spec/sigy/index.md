# Sigy Specification v0.1 (Draft)

**Status:** Draft / exploratory
**Theme:** Permissive sketching -> structured compilation
**Scope:** Authoring-time spatial intent for buildings and interiors, compiled into Rigy

---

## 1. Purpose

**Sigy** is a *sketch language* for authoring spatial structures (e.g. buildings, rooms, openings, placement intent) in a **human-friendly, underspecified** way.

Sigy is **not** a runtime format and **not** a deterministic interchange format.

Instead, Sigy exists to be:

```
Sigy  ->  Rigy  ->  glTF / GLB
(sketch)   (contract)   (artifact)
```

Sigy prioritizes:

* readability
* ease of iteration
* semantic intent over explicit geometry

Rigy prioritizes:

* determinism
* explicit geometry
* byte-identical outputs

Sigy deliberately makes tradeoffs Rigy must not.

---

## 2. Non-Goals

Sigy v0.1 explicitly does **not**:

* Guarantee deterministic output
* Define exact mesh topology
* Define tessellation profiles
* Define boolean geometry semantics
* Replace Rigy
* Define animation, physics, or interaction
* Require a canonical compiler

Multiple Sigy->Rigy compilers MAY exist and MAY produce different Rigy outputs from the same Sigy input.

This is intentional.

---

## 3. Versioning

A Sigy document MUST declare:

```yaml
sigy_version: "0.1"
```

Minor versions MAY introduce breaking changes.
Sigy has **no backward compatibility guarantees** prior to v1.0.

---

## 4. Coordinate System (Conventional, Not Normative)

Unless overridden by tooling, Sigy assumes:

* X = east (+)
* Y = north (+)
* Z = up (+)
* Origin = south-west corner of the footprint at floor level

This is a **convention**, not a contract.

---

## 5. Core Concepts

### 5.1 Sketch vs Contract

Sigy values *intent*:

> "There is a door centered on the south wall."

Rigy requires *explicit realization*:

> "This wall is split into three segments; the center segment is omitted."

Sigy MAY be ambiguous.
Rigy MUST NOT be.

---

## 6. Top-Level Structure

```yaml
sigy_version: "0.1"
units: m
house:
  ...
```

Unknown top-level keys SHOULD be ignored by tooling unless explicitly rejected.

---

## 7. House Object

Sigy v0.1 focuses on a single building-like structure.

```yaml
house:
  id: tempera_house
  name: "Tempera House"
```

`id` is required.
`name` is optional and informational.

---

## 8. Plan (2D Layout)

The **plan** describes a 2D footprint and room rectangles.

```yaml
plan:
  footprint: { width, depth }

  rooms:
    - id
      rect: { x, y, w, h }

  interior_walls: implied | explicit
```

### Semantics

* Coordinates are 2D (X/Y).
* Rooms MAY overlap (Sigy does not forbid this).
* `interior_walls: implied` allows tooling to infer walls from shared boundaries.

---

## 9. Shell (Vertical Structure)

```yaml
shell:
  wall_height
  wall_thickness
  floor_thickness
  ceiling: true | false

  roof:
    type: gable | flat | shed | unknown
    ridge_axis: x | y
    overhang
    pitch_deg
    attic:
      exists: true | false
      accessible: true | false
```

### Notes

* Roof geometry is **intent only**.
* "Attic exists but inaccessible" has no required geometric interpretation.

---

## 10. Openings (Doors and Windows)

```yaml
openings:
  - id
    kind: door | window
    wall: north | south | east | west
    pos: center | { offset_from_left }
    width
    height
    sill
```

### Semantics

* Openings do **not** imply boolean subtraction.
* A compiler MAY:
  * segment walls
  * leave gaps
  * ignore openings entirely (for early passes)

Sigy does not care how you get there.

---

## 11. Anchors (Semantic Points)

Anchors declare **meaningful locations** that should survive compilation.

```yaml
anchors:
  - name
    kind: point
    at: { x, y, z }
```

Anchors MAY also be derived:

```yaml
derived_from_opening: front_door
```

Anchors are **semantic commitments**:

> "This point matters later."

---

## 12. Interfaces (Slots and Mounts — Intent Only)

Sigy introduces **interfaces** to mirror the Rigs mental model *without frame math*.

```yaml
interfaces:
  frame_span: 1.0

  slots:
    - name
      kind: frame
      base_point
      plane: floor | wall

  mounts:
    - name
      kind: frame
      intent: string
```

### Semantics

* Slots and mounts declare *attachment intent*, not transforms.
* A compiler MAY synthesize Rigy `frame3` anchors using a deterministic rule.
* Sigy itself defines **no snapping behavior**.

---

## 13. Furniture Placeholders (Optional)

```yaml
furniture:
  - id
    kind: placeholder
    room
    footprint
    place:
      slot
      mount
      rotate
      nudge
```

These are:

* not geometry
* not required
* purely layout intent

They exist to test whether the spatial model *feels usable*.

---

## 14. Compilation Relationship to Rigy

A Sigy->Rigy compiler typically:

1. Realizes floors, walls, roofs as Rigy primitives
2. Segments walls to accommodate openings (or cheats)
3. Converts anchors -> Rigy anchors
4. Converts interface frames -> anchor triples
5. Emits pure, explicit Rigy YAML

Rigy remains the **authoritative contract**.

---

## 15. Philosophy (Non-Normative)

Sigy exists because:

* Humans sketch before they specify
* Early rigidity kills exploration
* Under-specification is dangerous *only if it leaks downstream*

Sigy is the place where:

* ambiguity is allowed
* revision is cheap
* intent is captured early

Rigy is the place where:

* ambiguity is rejected
* revision is expensive
* intent is frozen into geometry

This separation is deliberate.

---

## 16. Example

See the canonical Sigy v0.1 example file (e.g., `tempera_house.sigy.yaml`). This file is expected to evolve alongside the spec.

---

## 17. Open Questions (v0.1)

* Should Sigy support multiple buildings?
* Should rooms imply doors automatically?
* Should interior walls ever be explicit by default?
* How much compiler opinion is too much?

These are intentionally unresolved.

---

**End of Sigy Specification v0.1 (Draft)**
