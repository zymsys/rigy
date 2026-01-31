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
```

## Architecture

Rigy is a YAML-to-glTF compiler for rigged assemblies of geometric primitives. The compile pipeline is a strict linear sequence:

```
YAML → parse → expand symmetry → validate → export GLB
```

Orchestrated in `cli.py`, each stage has a dedicated module in `src/rigy/`:

- **parser.py** — Loads YAML, checks version, produces a `RigySpec` (Pydantic v2 model from `models.py`)
- **symmetry.py** — Mirror-X expansion via prefix substitution. Deep-copies the spec, negates X coordinates, renames IDs. Returns a new spec with `symmetry` cleared. Runs *before* validation.
- **validation.py** — 10 semantic checks (unique IDs, acyclic bones, positive dimensions, weight ranges, reference integrity, single-binding-per-mesh). Raises `ValidationError`.
- **tessellation.py** — Generates deterministic NumPy geometry (positions, normals, indices) per primitive type (box, sphere, cylinder, capsule) using the `v0_1_default` profile. `tessellate_mesh()` merges all primitives and returns a `prim_ranges` map tracking each primitive's vertex range.
- **skinning.py** — Builds per-vertex joint indices and weights from primitive-level assignments. Caps to 4 joints (glTF limit), normalizes weights. Computes inverse bind matrices (translation-only, negated bone head).
- **exporter.py** — Assembles glTF via pygltflib. Bone nodes use parent-relative translations. IBMs are written column-major (numpy row-major transposed). Single merged primitive per mesh.

## Key conventions

- **Pydantic strict mode**: All models use `extra="forbid"`. Unknown fields are rejected.
- **Error hierarchy**: `RigyError` → `ParseError`, `ValidationError`, `TessellationError`, `ExportError`. CLI catches `RigyError` and converts to `click.ClickException`.
- **Immutable data flow**: Symmetry expansion returns a new spec (deep copy); validation does not mutate.
- **Determinism**: Same YAML must produce byte-identical GLB. Tests verify this.
- **Coordinate system**: glTF 2.0 aligned — Y-up, -Z forward, right-handed, meters.
- **Transforms**: Rotation (Euler XYZ) applied before translation. Normals rotated but not translated.
- **Spec version**: v0.1. Parser rejects major != 0, warns on minor > 1. v0.2 fields (imports, anchors, instances, attach3) are intentionally rejected.

## Test patterns

- Shared YAML fixtures in `tests/conftest.py` (`minimal_mesh_yaml`, `full_humanoid_yaml`)
- `_make_spec()` helper in test_validation.py for programmatic spec construction
- NumPy assertions via `np.testing.assert_allclose()`
- Determinism tests compare byte-for-byte GLB output across runs
- `tests/fixtures/humanoid.rigy.yaml` is a full example used in e2e tests
- `composition/` contains v0.2 example files that v0.1 must reject
