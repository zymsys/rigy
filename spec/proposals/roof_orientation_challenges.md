# Roof Orientation Challenges in the Kids House Exercise

## What made this harder than expected

1. **Axis intent was underspecified at the "house design" level**
   - We had geometry rules, but not a single explicit contract like: "ridge runs along Z; roof slopes along X; front is +Z."
   - I initially built a valid-looking roof that was effectively rotated relative to the intended gable relationship.

2. **Mixed dimension vocabularies increase cognitive load**
   - `box` uses `width/height/depth`, while `wedge` uses `x/y/z`.
   - For gable alignment, this forces constant mental remapping between conceptual dimensions and world axes.

3. **Euler rotation reasoning is brittle in practice**
   - The spec is clear, but composing `rotation_euler` for wedge orientation + mirror cases is easy to get wrong.
   - Small sign mistakes still produce plausible geometry, so errors can survive until visual inspection.

4. **No geometric constraint/snap feedback**
   - Nothing in validation says "roof eave/ridge should coincide with gable boundary planes" or "gable apex should touch roof underside."
   - So semantically wrong-but-valid outputs compile cleanly.

5. **Render/camera workflow can mask state confusion**
   - Different camera options can make orientation look "fixed" from one view and wrong from another.
   - Re-rendering to the same output name makes it harder to tell which artifact corresponds to which model revision.

## Could Rigy be easier (without adding new primitives)?

Yes. The biggest wins are in **authoring helpers and diagnostics**, not primitive count.

1. **Add a compile-time expanded dump mode**
   - e.g. `rigy compile --emit-expanded-yaml ...`
   - Makes macro results and final transforms auditable before render.

2. **Add structural diagnostics/inspect command**
   - e.g. `rigy inspect model.rigy.yaml` showing per-primitive world AABB, face plane normals, and key alignment distances.
   - This would catch roof/gable misalignment numerically, not just visually.

3. **Add optional rotation degrees input (authoring convenience)**
   - Keep canonical internal radians, but allow `rotation_degrees` in preprocessing.
   - Reduces manual radian conversion errors while preserving deterministic output.

4. **Add optional validation hints (warnings, not hard errors)**
   - Example: warn when two surfaces intended to meet are within a large gap/overlap tolerance.
   - This stays within existing primitives and keeps the spec strict where needed.

5. **Add standard render presets for debugging**
   - Not a primitive change: just consistent camera presets (`front`, `isometric`, `top`) in tooling docs/CLI wrappers.
   - Reduces false confidence from a single favorable view.

## Prompting improvements that would have helped

1. **Pin the orientation contract in one line**
   - Example: "Front is +Z, depth is Z, ridge axis is Z, roof slope axis is X."

2. **Require explicit geometric checks in text**
   - Example: "Report ridge Y, eave Y, and the two gable apex coordinates before final render."

3. **Require two fixed camera renders by name**
   - Example: `kids_house_iso.png` and `kids_house_front.png` with exact camera params in prompt.

4. **Require unique output names per iteration**
   - Avoid stale-file ambiguity (`*_v1`, `*_v2`, etc.).

5. **Call out wedge mirror strategy explicitly**
   - The prompt already hinted at two wedges per gable end; adding exact expected plane/axis for those wedges would remove most ambiguity.

## Bottom line

You likely do **not** need more primitives for this class of model.
The pain came from transform/axis ambiguity and weak geometric diagnostics.
Improving prompt specificity and adding lightweight tooling feedback would remove most of the friction.

## Reusable prompt template (with helpful pieces from your original)

You can reuse this for similar tasks:

```md
Goal:
Create a NEW Rigy v0.11 YAML for <object>, exterior only, solid colors.

Axis contract (explicit):
- Front is +Z, back is -Z
- Left/right are -X/+X
- Up is +Y
- For roofs: ridge axis is <X|Z>, slope axis is <Z|X>

Must-read spec chapters before modeling:
- spec/rigy/index.md
- spec/rigy/03-primitives.md (wedge)
- spec/rigy/08-materials.md (V41)
- spec/rigy/10-preprocessing.md (aabb, box_decompose)
- spec/rigy/12-validation.md

Critical constraints:
1) No top-level `surfaces:` registry.
2) Material homogeneity per mesh is strict (V41): split meshes by material.
3) `aabb` cannot be combined with transform translation/rotation/scale.
4) Wedge is a right triangular prism; symmetric gables usually need two mirrored wedges per end.

Implementation requirements:
- Use a NEW path: scratch/<name>.rigy.yaml
- Prefer `box_decompose` for wall cutouts
- Keep coordinates simple and symmetric around origin

Verification loop (required):
1) Compile: `uv run rigy compile scratch/<name>.rigy.yaml -o scratch/<name>.glb`
2) Render isometric: `f3d --verbose --resolution=1024,1024 --output=scratch/<name>_iso.png scratch/<name>.glb`
3) Render front: `f3d --resolution=1024,1024 --camera-direction=0,-0.2,-1 --output=scratch/<name>_front.png scratch/<name>.glb`
4) If incorrect, fix YAML and repeat.

Report before finalizing:
- ridge_y and eave_y
- gable apex coordinates (front + back)
- final file list with timestamps

Deliverables:
1) Final YAML content only
2) Exact compile/render commands run
3) Spec-focused pain points (ambiguities, easy mistakes)
```
