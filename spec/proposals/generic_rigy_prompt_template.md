# Generic Prompt Template for Better Rigy Outputs

Use this template when requesting Rigy models for arbitrary objects (table, toy, computer, etc.).

```md
Create a NEW Rigy v0.11 model for: <OBJECT>.

Requirements:
- Visual style: <simple/stylized/realistic-ish>
- Scope: <exterior-only | include interior detail>
- Primitive policy: <allowed types/macros>, avoid unnecessary complexity
- Keep model centered near origin and dimensions in meters

Coordinate contract:
- Up: +Y
- Front: <+Z or -Z>
- Main width axis: <X>
- Main depth axis: <Z>

Hard constraints:
1) No top-level `surfaces:` registry.
2) Material homogeneity per mesh is strict (V41): split meshes by material.
3) If using `aabb`, do not combine with transform translation/rotation/scale.
4) If using `box_decompose`, ensure generated geometry inherits intended material.

Mandatory workflow:
1) Read relevant spec chapters:
   - spec/rigy/index.md
   - spec/rigy/03-primitives.md
   - spec/rigy/08-materials.md
   - spec/rigy/10-preprocessing.md
   - spec/rigy/12-validation.md
2) Write to NEW path: scratch/<name>.rigy.yaml
3) Before writing YAML, provide a decomposition plan:
   - part list
   - primitive choice per part
   - mesh/material grouping (V41-safe)
4) Compile:
   - `uv run rigy compile scratch/<name>.rigy.yaml -o scratch/<name>.glb`
5) Render two views:
   - isometric: `scratch/<name>_iso.png`
   - front: `scratch/<name>_front.png`
6) If incorrect, revise and repeat steps 4-5 until requirements are met.

Deliverables:
1) Final YAML content only
2) Exact compile/render commands run
3) Final check table:
   - world AABB
   - key-part positions/sizes
   - important alignment/symmetry checks
4) Brief pain points list (spec ambiguities, easy failure modes)
```

## Optional add-ons for reliability

- Require unique artifact names per iteration (`*_v1`, `*_v2`, ...).
- Require fixed camera parameters for front/iso renders.
- Require a final artifact table with path + timestamp + source command.
- Require numeric sanity checks before final answer (not only visual screenshots).

## Why this template works

- Forces explicit geometry intent before implementation.
- Reduces axis/remapping mistakes.
- Prevents mesh/material validation errors late in the loop.
- Makes visual checks reproducible and less dependent on one camera angle.
