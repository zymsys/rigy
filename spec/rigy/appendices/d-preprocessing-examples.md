# Appendix D: Preprocessing Examples

## D.1 `params` Example

```yaml
version: "0.11"

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

**Expanded form:**

```yaml
version: "0.11"

meshes:
  - id: table
    primitives:
      - id: leg0
        type: capsule
        dimensions:
          radius: 0.05
          height: 0.7
```

---

## D.2 `repeat` Example

```yaml
version: "0.11"

meshes:
  - id: fence
    primitives:
      - repeat:
          count: 5
          as: i
          body:
            id: picket${i}
            type: box
            dimensions: { x: 0.02, y: 1.0, z: 0.02 }
            transform:
              translation: [${i}, 0, 0]
```

**Expanded form:**

```yaml
version: "0.11"

meshes:
  - id: fence
    primitives:
      - id: picket0
        type: box
        dimensions: { x: 0.02, y: 1.0, z: 0.02 }
        transform:
          translation: [0, 0, 0]
      - id: picket1
        type: box
        dimensions: { x: 0.02, y: 1.0, z: 0.02 }
        transform:
          translation: [1, 0, 0]
      - id: picket2
        type: box
        dimensions: { x: 0.02, y: 1.0, z: 0.02 }
        transform:
          translation: [2, 0, 0]
      - id: picket3
        type: box
        dimensions: { x: 0.02, y: 1.0, z: 0.02 }
        transform:
          translation: [3, 0, 0]
      - id: picket4
        type: box
        dimensions: { x: 0.02, y: 1.0, z: 0.02 }
        transform:
          translation: [4, 0, 0]
```

---

## D.3 AABB Box Syntax Example (v0.11)

```yaml
version: "0.11"

meshes:
  - id: room
    primitives:
      - id: floor
        type: box
        aabb:
          min: [0, 0, 0]
          max: [4, 0.1, 3]
```

**Expanded form:**

```yaml
version: "0.11"

meshes:
  - id: room
    primitives:
      - id: floor
        type: box
        dimensions:
          x: 4.0
          y: 0.1
          z: 3.0
        transform:
          translation: [2.0, 0.05, 1.5]
```

---

## D.4 `box_decompose` Example (v0.11)

### Axis and Offset Relationship

```
  Top-down view (looking down Y axis)

  axis: x                      axis: z
  =======                      =======

  Z ^                          Z ^
    |   wall spans X             |   +---+ wall spans Z
    |   +-----------+            |   |   |
    |   |           |            |   +---+
    +---|-- offset -|---> X      +----offset----> X
        +-----------+                 (X displacement)
        (Z displacement)
```

### Full Example

```yaml
version: "0.11"

materials:
  wall_mat:
    base_color: [0.9, 0.85, 0.8, 1.0]

meshes:
  - id: walls
    primitives:
      - macro: box_decompose
        id: south_wall
        mesh: walls
        material: wall_mat
        surface: exterior

        axis: x
        span: [0.0, 4.0]
        base_y: 0.0
        height: 2.5

        thickness: 0.2
        offset: 0.0

        cutouts:
          - id: door
            span: [1.5, 2.5]
            bottom: 0.0
            top: 2.1
```

**Expanded form (conceptual):**

```yaml
version: "0.11"

materials:
  wall_mat:
    base_color: [0.9, 0.85, 0.8, 1.0]

meshes:
  - id: walls
    primitives:
      # Gap before door
      - id: south_wall_gap_0
        type: box
        material: wall_mat
        aabb:
          min: [0.0, 0.0, 0.0]
          max: [1.5, 2.5, 0.2]
        surface: exterior

      # Above door
      - id: south_wall_door_above
        type: box
        material: wall_mat
        aabb:
          min: [1.5, 2.1, 0.0]
          max: [2.5, 2.5, 0.2]
        surface: exterior

      # Gap after door
      - id: south_wall_gap_1
        type: box
        material: wall_mat
        aabb:
          min: [2.5, 0.0, 0.0]
          max: [4.0, 2.5, 0.2]
        surface: exterior
```

---

## D.5 Semantic Tags Example (v0.11)

```yaml
version: "0.11"

meshes:
  - id: house
    primitives:
      - id: exterior_wall_south
        type: box
        dimensions: { x: 4.0, y: 2.5, z: 0.2 }
        tags: [wall, exterior, load_bearing]
```

**glTF export:**

```json
{
  "primitives": [{
    "extras": {
      "rigy_tags": ["wall", "exterior", "load_bearing"]
    }
  }]
}
```

---

**End of Appendix D**
