# 13. glTF Export

## 13.1 Floating-Point Serialization

All vertex attributes (positions, normals) and skinning data (weights) written to GLB buffers MUST be serialized as **IEEE 754 little-endian float32** (`binary32`).

Joint indices MUST be serialized as **little-endian uint16**.

Triangle indices MUST be serialized as **little-endian uint32**.

Inverse bind matrices MUST be serialized as float32, in **column-major** order (the numpy row-major matrix is transposed before serialization).

UV coordinates MUST be serialized as **IEEE 754 little-endian float32** (`binary32`).

**Quaternion serialization:** Pose rotations are authored as `[w, x, y, z]` (scalar-first) in YAML. When serialized to GLB binary buffers, implementations MUST reorder to `[x, y, z, w]` (vector-first) to match the glTF 2.0 accessor convention for rotation data.

---

## 13.2 BufferView and Accessor Ordering

### Per-Primitive Emission (v0.12+)

In v0.12+, each Rigy mesh emits **one glTF mesh**, and each Rigy primitive within that mesh emits **one glTF primitive**.

- **Ordering is preserved**: glTF `primitives[i]` corresponds to Rigy `primitives[i]`.
- Each glTF primitive MUST have its own attribute accessors (POSITION, NORMAL, TEXCOORD_n) and its own indices accessor.
- If skinning is enabled, each glTF primitive MUST have its own JOINTS_0 and WEIGHTS_0 accessors.
- Inverse bind matrices are **shared per mesh** (one IBM accessor per mesh binding).
- Implementations MAY pack multiple primitives' data into shared buffer(s) for efficiency, but MUST expose **separate accessors per glTF primitive**.

For each primitive (in YAML declaration order within the mesh), buffer data MUST be emitted in this order:

1. Position data (float32 x 3 x N vertices)
2. Normal data (float32 x 3 x N vertices)
3. UV data for each declared UV set, in index order (float32 x 2 x N vertices per set)
4. Index data (uint32 x M indices)
5. If the mesh is skinned:
   a. Joint indices (uint16 x 4 x N vertices)
   b. Weights (float32 x 4 x N vertices)

After all primitives in a skinned mesh, emit:
- Inverse bind matrices (float32 x 4 x 4 x J joints, column-major) — one accessor shared by all primitives in the mesh.

### Legacy Merged Emission (v0.1–v0.11)

In v0.1–v0.11, all primitives in a mesh are merged into a single glTF primitive. For each mesh (in YAML declaration order), buffer data MUST be emitted in this order:

1. Position data (float32 x 3 x N vertices)
2. Normal data (float32 x 3 x N vertices)
3. UV data for each declared UV set, in index order (float32 x 2 x N vertices per set)
4. Index data (uint32 x M indices)
5. If the mesh is skinned:
   a. Joint indices (uint16 x 4 x N vertices)
   b. Weights (float32 x 4 x N vertices)
   c. Inverse bind matrices (float32 x 4 x 4 x J joints, column-major)

Each data block corresponds to one bufferView and one accessor, appended in the same order to their respective glTF arrays.

---

## 13.3 Vertex Attribute Order

Mesh primitives MUST emit attributes in the following order:

* `POSITION`
* `NORMAL`
* `TEXCOORD_0` (if UV set `uv0` is declared)
* `TEXCOORD_1` (if UV set `uv1` is declared)
* ... (continuing for each declared UV set)
* `JOINTS_0` (if skinned)
* `WEIGHTS_0` (if skinned)

---

## 13.4 Binary Buffer Alignment

glTF 2.0 requires accessor alignment. Padding bytes between bufferViews, if needed, MUST be zero-filled. Padding bytes are included in determinism checks (they are part of the GLB binary blob).

---

## 13.5 Material Export

When exporting to glTF 2.0:

* `base_color` MUST be exported as `pbrMetallicRoughness.baseColorFactor`
* `metallicFactor` MUST be `0.0`
* `roughnessFactor` MUST be `1.0`

### Alpha Mode (Deterministic)

To preserve byte-identical GLB output:

* If `base_color[3] == 1.0`, `alphaMode` MUST be `"OPAQUE"`
* Otherwise, `alphaMode` MUST be `"BLEND"`
* `alphaCutoff` MUST be omitted
* `doubleSided` MUST be `false`

### Numeric Serialization

When serializing `baseColorFactor` into the glTF JSON:

1. Values MUST be computed as **IEEE 754 float32**
2. Values MUST be written using a fixed decimal format with **exactly six digits after the decimal point**, using round-half-even rounding

Example:

```json
"baseColorFactor": [1.000000, 0.300000, 0.666667, 1.000000]
```

This rule ensures cross-platform string identity.

### Per-Primitive Material (v0.12+)

In v0.12+, each glTF primitive within a mesh MAY have a different material index, corresponding to its resolved material (see [Section 8.6](08-materials.md#86-material-resolution-v012)).

---

## 13.6 UV Export

When exporting to glTF 2.0:

* The UV set `uv<N>` MUST be exported as glTF attribute `TEXCOORD_<N>`.
* The numeric suffix determines the glTF attribute index.
* UV buffers are serialized as float32, little-endian.
* Attribute ordering follows canonical rules (Section 13.3).
* UV coordinates are emitted strictly per-vertex and MUST NOT be reordered, deduplicated, or canonicalized independently of vertex ordering.

---

## 13.7 Tags Export

When exporting to glTF 2.0:

* Primitives with `tags` MUST export them via glTF `extras`:

```json
"extras": { "rigy_tags": ["wall", "exterior"] }
```

* Tags are exported as-is, preserving order.
* Primitives without tags MUST NOT emit a `rigy_tags` field.

In v0.12+, `rigy_tags` and `rigy_id` (see Section 13.8) coexist in the same `extras` object.

---

## 13.8 Primitive ID Export (v0.12)

*Introduced in v0.12.*

In v0.12+, each glTF primitive MUST include the Rigy primitive ID in its `extras`:

```json
"extras": { "rigy_id": "<primitive.id>" }
```

This enables debugging and tooling to map glTF primitives back to their Rigy source definitions.

When combined with tags, the extras object contains both fields:

```json
"extras": { "rigy_id": "wall_south_gap_0", "rigy_tags": ["wall", "exterior"] }
```

---

**End of Chapter 13**
