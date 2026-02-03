# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
uv sync                          # install dependencies
uv run pytest                    # run all tests
uv run pytest tests/test_foo.py  # run one test file
uv run pytest -k test_name       # run tests matching name
uv run ruff check src/           # lint
uv run ruff format src/          # format
rigy compile input.rigy.yaml -o output.glb  # compile a spec
rigy compile input.rigy.yaml --pose rest --bake-skin -o baked.glb  # baked pose export
f3d output.glb --output render.png --resolution 800,600  # render GLB to PNG
```

## Architecture

Rigy is a YAML-to-glTF compiler for rigged assemblies of geometric primitives. The compile pipeline is a strict linear sequence:

```
YAML → preprocess → parse → expand symmetry → validate → tessellate → skin → export GLB
```

Orchestrated in `cli.py`, each stage has a dedicated module in `src/rigy/`:

- **preprocessing.py** — v0.10+ macro expansion: `repeat` loops, `$param` substitution, AABB syntax (`[[x,y,z],[x,y,z]]`), and `box_decompose` (v0.11). Runs on raw dicts before Pydantic validation.
- **parser.py** — Loads YAML via ruamel.yaml (duplicate key detection), checks version, resolves imports recursively with cycle detection, produces `RigySpec` (Pydantic v2 model from `models.py`).
- **symmetry.py** — Mirror-X expansion via prefix substitution. Deep-copies the spec, negates X coordinates, renames IDs. Returns a new spec with `symmetry` cleared. Runs *before* validation.
- **validation.py** — Semantic checks (unique IDs, acyclic bones, positive dimensions, weight ranges, reference integrity, single-binding-per-mesh, version gating). Raises `ValidationError`.
- **tessellation.py** — Generates deterministic NumPy geometry (positions, normals, indices) per primitive type (box, sphere, cylinder, capsule, wedge) using the `v0_1_default` profile. `tessellate_mesh()` merges all primitives and returns a `prim_ranges` map tracking each primitive's vertex range.
- **skinning.py** — Builds per-vertex joint indices and weights via 5-layer influence resolution (default → per-primitive → external JSON → gradients → overrides). Caps to 4 joints (glTF limit), normalizes weights. Computes inverse bind matrices (translation-only, negated bone head).
- **exporter.py** — Assembles glTF via pygltflib. Bone nodes use parent-relative translations. IBMs are written column-major (numpy row-major transposed). Generates UV sets (v0.8), exports materials (v0.6), handles baked pose export (v0.5).
- **dqs.py** — Dual Quaternion Skinning pose evaluator (v0.5). Preserves volume at bent joints vs. LBS collapse.

### Composition subsystem (v0.2)

For specs with `imports`, additional modules handle instance resolution:

- **composition.py** — Resolves instances, computes transforms, produces `ComposedAsset`.
- **attach3.py** — 3-point frame alignment (rigid/uniform/affine modes) for anchor-based attachment.
- **contracts.py** — Validates `.ricy.yaml` interface definitions (required anchors, frame3 sets).

### Rigs subsystem (v0.1)

Separate pipeline for `.rigs.yaml` scene composition files:

- **rigs_parser.py** — Parses `RigsSpec`, resolves all Rigy imports.
- **rigs_composition.py** — Traverses scene tree, snaps mount frames onto slot frames.
- **rigs_placement.py** — Frame rotation (0/90/180/270°), nudge parsing (m/cm/in/ft).
- **rigs_exporter.py** — Merges assets into single GLB with mesh deduplication.

## Key conventions

- **Pydantic strict mode**: All models use `extra="forbid"`. Unknown fields are rejected.
- **Error hierarchy**: `RigyError` → `ParseError`, `ValidationError`, `TessellationError`, `ExportError`. CLI catches `RigyError` and converts to `click.ClickException`.
- **Immutable data flow**: Symmetry expansion returns a new spec (deep copy); validation does not mutate.
- **Determinism**: Same YAML must produce byte-identical GLB. Tests verify this.
- **Coordinate system**: glTF 2.0 aligned — Y-up, -Z forward, right-handed, meters.
- **Transforms**: Rotation (Euler XYZ) applied before translation. Normals rotated but not translated.
- **Spec versions**: v0.1–v0.11. Parser rejects major ≥ 1. Key version additions:
  - v0.4: `skinning_solver`, NaN/Infinity check, float64 precision, conformance suite
  - v0.5: DQS solver, per-binding override, poses, baked GLB export
  - v0.6: Solid-color materials (`base_color`)
  - v0.8: UV generation (5 deterministic generators: planar_xy, box_project, sphere_latlong, cylindrical, capsule_cyl_latlong)
  - v0.9: Wedge primitive, surface keys
  - v0.10: Preprocessing (repeat macros, params substitution)
  - v0.11: AABB box syntax, `box_decompose` macro, semantic tags

## Test patterns

- Shared YAML fixtures in `tests/conftest.py` (`minimal_mesh_yaml`, `full_humanoid_yaml`)
- `_make_spec()` helper in test_validation.py for programmatic spec construction
- NumPy assertions via `np.testing.assert_allclose()`
- Determinism tests compare byte-for-byte GLB output across runs
- `tests/fixtures/humanoid.rigy.yaml` is a full example used in e2e tests
- `composition/` contains v0.2 example files that v0.1 must reject
- `conformance/` contains canonical input/output GLB pairs with SHA-256 hashes in `manifest.json`

## Visual verification

**Always visually verify GLB output with f3d** when working on geometry, skinning, or export changes. Render to PNG and inspect:

```bash
f3d output.glb --output render.png --resolution 800,600
```

This catches bugs that unit tests miss (e.g. missing IBM composition in DQS, wrong rotation axes, mangled geometry). Compare against the reference rest-pose render of `conformance/outputs/I01_arm_weight_maps.glb` or `examples/I01_skinned.glb` as a sanity baseline.
