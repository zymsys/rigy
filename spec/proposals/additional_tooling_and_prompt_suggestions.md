# Additional Suggestions You Might Have Missed

## A) Tooling improvements (no new primitives)

1. Canonicalize authoring style
- Add `rigy fmt` to normalize dimensions to `x/y/z` and normalize rotation field style.
- Reduces mixed-vocabulary drift.

2. Warning policy controls
- Add `--warn-as-error <codes>` and `--suppress-warning <codes>`.
- Helps CI enforce project-specific quality bars.

3. Build artifact manifest
- Add `--emit-manifest <path>` on compile/render pipelines.
- Record input hash, expanded YAML hash, output GLB hash, timestamps, tool version.
- Avoids confusion over stale images/files.

4. Standard camera presets for render docs
- Document stable preset values: `front`, `iso`, `top`.
- Encourages multi-view validation by default.

5. Optional model checks profile
- `rigy inspect --profile house` could run a curated set of generic checks (ridge above eave, symmetry deltas, overhang ranges).

## B) Prompting improvements

1. Declare axis contract in one line
- Example: "Front +Z, ridge along Z, roof slopes along X."

2. Require two fixed render outputs each iteration
- `<name>_front.png` + `<name>_iso.png` with explicit camera params.

3. Require numeric reporting before final answer
- Include ridge/eave Y and key primitive AABBs.

4. Require unique artifact names per iteration
- `*_v1`, `*_v2` (or timestamp suffix) to avoid stale overwrite ambiguity.

5. Require final artifact table
- Path, timestamp, and source command for each output.

## C) Documentation quality improvements

1. Prefer degree-first examples for transforms
- Use `rotation_degrees` in examples; mention `rotation_euler` as compatibility/canonical field.

2. Keep one canonical dimension vocabulary in docs/examples
- `x/y/z` everywhere for boxes to reduce remapping.

3. Add one full "debugging workflow" appendix
- compile + emit-expanded-yaml + inspect + render-front/iso + iterate.

## D) Recommended implementation order

1. `--emit-expanded-yaml`
2. `rigy inspect` (AABB + normals first)
3. intent checks (`W10+`)
4. manifest + warning policy knobs

This order gives immediate user value with low risk to core compiler determinism.
