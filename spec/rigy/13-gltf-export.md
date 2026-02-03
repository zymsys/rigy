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

For each mesh (in YAML declaration order), buffer data MUST be emitted in this order:

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

---

**End of Chapter 13**
