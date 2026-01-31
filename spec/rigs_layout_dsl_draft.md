# Rigs — RigSpec Scene (Draft)

**Status:** draft / exploratory  
**Goal:** provide a very simple, text-first way for artists to assemble scenes and composites from reusable Rigy assets.

**Pronunciation:** **Rigs** = “RIGS”

Rigs is intentionally constrained:
- No arbitrary math or scripting
- No freeform transforms by default
- Deterministic compilation
- Friendly units for layout

Rigs builds on:
- **Rigy** (`*.rigy.yaml`) for asset definitions
- **Ricy** (`*.ricy.yaml`) for optional contracts/interfaces (slot/mount definitions)

---

## Core idea

A Rigs file:
1) imports Rigy assets
2) chooses a **base** (root) asset
3) instantiates children by snapping a child **mount** to a parent **slot**
4) optionally applies small, human-friendly adjustments like **nudge** and **rotate**

---

## Imports

```yaml
imports:
  room: parts/room.rigy.yaml
  coffee_table: parts/coffee_table.rigy.yaml
  sofa: parts/sofa.rigy.yaml
  vase: parts/vase.rigy.yaml
```

Imports introduce namespaces (e.g., `room`, `sofa`) for readability and tooling.

---

## Scene tree

```yaml
scene:
  base: room
  children:
    - id: table
      base: coffee_table
      place:
        slot: floor_center
        mount: floor_mount
      children:
        - id: vase_on_table
          base: vase
          place:
            slot: top_center
            mount: base_mount
    - id: sofa
      base: sofa
      place:
        slot: back_left_corner
        mount: floor_mount
```

- `scene.base` establishes the root instance (the room).
- `children` is a nested tree: *things inside things*.

---

## Slots and mounts

- A **slot** is an attachment target on the parent (e.g., `floor_center`, `top_center`).
- A **mount** is an attachment origin on the child (e.g., `floor_mount`, `base_mount`).

Slots/mounts are expected to be backed by **frame3** anchor sets (see below). They can be described:
- implicitly (conventions in the Rigy asset), or
- explicitly via a Ricy contract.

### Contract example (Ricy)

```yaml
contract_version: "0.1"
name: RoomContract
slots:
  floor_center: [floor_a, floor_b, floor_c]
  back_left_corner: [bl_a, bl_b, bl_c]
```

```yaml
contract_version: "0.1"
name: TableContract
mounts:
  floor_mount: [fm_a, fm_b, fm_c]
slots:
  top_center: [top_a, top_b, top_c]
```

---

## Placement adjustments

### Nudge

Nudge is an optional, small translation applied **in the local slot frame**.

```yaml
place:
  slot: floor_center
  mount: floor_mount
  nudge:
    north: 30cm
    east: 10cm
    up: 0
```

- `north/east/up` are axes of the slot frame (see frame3 convention).
- Units are friendly: `cm`, `m`, `in`, `ft` (compiled to meters internally).

### Rotate

Rotate is an optional orientation adjustment (artist-friendly).

```yaml
place:
  slot: back_left_corner
  mount: floor_mount
  rotate: 90deg
```

Planned accepted forms (TBD):
- degrees: `0deg`, `90deg`, `180deg`, `270deg`
- keywords: `left`, `right`, `back`, `front`

Rotation applies around the slot frame’s **up** axis.

---

## Frame3 convention (shared with Rigy composition)

Slots and mounts are defined using three anchors `[p1, p2, p3]`:

- `p1` = origin
- `x̂ = normalize(p2 − p1)`
- `t = (p3 − p1)`
- `ẑ = normalize(x̂ × t)` (right-handed)
- `ŷ = ẑ × x̂`

Constraints:
- points must be non-collinear
- `distance(p1,p2) > ε`
- `|x̂ × t| > ε`

---

## Compiler intent

A Rigs compiler should be able to:
- produce a flattened Rigy spec
- or export directly to glTF scene nodes

Rigs is designed to support live-preview IDE workflows (incremental rebuild, stable IDs, deterministic output).

---

## Open questions (future refinement)

- Naming conventions: `slot`/`mount` vs `position` presets
- Defaults: when can `mount` be omitted?
- Collision/overlap handling: do we support “push away” behaviors or keep manual nudges only?
- Variants: simple `variant: oak` or `style: modern` selection for assets
