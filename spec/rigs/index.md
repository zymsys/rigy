# Rigs Specification v0.1

**Status:** Specification
**Theme:** Deterministic scene assembly via *slot-to-mount* snapping
**Scope:** A scene language that composes existing Rigy assets into a glTF 2.0 scene at export time

Rigs is intentionally constrained:
- No scripting / expressions
- No arbitrary transforms (only `rotate` + `nudge` as defined here)
- Deterministic compilation

Rigs builds on:
- **Rigy** (`*.rigy.yaml`) for asset geometry, anchors, materials, UVs, etc.
- **Ricy** (`*.ricy.yaml`) optionally, to name slot/mount triples (interfaces)

The key words MUST, MUST NOT, SHOULD, and MAY are to be interpreted as in RFC 2119.

---

## 1. Goals

A Rigs file MUST be able to:
1. Import Rigy assets under stable aliases
2. Choose a root ("base") asset instance
3. Instantiate child assets and place them by snapping a child **mount** frame onto a parent **slot** frame
4. Apply small artist-friendly adjustments:
   - `rotate`: discrete yaw rotations about the slot "up" axis
   - `nudge`: translation along the slot axes in friendly units

---

## 2. Non-goals (v0.1)

Rigs v0.1 does **not**:
- Define animation, physics, collision, constraints, or procedural layout
- Support general transforms (scale, arbitrary rotations, arbitrary translations)
- Define a reusable "instance reference" DAG model (instances form a strict tree)
- Flatten Rigy into a single "resolved Rigy" document (composition happens at glTF export time)

---

## 3. Document structure

A Rigs v0.1 document MUST have:

```yaml
rigs_version: "0.1"
imports: { ... }
scene: { ... }
```

Unknown top-level fields MUST be rejected (ParseError).

---

## 4. Imports

```yaml
imports:
  room: parts/room.rigy.yaml
  table: parts/coffee_table.rigy.yaml
  vase: parts/vase.rigy.yaml
```

Rules:
- `imports` is a mapping of `alias -> relative_or_absolute_path`.
- Import aliases MUST be unique.
- A `base` reference uses an alias from `imports`.

**Note:** Rigs does not define how Rigy file paths are resolved (cwd vs project root, etc.). An implementation MUST document its path resolution behavior.

---

## 5. Scene graph (tree)

```yaml
scene:
  base: room
  children:
    - id: table1
      base: table
      place:
        slot: { name: floor_center }
        mount: { name: floor_mount }
      children:
        - id: vase1
          base: vase
          place:
            slot: { name: top_center }
            mount: { name: base_mount }
```

Rules:
- `scene.base` MUST be an import alias.
- The scene is a **strict tree**: each child is nested under exactly one parent.
- Each child node MUST have:
  - `id` (unique within the entire scene tree)
  - `base` (an import alias)
  - `place` (a placement block)

---

## 6. Slots and mounts

A **slot** is an attachment target frame on the **parent** instance.
A **mount** is an attachment origin frame on the **child** instance.

In v0.1, both slots and mounts resolve to a **frame3** triple of **Rigy anchor IDs**: `[p1, p2, p3]`.

### 6.1 SlotRef and MountRef forms

A `slot` or `mount` reference MUST be one of:

#### A) Named reference (requires a contract)
```yaml
slot:  { name: floor_center }
mount: { name: floor_mount }
```

Resolution:
- The implementation MUST have a way to associate a **Ricy contract** with the Rigy asset.
- The contract MUST provide:
  - `slots.<name> = [anchor_id, anchor_id, anchor_id]` for slot names
  - `mounts.<name> = [anchor_id, anchor_id, anchor_id]` for mount names
- If `name` cannot be resolved, it is a ValidationError.

#### B) Explicit anchor triple (no contract required)
```yaml
slot:  { anchors: [floor_a, floor_b, floor_c] }
mount: { anchors: [fm_a, fm_b, fm_c] }
```

Resolution:
- `anchors` MUST contain exactly 3 distinct strings.
- Each anchor ID MUST exist in the referenced Rigy asset:
  - slot anchors in the **parent** asset
  - mount anchors in the **child** asset
- Missing anchors are a ValidationError.

**Rigs v0.1 does not define any implicit naming convention** (e.g., `_a/_b/_c` suffix rules). If you want named slots/mounts, use a contract.

---

## 7. Placement

```yaml
place:
  slot:  { name: floor_center }        # or { anchors: [...] }
  mount: { name: floor_mount }         # or { anchors: [...] }
  rotate: 90deg
  nudge:
    north: 30cm
    east:  10cm
    up:    0
```

Fields:
- `slot` (required)
- `mount` (required)
- `rotate` (optional, default `0deg`)
- `nudge` (optional, default all zero)

### 7.1 Rotate (discrete yaw)

`rotate` MUST be one of:

- `0deg`
- `90deg`
- `180deg`
- `270deg`

Semantics:
- Rotation is applied about the **slot frame's up axis**.
- Positive rotation is right-handed about that axis.

Any other value is a ParseError.

### 7.2 Nudge (translation in slot frame)

`nudge` components are distances with friendly units:

- `m`, `cm`, `in`, `ft`

Accepted examples:
- `0`
- `10cm`
- `0.25m`
- `2in`
- `1ft`

Conversions (normative):
- `1cm = 0.01m`
- `1in = 0.0254m`
- `1ft = 0.3048m`

Semantics:
- `north`, `east`, `up` are axes of the **slot frame**:
  - `east`  is +X of slot frame
  - `up`    is +Y of slot frame
  - `north` is +Z of slot frame
- Nudge is applied **in parent space** as:
  - `Tnudge = east*X + up*Y + north*Z`

---

## 8. frame3 construction (normative)

Slots and mounts are defined by three Rigy anchors `[p1, p2, p3]` (each anchor provides a 3D position).

Given positions:
- `P1`, `P2`, `P3`

Define:
- `origin = P1`
- `X = normalize(P2 - P1)`
- `T = (P3 - P1)`
- `Z = normalize(X x T)`   (right-handed)
- `Y = Z x X`

Constraints (ValidationError if violated):
- `distance(P1,P2) > epsilon`
- `|X x T| > epsilon`  (non-collinear)

Where `epsilon = 1e-9` in meters.

---

## 9. Placement transform math (normative)

Let:
- Parent slot frame: `(Os, Rs)` where `Os` is origin and `Rs` is a 3x3 basis with columns `(Xs, Ys, Zs)`
- Child mount frame: `(Om, Rm)` in child local space
- `Rrot` be the yaw rotation about `Ys` by `rotate`
- `Tnudge` as defined in 7.2

The child node transform in parent space is:

- `R = Rs * Rrot * inverse(Rm)`
- `T = (Os + Tnudge) - R * Om`

The child's world transform is parent_world * (R, T).

Determinism requirements:
- Implementations MUST compute intermediate math in float64.
- Implementations MUST use the same normalization and cross-product definitions as standard Euclidean linear algebra.
- Any platform-dependent "fast math" or reordering that changes IEEE results is prohibited.

---

## 10. Export to glTF 2.0 (composition at export time)

A conforming exporter MUST:
1. Load each imported Rigy asset
2. Compile each Rigy asset to glTF mesh content (per the Rigy version used by that asset)
3. Create glTF scene nodes representing the Rigs instance tree
4. Apply the placement transforms from Section 9 as node transforms
5. Emit a single glTF/glb containing:
   - all referenced meshes/materials/etc. required by the imported assets
   - one scene with nodes matching the Rigs tree

### 10.1 Node identity

- Each instance `id` MUST map to a glTF node name exactly equal to that `id`.
- The root node name SHOULD be `scene` unless the implementation provides a different stable convention.

---

## 11. Validation and errors

Rigs defines two high-level error categories:
- **ParseError** — YAML/schema failures (unknown fields, wrong types, invalid tokens)
- **ValidationError** — semantic violations (missing anchors, degenerate frames, unknown imports)

A conforming implementation MUST reject (ValidationError) for at least:
- unknown `scene.base` alias
- duplicate instance IDs anywhere in the tree
- missing `place.slot` or `place.mount`
- unresolved `name` slot/mount
- missing anchor IDs in `anchors: [...]`
- invalid frame3 (degenerate constraints in Section 8)

---

## 12. Examples

### 12.1 Contract-free explicit anchors

```yaml
rigs_version: "0.1"
imports:
  room: parts/room.rigy.yaml
  table: parts/coffee_table.rigy.yaml

scene:
  base: room
  children:
    - id: table1
      base: table
      place:
        slot:  { anchors: [floor_a, floor_b, floor_c] }
        mount: { anchors: [fm_a, fm_b, fm_c] }
        rotate: 90deg
        nudge: { north: 20cm, east: 0, up: 0 }
```

### 12.2 Contract-backed named slots/mounts

```yaml
rigs_version: "0.1"
imports:
  room: parts/room.rigy.yaml
  table: parts/coffee_table.rigy.yaml

scene:
  base: room
  children:
    - id: table1
      base: table
      place:
        slot:  { name: floor_center }
        mount: { name: floor_mount }
```

(Contract association is implementation-defined in v0.1, but the mapping data shape is as described in 6.1-A.)

---

**End of Rigs Specification v0.1**
