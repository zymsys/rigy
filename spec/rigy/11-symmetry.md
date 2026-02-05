# 11. Symmetry

## 11.1 Symmetry Interaction

Symmetry expansion operates **before validation**, **before weight-map evaluation**, and **before glTF emission**.

The rules from v0.3 remain normative:

* Deep-copy all primitives, bones, anchors, and ID-bearing objects
* Apply rename rules deterministically (e.g., `_L` -> `_R`)
* Preserve stable output ordering: original items first, then mirrored items
* Negate X coordinates in positions, bone heads, bone tails
* Reverse triangle winding to preserve outward-facing normals
* Gradient `axis: x` MUST invert its range: `[a, b]` -> `[-b, -a]`
* Other axes (`y`, `z`) preserve their range values
* External weight file paths are **not** mirrored (both sides reference the same file)

---

## 11.2 Materials and Symmetry

During symmetry expansion:

* Material references on primitives are **preserved unchanged**
* Material IDs are **not renamed or duplicated**
* The `materials` table itself is **not modified or duplicated**

Materials are not spatially dependent and do not participate in symmetry transforms.

---

## 11.3 UV Roles and Symmetry

During symmetry expansion:

* `uv_roles` declarations MUST be deep-copied verbatim to mirrored meshes.
* Role names and UV set tokens are preserved unchanged.
* No implicit U/V flipping or remapping occurs.

---

## 11.4 UV Sets and Symmetry

During symmetry expansion:

* `uv_sets` declarations MUST be deep-copied verbatim to mirrored meshes.
* UV generators operate on all vertices (original + mirrored) after expansion.
* No special UV flipping or post-processing is performed.

**Note (Non-Normative):** Because symmetry mirrors geometry, textures sampled via generated UVs will appear mirrored on mirrored surfaces (e.g., text or directional grain). This is expected; future versions may introduce explicit UV-space mirroring controls.

---

## 11.5 Tags and Symmetry

During symmetry expansion:

* `tags` on primitives MUST be deep-copied verbatim to mirrored primitives.
* Tag names are preserved unchanged.

---

## 11.6 Implicit Surfaces and Symmetry

*Introduced in v0.13.*

During symmetry expansion of `implicit_surface` primitives:

### Operator Merging

* Symmetry expansion operates on the **field operator list**
* Mirrored operators are **merged into the same implicit surface** (not duplicated as a separate primitive)
* Surface extraction occurs **once**, after expansion

This ensures implicit blending across the symmetry plane.

### Domain Expansion Rule (Normative)

After symmetry expansion merges mirrored operators into the same implicit surface, the compiler MUST expand the sampling domain AABB to enclose the full region influenced by the expanded operator set.

For a symmetry mirror about the YZ plane (X mirror):

Let original AABB be:

* `min = (x0, y0, z0)`
* `max = (x1, y1, z1)`

Define mirrored AABB:

* `min' = (-x1, y0, z0)`
* `max' = (-x0, y1, z1)`

Expanded AABB is the union:

* `min_exp = (min(x0, -x1), y0, z0)`
* `max_exp = (max(x1, -x0), y1, z1)`

The compiler MUST use the expanded AABB for grid sampling and extraction.

Grid resolution (`nx`, `ny`, `nz`) remains unchanged. The world-space grid step size MAY change as a result of domain expansion.

### Operator Transform Mirroring

For each mirrored operator:

* X component of translation is negated
* Rotation is mirrored about the YZ plane (consistent with existing symmetry rules)

### Material and Tag Interaction

Material references and tags on implicit surface primitives follow the same rules as other primitives (see Sections 11.2 and 11.5).

---

**End of Chapter 11**
