# 6. Weight Maps

Weight maps provide per-vertex control over skinning influences, enabling smooth deformation across bone boundaries.

## 6.1 Weight Map Sources

Weight maps can be specified through three mechanisms:

### Gradients

Gradients interpolate bone influences along an axis:

```yaml
weight_maps:
  - primitive_id: upper_arm
    gradients:
      - axis: y
        range: [0.88, 1.02]
        from:
          - bone_id: elbow
            weight: 1.0
        to:
          - bone_id: shoulder
            weight: 1.0
```

### Overrides

Overrides set explicit per-vertex influences:

```yaml
weight_maps:
  - primitive_id: forearm
    overrides:
      - vertex_index: 42
        bones:
          - bone_id: wrist
            weight: 0.8
          - bone_id: elbow
            weight: 0.2
```

### External Sources

External JSON files can provide weight data:

```yaml
weight_maps:
  - primitive_id: body
    source: weights/body_weights.json
```

---

## 6.2 Resolution Order

See [Chapter 5](05-armatures-skinning.md) for the complete influence resolution order. Weight maps participate in layers 3-5:

1. Default binding
2. Per-primitive weights
3. **External weight file** (from `source`)
4. **Gradients** (in declaration order)
5. **Overrides** (in declaration order)

---

## 6.3 Gradient Semantics

A gradient defines a linear interpolation of bone weights along a spatial axis.

**Required fields:**

- `axis`: One of `x`, `y`, or `z`
- `range`: `[from_value, to_value]` defining the interpolation extent
- `from`: Bone weights at `range[0]`
- `to`: Bone weights at `range[1]`

**Interpolation:**

For a vertex at position `p`:

```
t = clamp((p[axis] - range[0]) / (range[1] - range[0]), 0.0, 1.0)
weight = from_weight * (1.0 - t) + to_weight * t
```

---

## 6.4 Override Semantics

Overrides replace all influences for specific vertices.

**Required fields:**

- `vertex_index`: Index into the primitive's vertex buffer
- `bones`: List of `{bone_id, weight}` pairs

Vertex indices are zero-based and primitive-local. The vertex index must be valid for the primitive's tessellation (V19).

---

## 6.5 External Weight File Format

External weight files use JSON format:

```json
{
  "primitive_id": "body",
  "vertex_count": 858,
  "weights": [
    {
      "vertex_index": 0,
      "bones": [
        {"bone_id": "spine", "weight": 0.7},
        {"bone_id": "root", "weight": 0.3}
      ]
    }
  ]
}
```

**Validation:**

- File must exist and be valid JSON (V20)
- `vertex_count` must match the primitive's actual vertex count (V21)
- `primitive_id` must match the referencing weight map (V22)

---

## 6.6 Weight Validation

| ID | Check |
|----|-------|
| V14 | Weight map references unknown primitive |
| V15 | Gradient `bone_id` references unknown bone |
| V16 | Override `bone_id` references unknown bone |
| V17 | Gradient weight value outside [0.0, 1.0] |
| V18 | Override weight value outside [0.0, 1.0] |
| V19 | Override vertex index out of bounds |
| V20 | External weight file not found or malformed JSON |
| V21 | External weight file `vertex_count` mismatch |
| V22 | External weight file `primitive_id` mismatch |
| V23 | Weight map has none of `gradients`, `overrides`, or `source` |

---

**End of Chapter 6**
