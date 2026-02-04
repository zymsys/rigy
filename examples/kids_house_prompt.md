You are working in a local repo that contains the Rigy v0.11 spec as a set of Markdown chapters under:

  spec/rigy/

There may also be old / misleading "examples/" files in the repo. DO NOT copy or trust anything just because it's in an examples folder. Treat any existing house examples as potentially wrong.

Goal
----
Create a NEW Rigy v0.11 YAML file that models a simple "kids drawing" house:
- Visual style: simple / stylized
- Scope: exterior only
- Primitive policy: boxes, wedges, `box_decompose`; avoid unnecessary complexity
- Rectangular footprint (boxy house body)
- Gable roof (two sloped roof planes)
- Chimney on one side of the roof
- Front side has: 1 door + 2 windows
- Solid-color materials throughout

Coordinate contract
-------------------
- Up: +Y
- Front: -Z (glTF convention)
- Main width axis: X
- Main depth axis: Z
- Model centered near origin, dimensions in meters

Critical constraints (do not violate)
------------------------------------
1) Rigy v0.11 has NO top-level `surfaces:` registry. Do not invent it.
   - `surface:` on primitives/macros (if used) is just a label. No registry required.

2) Mesh material homogeneity is STRICT (V41):
   - Within a single mesh, ALL primitives must reference the EXACT same `material` OR all must omit it.
   - If you use `box_decompose`, set its `material:` so all generated pieces inherit it (avoid "material: null" pieces).
   - Split meshes by material when needed (walls vs roof vs trim vs glass etc).

3) If you use `aabb` for a box:
   - Do NOT also provide transform.translation / rotation / scale for that primitive.
   - aabb is mutually exclusive with center-based placement transforms.

4) For wedge usage (gable end caps):
   - Read the wedge definition in the spec before you place or rotate it.
   - Wedge is a right triangular prism; if you want an isosceles gable, you likely need TWO wedges per gable end (mirrored) to form a symmetric triangle.

Workflow you MUST follow
------------------------
A) Read the spec chapters needed (do not guess):
   - spec/rigy/index.md (chapter map)
   - spec/rigy/03-primitives.md (especially wedge)
   - spec/rigy/08-materials.md (V41 material homogeneity)
   - spec/rigy/10-preprocessing.md (aabb + box_decompose behavior)
   - spec/rigy/12-validation.md (error categories)
   Also read the README.md to learn about available CLI tools (especially `rigy inspect`).

B) Before writing any YAML, provide a decomposition plan:
   - Part list (body, roof left, roof right, chimney, door, windows, gable caps, ...)
   - Primitive choice per part (box, wedge, box_decompose, ...)
   - Mesh/material grouping (V41-safe: one material per mesh)

C) Write the Rigy YAML to a NEW scratch file path you choose (NOT reusing existing "examples" houses).
   Example: scratch/kids_house.rigy.yaml
   Use versioned filenames per iteration (`*_v1`, `*_v2`, ...) so earlier attempts are preserved.

D) Compile it locally (do not assume it compiles):
   uv run rigy compile scratch/kids_house.rigy.yaml -o scratch/kids_house.glb

E) Run `rigy inspect` to verify geometry BEFORE rendering:
   uv run rigy inspect scratch/kids_house.rigy.yaml
   Check that:
   - Gable apex coordinates and roof panel AABBs share the SAME ridge line (same axis, same Y height).
   - Gable slope normals match roof top-surface normals (same pitch angle).
   - Door/window AABBs fall within the front wall's span.

F) Render two views with f3d:
   - Isometric: `f3d --verbose --resolution=1024,1024 --output=scratch/kids_house_iso.png scratch/kids_house.glb`
   - Front:     `f3d --verbose --resolution=1024,1024 --camera-direction=0,0,1 --output=scratch/kids_house_front.png scratch/kids_house.glb`

G) Visually inspect both PNGs.
   - If anything is wrong (roof inverted, gables on wrong walls, missing windows/door, etc), FIX the YAML and repeat steps D–G until correct.

H) Deliverables
---------------
1) The final YAML content (only the final version).
2) The exact compile + render + inspect commands you ran.
3) Final check table:
   - World AABB (min/max extents)
   - Key-part positions and sizes (house body, roof ridge, chimney top, door, windows)
   - Important alignment/symmetry checks (roof planes meet at ridge, gable caps flush with walls, door centered or offset as intended)
4) A short "pain points" list that is SPEC-focused (ambiguities, confusing parameters, common errors).
   - Avoid proposing new primitives unless composition/macro usage truly failed.

Helpful implementation notes (use these)
----------------------------------------
- Keep coordinates simple and symmetrical around origin.
- Prefer `box_decompose` for the FRONT wall only (door + 2 window cutouts).
- Use separate meshes for: walls, roof, chimney, door, window glass, trim (if any).
- Roof and gable caps MUST share the same ridge axis:
  - For a classic "kids drawing" house (triangular gable visible from front at -Z),
    the ridge runs along Z (front-to-back) and the roof slopes left/right (±X).
  - Use two thin boxes rotated about Z (+/- pitch angle) and translated so they
    meet at a ridge line along Z.
  - Validate ridge_y > eave_y in the render.
  - CRITICAL: after writing the YAML, use `rigy inspect` to verify the gable wedge
    apex coordinates lie ON the roof ridge line. If the roof ridge runs along one axis
    but the gable apexes trace a line along a perpendicular axis, the geometry is wrong
    even if the renders look plausible.
- Gable end caps:
  - They belong on the FRONT and BACK ends of the house (the ±Z ends if your house depth runs along Z).
  - Each end needs TWO wedges (left + right) to make a symmetric triangle.
  - The gable slope normal must match the roof top-surface normal (same pitch angle).
  - Use the wedge spec to orient the prism correctly; compute rotation/translation from
    the spec's conceptual vertices, then verify with `rigy inspect` face normals.

Now do the work.
Start by reading the required spec files, then plan the decomposition, then implement the YAML, then compile + render + iterate until the PNGs match the requirements.
