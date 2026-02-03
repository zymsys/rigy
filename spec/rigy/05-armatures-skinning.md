# 5. Armatures and Skinning

## 5.1 Influence Resolution Order (Normative)

For a given vertex, influences are resolved in the following priority (last wins):

1. **Default binding** — rigidly bound to the armature root bone (weight 1.0)
2. **Per-primitive weights** — from `bindings[].weights[].bones`
3. **External weight file** — from `weight_maps[].source`
4. **Gradients** — from `weight_maps[].gradients`, in declaration order
5. **Overrides** — from `weight_maps[].overrides`, in declaration order

At each stage, the new influences **fully replace** the previous ones for the affected vertices. There is no additive blending between stages.

---

## 5.2 Canonicalization Rules (Normative)

These rules apply **before** output generation and are **normative**.

### Vertex Ordering

Vertices MUST follow the canonical tessellation order defined by the `v0_1_default` profile. Primitives are tessellated in YAML declaration order and merged sequentially into a single vertex buffer per mesh.

### Influence Sorting

For each vertex, the influence list MUST be sorted using a three-part key:

1. **Primary:** weight, descending (largest first)
2. **Secondary:** `bone_id` string, ascending (lexicographic)
3. **Tertiary:** bone index (position in armature's bones list), ascending

The tertiary key is a defensive tiebreaker. Since bone IDs are unique within an armature (V04), the tertiary key is never reached in valid input, but MUST be applied for implementation correctness.

**String ordering rule (normative):**

When comparing `bone_id` strings for sorting (secondary key), implementations MUST:

* Treat `bone_id` as UTF-8 encoded text
* Compare strings by **bytewise lexicographic ordering of UTF-8 encoded bytes**
* MUST NOT apply locale-specific collation, Unicode normalization, or case folding

Invalid UTF-8 `bone_id` values are a hard error (ValidationError).

### Influence Capping and Normalization

After sorting:

1. Retain only the first 4 influences (discard the rest)
2. Compute `total_w = sum of retained weights`
3. If `total_w > 0`: divide each retained weight by `total_w`
4. If `total_w == 0`: replace the entire influence list with `[(root_bone_index, 1.0)]`

### Influence Padding

After capping and normalization, if fewer than 4 influences remain, pad with `(joint_index=0, weight=0.0)` until exactly 4 slots are filled. The result is always a 4-element JOINTS_0 and 4-element WEIGHTS_0 per vertex.

### Gradient Interpolation Formula

Gradient evaluation for a vertex at position `p` along axis `a` with range `[r0, r1]`:

```
t = clamp((p[a] - r0) / (r1 - r0), 0.0, 1.0)
```

For each bone `b` present in the union of `from` and `to` bone sets:

```
w_b = w_from_b * (1.0 - t) + w_to_b * t
```

where `w_from_b` and `w_to_b` default to 0.0 if bone `b` is not listed in the respective set. Bones with `w_b > 0` are retained; bones with `w_b == 0` are discarded.

The formula `w_from * (1.0 - t) + w_to * t` is **normative**. The algebraically equivalent form `w_from + t * (w_to - w_from)` produces different IEEE 754 results and MUST NOT be used.

---

**End of Chapter 5**
