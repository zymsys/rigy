# 9. UV System

## 9.1 UV Roles (Normative)

*Introduced in v0.7.*

### Definition

A **UV Role** is a semantic identifier describing the *intended usage* of a texture coordinate layout.

Roles are **author-facing**, **meaningful**, and **independent of UV indices**.

### Initial UV Role Vocabulary (Normative)

The following roles are defined in Rigy v0.7. This table is **authoritative**.

| Role         | Meaning |
|--------------|---------|
| `albedo`     | Primary surface parameterization intended for base color or low-frequency surface detail. Typically non-overlapping and contiguous. |
| `detail`     | Secondary parameterization intended for high-frequency, tiling detail layered over another map. |
| `directional`| Parameterization with a stable dominant direction (e.g. wood grain, fabric weave). Orientation consistency is required; tiling is permitted. |
| `radial`     | Parameterization organized around a central point or axis (e.g. coins, knobs, dials). Continuity around the center is required; tiling is typically not expected. |
| `decal`      | Localized, non-tiling parameterization intended for labels, stickers, or markings applied to a subset of the surface. |
| `lightmap`   | Reserved role for baked lighting or similar secondary bake data. No semantics defined in v0.7. |

### Vocabulary Stability

- This role set is **finite and normative** for v0.7+.
- Future minor versions MAY add new roles.
- Existing roles MUST NOT change meaning or be removed.

### Asset-Side UV Role Exposure

Meshes MAY declare which UV roles they expose via a mesh-level `uv_roles` block:

```yaml
uv_roles:
  albedo:
    set: uv0
  detail:
    set: uv0
  decal:
    set: uv1
```

Semantics:

- `set` identifies a **UV set token** that maps to a declared UV set (in v0.8+) or remains a symbolic placeholder (in v0.7).
- All primitives within a mesh share the same UV role exposure.
- Implementations MUST NOT allow per-primitive UV role declarations.

Constraints (normative):

- Each role MUST resolve to exactly one UV set token.
- Multiple roles MAY resolve to the same UV set token.
- A role MUST NOT be declared more than once (V44).
- UV set tokens MUST follow the pattern `uv<N>` where `<N>` is a non-negative integer (V45).
- Roles MUST be from the UV role vocabulary (V43).
- In v0.8+, `uv_roles` MUST be accompanied by `uv_sets` (V53).
- In v0.8+, each role's `set` MUST reference a declared UV set (V54).

### UV Set Tokens and glTF Mapping

- UV set tokens (`uv0`, `uv1`, ...) correspond to glTF attributes `TEXCOORD_0`, `TEXCOORD_1`, etc.
- Numeric ordering of UV set tokens is zero-based and canonical.
- In v0.8+, `TEXCOORD_n` attributes are emitted for each declared UV set.

### UV Roles Express Intent Only

UV roles express semantic intent only and MUST NOT implicitly select, modify, or override UV generators.

---

## 9.2 UV Sets and UV Generation (Normative)

*Introduced in v0.8.*

### `uv_sets` (Mesh-level)

Meshes MAY declare `uv_sets` in v0.8 and later:

```yaml
uv_sets:
  uv0:
    generator: sphere_latlong@1
  uv1:
    generator: planar_xy@1
```

Schema:
- `Mesh.uv_sets: map<string, UvSetEntry> | null`
- `UvSetEntry.generator: string` (required)

Constraints:
- `uv_sets` is valid only when `version >= "0.8"`.
- UV set identifiers MUST match `uv<N>` where `N >= 0`.
- UV set identifiers MUST be unique per mesh.
- UV set identifiers MUST be **contiguous** starting from `uv0` (i.e., `uvK` implies all `uv0..uv(K-1)` are present) (V55).
- UV sets MUST be declared if any `uv_roles` are declared (V53).
- All primitives in a mesh share the same UV sets.

### Generator Identity

Each UV set references a **generator identifier**:

```yaml
generator: box_project@1
```

Rules:
- Generator identifiers are opaque strings of the form `<name>@<N>`.
- `N` MUST be a positive integer (`N >= 1`).
- Generator semantics are frozen per version suffix.
- Bug fixes or behavioral changes MUST introduce a new generator version.

### Initial Generator Vocabulary (Normative)

A conforming Rigy v0.8+ implementation MUST reject any generator identifier not listed here (V51).

| Generator ID | Applicable Primitives | Description |
|-------------|------------------------|-------------|
| `planar_xy@1` | all | Projects positions onto the XY plane |
| `box_project@1` | box | Per-face planar projection with fixed face assignment and orientation |
| `sphere_latlong@1` | sphere | Latitude/longitude UVs defined by Rigy's tessellation indices |
| `cylindrical@1` | cylinder | Cylindrical side UVs + radial cap UVs defined by tessellation indices |
| `capsule_cyl_latlong@1` | capsule | Cylinder body + lat/long hemispheres defined by tessellation indices |

A UV set generator MUST be valid for **every primitive type present in the mesh** (V52).

### Generator Evaluation Order (Normative)

UV generation occurs:

1. After tessellation
2. After symmetry expansion
3. Before glTF export

Generators operate on the mesh's vertices **after all primitive transforms** have been applied.

**Baking interaction:** If an implementation supports "baked skin" export, UV generation MUST occur on **rest-pose (pre-deformation)** positions. Pose evaluation MUST NOT affect UV coordinates.

All intermediate calculations MUST use IEEE 754 `float64` precision.
Final UV coordinates MUST be serialized as `float32`.

---

## 9.3 Generator Semantics (Normative)

### Common Rules

For all generators:

- Output UVs MUST be finite values.
- UV range is unconstrained (values MAY exceed `[0,1]`).
- Vertex order MUST NOT be modified.
- Implementations MUST NOT clamp, wrap, normalize, remap, or otherwise modify generated UV values.
- Unless explicitly specified by the generator, "seam duplication" is represented by distinct vertices that share position but differ in UVs.

### Sphere Latitude/Longitude (`sphere_latlong@1`)

This generator is defined **in terms of Rigy's sphere tessellation layout** (v0_1_default UV sphere), not by inverse-trig on positions.

Let:
- `lat_steps = 16`
- `lon_steps = 32`

For a vertex emitted at `(i_lat, i_lon)`:

```
u = i_lon / lon_steps
v = i_lat / lat_steps
```

Normative seam behavior:
- The seam is the duplicated column where `i_lon = 0` and `i_lon = lon_steps`.
- Positions are identical at the seam; UVs differ by `u=0.0` vs `u=1.0`.
- At poles, all `lon_steps+1` duplicated vertices MUST have distinct `u` values per the formula above.

### Box Projection (`box_project@1`)

This generator uses the box's canonical face emission and assigns UVs per face.

**Normative per-face mapping:**

| Face | u | v |
|------|---|---|
| +X | `-z` | `y` |
| -X | `z` | `y` |
| +Y | `x` | `-z` |
| -Y | `x` | `z` |
| +Z | `x` | `y` |
| -Z | `-x` | `y` |

Notes:
- This generator does not normalize by box dimensions.
- Implementations MUST apply the signs exactly as shown.
- Box vertices are already duplicated per face; no additional seam logic is required.

### Planar XY (`planar_xy@1`)

For each vertex position `(x, y, z)` in asset space:

```
u = x
v = y
```

No normalization is performed. UVs may be negative or exceed 1.0.

### Cylindrical (`cylindrical@1`)

This generator is defined in terms of Rigy's cylinder tessellation layout (v0_1_default, `n_radial = 32`).

**Side UVs:**

For each side vertex emitted at `(row, seg)`:

```
u = seg / n_radial
v = row                // 0 for top, 1 for bottom
```

**Cap UVs:**

For the cap center vertex: `u = 0.5`, `v = 0.5`

For each rim vertex at segment `seg`:

```
angle = 2pi * seg / n_radial
u = 0.5 + 0.5 * cos(angle)
v = 0.5 + 0.5 * sin(angle)
```

### Capsule Cylinder + Lat/Long Hemispheres (`capsule_cyl_latlong@1`)

This generator is defined in terms of Rigy's capsule tessellation layout:
- `n_radial = 32`
- `n_height = 8`
- `n_hemisphere_rings = 8`

**U coordinate (all sections):**

```
u = seg / lon_steps
```

**V coordinate partitioning:**

```
V_total_steps = n_hemisphere_rings + n_height + n_hemisphere_rings
```

- Top hemisphere ring `ring in 0..n_hemisphere_rings`: `v = ring / V_total_steps`
- Cylinder row `row in 0..n_height`: `v = (n_hemisphere_rings + row) / V_total_steps`
- Bottom hemisphere ring `ring in 1..n_hemisphere_rings`: `v = (n_hemisphere_rings + n_height + ring) / V_total_steps`

This yields shared equatorial ring semantics with no duplicate UV rows at boundaries.

---

## 9.4 UV Validation

| ID | Check |
|----|-------|
| V43 | `uv_roles` declares a role not in the v0.7 role vocabulary |
| V44 | Duplicate role key in `uv_roles` |
| V45 | `uv_roles.<role>.set` is not a valid UV set token (`uv<N>`, N >= 0) |
| V46 | A material references a UV role not exposed by the target asset |
| V47 | `uses_uv_roles` contains a role not in the v0.7 role vocabulary |
| V50 | UV set declared without a generator |
| V51 | Generator not in v0.8 vocabulary |
| V52 | A UV set generator is not valid for every primitive type present in the mesh |
| V53 | `uv_roles` declared but no `uv_sets` present |
| V54 | A `uv_role` references a UV set that is not declared |
| V55 | `uv_sets` contains a gap in indices (e.g., `uv1` present without `uv0`) |

---

**End of Chapter 9**
