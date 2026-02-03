You are working in a local repo that contains the Rigy v0.11 spec as a set of Markdown chapters under:

  spec/rigy/

There may also be old / misleading “examples/” files in the repo. DO NOT copy or trust anything just because it’s in an examples folder. Treat any existing house examples as potentially wrong.

Goal
----
Create a NEW Rigy v0.11 YAML file that models a simple “kids drawing” house:
- Rectangular footprint (boxy house body)
- Gable roof (two sloped roof planes)
- Chimney on one side of the roof
- Front side has: 1 door + 2 windows
- Keep it simple: exterior only, solid-color materials

Critical constraints (do not violate)
------------------------------------
1) Rigy v0.11 has NO top-level `surfaces:` registry. Do not invent it.
   - `surface:` on primitives/macros (if used) is just a label. No registry required.

2) Mesh material homogeneity is STRICT:
   - Within a single mesh, ALL primitives must reference the EXACT same `material` OR all must omit it.
   - If you use `box_decompose`, set its `material:` so all generated pieces inherit it (avoid “material: null” pieces).
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

B) Write the Rigy YAML to a NEW scratch file path you choose (NOT reusing existing “examples” houses).
   Example: scratch/kids_house.rigy.yaml

C) Compile it locally (do not assume it compiles):
   uv run rigy compile scratch/kids_house.rigy.yaml -o scratch/kids_house.glb

D) Render a PNG with f3d:
   f3d --verbose --resolution=1024,1024 --output=scratch/kids_house.png scratch/kids_house.glb

E) Visually inspect the PNG you rendered.
   - If anything is wrong (roof inverted, gables on wrong walls, missing windows/door, etc), FIX the YAML and repeat steps C–E until correct.

F) Deliverables
---------------
1) The final YAML content (only the final version).
2) The exact compile + render commands you ran.
3) A short “pain points” list that is SPEC-focused (ambiguities, confusing parameters, common errors).
   - Avoid proposing new primitives unless composition/macro usage truly failed.

Helpful implementation notes (use these)
----------------------------------------
- Keep coordinates simple and symmetrical around origin.
- Prefer `box_decompose` for the FRONT wall only (door + 2 window cutouts).
- Use separate meshes for: walls, roof, chimney, door, window glass, trim (if any).
- Roof:
  - Use two thin boxes rotated about X (+/- pitch angle) and translated so they meet at a ridge.
  - Validate ridge_y > eave_y in the render.
- Gable end caps:
  - They belong on the FRONT and BACK ends of the house (the ±Z ends if your house depth runs along Z).
  - Each end needs TWO wedges (left + right) to make a symmetric triangle.
  - Use the wedge spec to orient the prism correctly; do not “trial and error” forever—compute rotation/translation, then verify in PNG.

Sanity-check option (allowed)
-----------------------------
Optionally, before doing full visual inspection, you may run a quick Python script that converts the rendered PNG to ASCII art for a fast “shape sanity check”.
This is optional, but if you do it, include the command/script you ran.

Now do the work.
Start by reading the required spec files, then implement the YAML, then compile + render + iterate until the PNG matches the requirements.
