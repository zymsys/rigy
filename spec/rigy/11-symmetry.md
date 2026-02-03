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

**End of Chapter 11**
