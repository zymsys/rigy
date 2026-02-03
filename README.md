# Rigy

A text-based specification language for rigged assemblies of geometric primitives — *Mermaid for 3D assets*.

Rigy lets you describe geometric primitives, skeletal armatures, and skinning relationships in human-readable YAML. Specs compile deterministically to **glTF/GLB**, loadable directly in Blender, Godot, or any glTF-compatible tool.

## Install

```bash
pip install .
```

Or in editable mode for development:

```bash
pip install -e .
```

Requires Python 3.12+.

## Usage

### CLI

```bash
rigy compile humanoid.rigy.yaml -o humanoid.glb
rigy compile humanoid.rigy.yaml  # outputs humanoid.glb
rigy compile scene.rigs.yaml -o scene.glb  # Rigs scene composition
```

The CLI auto-detects `.rigs.yaml` files and routes to the Rigs composition pipeline.

### Library

#### Rigy (single asset)

```python
from rigy.parser import parse_with_imports
from rigy.symmetry import expand_symmetry
from rigy.validation import validate, validate_composition
from rigy.composition import resolve_composition
from rigy.exporter import export_gltf
from pathlib import Path

asset = parse_with_imports(Path("car.rigy.yaml"))
asset.spec = expand_symmetry(asset.spec)
validate(asset.spec)
for imported in asset.imported_assets.values():
    imported.spec = expand_symmetry(imported.spec)
composed = resolve_composition(asset)
export_gltf(composed, Path("car.glb"))
```

For v0.1 files without imports, the same pipeline works — `imported_assets` will be empty and `resolve_composition` passes through the root spec.

#### Rigs (scene composition)

```python
from rigy.rigs_parser import parse_rigs
from rigy.rigs_validation import validate_rigs
from rigy.rigs_composition import compose_rigs
from rigy.rigs_exporter import export_rigs_gltf
from pathlib import Path

asset = parse_rigs(Path("scene.rigs.yaml"))
validate_rigs(asset)
composed = compose_rigs(asset)
export_rigs_gltf(composed, Path("scene.glb"))
```

## Examples

### Humanoid with symmetry and materials (v0.6)

A minimal humanoid with symmetry-expanded legs and a solid-color material (`tests/fixtures/humanoid.rigy.yaml`):

```yaml
version: "0.6"
units: meters
coordinate_system:
  up: Y
  forward: -Z
  handedness: right
tessellation_profile: v0_1_default

materials:
  skin:
    base_color: [0.8, 0.6, 0.5, 1.0]

meshes:
  - id: humanoid_mesh
    primitives:
      - type: capsule
        id: torso
        dimensions: { radius: 0.15, height: 0.30 }
        transform: { translation: [0, 1.15, 0] }
        material: skin
      - type: sphere
        id: head
        dimensions: { radius: 0.12 }
        transform: { translation: [0, 1.60, 0] }
        material: skin
      - type: capsule
        id: legL_upper
        dimensions: { radius: 0.07, height: 0.25 }
        transform: { translation: [0.12, 0.65, 0] }
        material: skin
      - type: capsule
        id: legL_lower
        dimensions: { radius: 0.05, height: 0.28 }
        transform: { translation: [0.12, 0.24, 0] }
        material: skin

armatures:
  - id: humanoid_armature
    bones:
      - { id: root, parent: none, head: [0, 0.90, 0], tail: [0, 0.95, 0], roll: 0.0 }
      - { id: spine, parent: root, head: [0, 0.95, 0], tail: [0, 1.40, 0], roll: 0.0 }
      - { id: neck, parent: spine, head: [0, 1.40, 0], tail: [0, 1.60, 0], roll: 0.0 }
      - { id: legL_upper, parent: root, head: [0.12, 0.90, 0], tail: [0.12, 0.48, 0], roll: 0.0 }
      - { id: legL_lower, parent: legL_upper, head: [0.12, 0.48, 0], tail: [0.12, 0.05, 0], roll: 0.0 }

bindings:
  - mesh_id: humanoid_mesh
    armature_id: humanoid_armature
    weights:
      - { primitive_id: torso, bones: [{ bone_id: spine, weight: 1.0 }] }
      - { primitive_id: head, bones: [{ bone_id: neck, weight: 1.0 }] }
      - { primitive_id: legL_upper, bones: [{ bone_id: legL_upper, weight: 1.0 }] }
      - { primitive_id: legL_lower, bones: [{ bone_id: legL_lower, weight: 1.0 }] }

symmetry:
  mirror_x:
    prefix_from: "legL_"
    prefix_to: "legR_"
```

The compiler expands `symmetry` before validation, producing mirrored `legR_*` primitives, bones, and weights automatically. The `materials` table defines named solid-color materials referenced by primitives — all primitives in a mesh must share the same material.

### Composed car with imported wheels (v0.2)

A car body that imports a reusable wheel part and mounts four instances via 3-point anchor frames (`tests/composition/car.rigy.yaml`):

```yaml
version: "0.2"

imports:
  wheel:
    source: parts/wheel.rigy.yaml
    contract: parts/wheel.ricy.yaml

meshes:
  - id: car_body_mesh
    name: CarBody
    primitives:
      - type: box
        id: body
        dimensions: { x: 2.2, y: 0.4, z: 1.2 }
        transform: { translation: [0.0, 0.45, 0.0] }
      - type: box
        id: cabin
        dimensions: { x: 0.9, y: 0.35, z: 0.9 }
        transform: { translation: [-0.3, 0.75, 0.0] }

anchors:
  - { id: fl_a, translation: [0.8, 0.25, 0.65] }
  - { id: fl_b, translation: [1.8, 0.25, 0.65] }
  - { id: fl_c, translation: [0.8, 1.25, 0.65] }
  # ... and fr_*, rl_*, rr_* anchor triplets

instances:
  - id: wheel_fl
    import: wheel
    attach3:
      from: [wheel.mount_a, wheel.mount_b, wheel.mount_c]
      to: [fl_a, fl_b, fl_c]
      mode: rigid
  # ... wheel_fr, wheel_rl, wheel_rr
```

Each wheel part defines its own mesh and a 3-point mount frame. The `attach3` block computes the rigid transform that maps the wheel's mount frame onto the car's anchor frame, positioning and rotating each wheel correctly.

### Scene composition with Rigs (v0.1)

A Rigs file (`.rigs.yaml`) composes multiple Rigy assets into a single glTF scene via slot-to-mount frame snapping (`tests/rigs_fixtures/nested_scene.rigs.yaml`):

```yaml
rigs_version: "0.1"
imports:
  plate: parts/base_plate.rigy.yaml
  cube: parts/cube.rigy.yaml

scene:
  base: plate
  children:
    - id: cube1
      base: cube
      place:
        slot:  { anchors: [top_a, top_b, top_c] }
        mount: { anchors: [bottom_a, bottom_b, bottom_c] }
      children:
        - id: cube2
          base: cube
          place:
            slot:  { anchors: [top_a, top_b, top_c] }
            mount: { anchors: [bottom_a, bottom_b, bottom_c] }
```

Each child is placed by snapping its **mount** frame (three anchors on the child) onto a **slot** frame (three anchors on the parent). Optional `rotate` (discrete 0/90/180/270 deg yaw) and `nudge` (translation in slot-frame axes with friendly units like `20cm`, `1ft`) provide artist-friendly adjustments. Slots and mounts can be referenced by name via Ricy contracts or by explicit anchor triples.

## What's Implemented

### v0.1 — Rigged primitives

**Primitives** — `box`, `sphere`, `capsule`, `cylinder`, `wedge` with fixed tessellation (`v0_1_default` profile), per-primitive transforms, and symbolic material references.

**Armatures** — Bone trees with head/tail positioning, roll, and parent hierarchy. Validated for cycles and zero-length bones.

**Skinning** — Primitive-level weight assignment (all vertices in a primitive get identical weights). Weights are normalized and capped to 4 bones per primitive for glTF compatibility.

**Bindings** — Connect a mesh to an armature with per-primitive bone weights. Each mesh may appear in only one binding.

**Symmetry** — Compile-time mirror-X expansion via prefix substitution. Deterministic and applied before validation.

**Validation** — Unique IDs, acyclic bone hierarchies, positive dimensions, weight range checks, reference integrity, unknown field rejection (strict mode).

**Export** — glTF 2.0 / GLB with positions, normals, indices, skinning joints/weights, and inverse bind matrices.

### v0.2 — Composition

**Anchors** — Named 3D points on meshes, used as attachment sites. Mirrored by symmetry expansion.

**Imports** — Reference external `.rigy.yaml` files as reusable parts. Resolved recursively with circular import detection.

**Contracts** (`.ricy.yaml`) — Interface definitions that imported parts must satisfy. Specify required anchors and frame3 sets. Validated at composition time.

**Instances** — Place imported parts into a scene. Each instance references an import and an `attach3` block.

**attach3** — 3-point frame alignment. Given three `from` anchors on the imported part and three `to` anchors on the parent, computes the affine transform mapping one frame to the other. Three constraint modes:
- `rigid` — rotation + translation only (no scale/shear)
- `uniform` — rotation + translation + uniform scale
- `affine` — full affine transform (rotation, translation, scale, shear)

### v0.3 — Per-vertex weight maps

**Weight maps** — Per-vertex joint influences that replace rigid per-primitive skinning with smooth deformation across bone boundaries. Defined per-primitive in `bindings[].weight_maps[]`.

**Gradients** — Parametric weight blending along an axis (`x`, `y`, or `z`). A gradient linearly interpolates between a `from` and `to` bone set over a spatial range, producing smooth joint transitions without manually specifying per-vertex data. Clamped outside the range. Multiple gradients on the same primitive are applied in order (last wins).

**Overrides** — Explicit vertex-index assignments that override all other weight sources for the listed vertices. Useful as an escape hatch for vertices that need hand-tuned weights.

**External JSON sources** — Weight maps can reference an external `.json` file via `source`, containing per-vertex `influences` arrays. Useful for weights exported from external tools.

**Resolution order** — Influences are resolved in a strict 5-layer hierarchy: default binding → per-primitive weights → external JSON → gradients → overrides. Each layer fully replaces the previous for affected vertices.

**Sorting & capping** — Influences are sorted by descending weight, then ascending bone ID, then ascending bone index. Capped to 4 joints per vertex (glTF limit) with weight renormalization. Vertices with zero total weight fall back to the root bone.

**Symmetry interaction** — Weight maps are expanded under mirror-X symmetry: primitive and bone IDs are renamed, X-axis gradient ranges are negated and swapped, and external JSON source paths are preserved as-is.

### v0.4 — Determinism, conformance, and correctness

**Formalization release** — No new authoring constructs. Strengthens determinism guarantees and establishes a normative conformance suite.

**Float64 intermediate precision** — All intermediate arithmetic uses IEEE 754 float64. Truncation to float32 occurs only at the GLB serialization boundary, ensuring byte-identical output across implementations.

**Conformance suite** — Canonical input/output pairs under `conformance/` with SHA-256 hashes in `conformance/manifest.json`. The test runner (`tests/test_conformance.py`) verifies byte-identical GLB output.

**V32 validation** — NaN and ±Infinity values in any numeric field (dimensions, transforms, bone positions, weights) are now a hard error.

**`skinning_solver` field** — Reserved extension point. Only `"lbs"` (Linear Blend Skinning) is valid in v0.4; defaults to `"lbs"` when absent.

**Box dimension keys** — Boxes now accept `width`/`height`/`depth` in addition to `x`/`y`/`z`.

**Cylinder winding fix** — Bottom cap triangle winding corrected to match the normative spec pseudocode.

### v0.5 — Dual Quaternion Skinning

**DQS solver** — `skinning_solver: dqs` activates Dual Quaternion Skinning, which preserves volume at bent joints where LBS collapses. The solver runs in float64 with full dual-quaternion normalization and hemisphere consistency, truncating to float32 at the GLB boundary.

**Per-binding solver override** — Each binding can set its own `skinning_solver`, overriding the top-level default. This allows mixing LBS and DQS within a single spec (e.g., rigid props use LBS, organic limbs use DQS).

**Poses** — Named pose definitions (`poses[]`) specify per-bone rotations (unit quaternion `[w,x,y,z]`) and translations. Validated for finite components and unit-length quaternions (V36).

**Baked GLB export** — `rigy compile --pose <id> --bake-skin` evaluates a pose and writes deformed geometry directly into the GLB, omitting JOINTS_0/WEIGHTS_0/Skin data. Useful for conformance testing and static snapshots.

**Conformance fixtures** — Six new test cases (L01–N02) covering identity pose, two-bone twist, mixed solver, top-level override, opposing-hemisphere quaternions, and near-antipodal blending.

### v0.6 — Solid-color materials

**Materials table** — Named materials defined at the top level with `base_color: [r, g, b, a]` in linear RGBA. Each component must be a finite float in `[0.0, 1.0]`.

**Primitive assignment** — Primitives reference materials by ID. All primitives within a mesh must share the same material (or all omit it). Omitting `material` uses the implicit default (`[1.0, 1.0, 1.0, 1.0]`).

**glTF export** — Materials export as `pbrMetallicRoughness.baseColorFactor` with `metallicFactor=0.0`, `roughnessFactor=1.0`. Alpha 1.0 maps to `alphaMode: OPAQUE`, otherwise `BLEND`. `baseColorFactor` values are serialized with exactly 6 decimal places for cross-platform determinism.

**Validation (V37–V42)** — Duplicate material IDs, unknown material references, base_color length/range checks, mesh material consistency, and material ID collisions with other namespaces.

**Conformance fixtures** — Three new test cases (O01–O03) covering minimal material, material with skinning, and invalid material reference.

### v0.7 — UV roles & duplicate key detection

**Schema-only release** — Adds UV role declarations to meshes and UV role references to materials. These are validated but have no effect on GLB output (no `TEXCOORD_n` attributes are emitted).

**UV roles** — Meshes can declare `uv_roles`, a mapping from role names (`albedo`, `detail`, `directional`, `radial`, `decal`, `lightmap`) to UV set tokens (`uv0`, `uv1`, etc.). Materials can declare `uses_uv_roles` to reference roles that their assigned meshes must expose.

**Validation (V43–V47)** — UV role keys must be from the normative vocabulary (V43), set tokens must match `uv<N>` format (V45), material `uses_uv_roles` entries must be from the vocabulary (V47), and materials referencing UV roles must be assigned to meshes that expose those roles (V46).

**Duplicate key detection** — The YAML parser now uses `ruamel.yaml` instead of `pyyaml`, which rejects duplicate mapping keys at parse time (V44).

**Conformance fixtures** — Two new test cases (P01–P02) covering UV roles with schema-only GLB output and invalid UV role references.

### v0.8 — Deterministic UV generation

**UV sets** — Meshes can declare `uv_sets`, a mapping from contiguous keys (`uv0`, `uv1`, ...) to UV generator entries. Each entry specifies a `generator` that deterministically computes `(u, v)` coordinates from the tessellated geometry.

**Five generators** — Each generator is versioned and produces frozen math:
- `planar_xy@1` — `u = x, v = y`. Works on all primitive types.
- `box_project@1` — Per-face projection for boxes. Each of the 6 faces maps two axes to `(u, v)`.
- `sphere_latlong@1` — Index-based latitude/longitude UVs for spheres. `u = lon/32, v = lat/16`.
- `cylindrical@1` — Side seam + polar cap mapping for cylinders.
- `capsule_cyl_latlong@1` — Continuous `v` spanning top hemisphere → cylinder → bottom hemisphere for capsules.

**glTF export** — UV sets are written as `TEXCOORD_0`, `TEXCOORD_1`, etc. in the GLB. UVs are computed on rest-pose positions before any pose deformation, ensuring consistency between standard and baked export paths.

**UV roles integration** — `uv_roles` now requires `uv_sets` to also be present (V53), and each role's `set` must reference a declared UV set key (V54).

**Validation (V50–V55)** — Generator required (V50), generator vocabulary (V51), generator applicability per primitive type (V52), `uv_roles` requires `uv_sets` (V53), role set references declared UV sets (V54), and contiguous UV set key indices (V55).

**Conformance fixtures** — Seven new test cases (P03–P09) covering each generator, symmetry with UVs, and multiple UV sets.

### v0.9 — Wedge primitive & surface keys

**`wedge` primitive** — A right triangular prism formed by extruding a right triangle in the XZ plane along the Y axis. Defined by three positive dimensions (`x`, `y`, `z`), centered on the origin. Emits 18 vertices and 24 indices (8 triangles) across 5 flat-shaded faces: `-z`, `-x`, `slope`, `-y`, `+y`.

**Surface keys** — Canonical identifiers for bounded surface patches produced by a primitive's tessellation. Every generated triangle belongs to exactly one surface. In v0.9, `box` defines 6 surface keys (`+x`, `-x`, `+y`, `-y`, `+z`, `-z`) and `wedge` defines 5 (`-z`, `-x`, `slope`, `-y`, `+y`). Other primitives have no surface keys yet.

**Version gating** — `type: "wedge"` requires `version: "0.9"` or later. The validator rejects wedge primitives in documents declaring an earlier version.

**UV compatibility** — `wedge` participates in the existing UV generator framework. `planar_xy@1` applies to wedge; type-specific generators (e.g., `box_project@1`) do not.

**Conformance fixture** — One new test case (C0901) covering a 2x2x2 wedge with byte-identical GLB verification.

### v0.10 — Preprocessing: params & repeat macros

**Preprocessing stage** — A mandatory preprocessing pass runs on the raw YAML data *before* schema validation. It expands `repeat` macros, substitutes `params` constants, strips the `params` key, and rejects any unresolved tokens. The pipeline becomes: YAML load → preprocess → schema validate → semantic validate → export.

**`params` (compile-time constants)** — A top-level `params` mapping defines named scalar constants (number, string, or boolean). References like `$leg_radius` are substituted with the literal value. Only whole-scalar replacement is supported — string interpolation and expressions are rejected (V60). Param values are not recursively expanded.

**`repeat` macro** — Deterministic duplication of list elements. A `repeat` block specifies `count`, `as` (index variable name), and `body` (a single object template). Index tokens like `${i}` are substituted with the zero-based index — `"${i}"` alone becomes a number, `"picket${i}"` becomes a string. Nested repeats are supported.

**Validation (V56–V66)** — Duplicate YAML keys (V56), unknown fields (V57), non-scalar params (V58), unknown param references (V59), invalid param usage (V60), param type mismatch (V61), invalid repeat count/as/structure (V62–V64), unresolved `${…}` tokens (V65), and identifier collisions after expansion (V66).

**Conformance fixtures** — Three positive test cases (Q01–Q03) covering params, repeat, and combined usage. Eleven negative test cases (Q04–Q14) covering all V56–V66 error codes.

### v0.11 — AABB syntax, box decomposition macro & semantic tags

**AABB box syntax** — Boxes can be defined with `aabb: {min: [x,y,z], max: [x,y,z]}` instead of `dimensions` + `transform`. The preprocessor converts min/max to centered dimensions and a translation. Mutually exclusive with `dimensions`; rejected if combined with `transform` (F115).

**`box_decompose` macro** — A preprocessing macro that decomposes a box span with cutouts into box primitives. Specify `axis` (x|z), `span`, `height`, `thickness`, and a list of `cutouts` (each with `id`, `span`, `bottom`, `top`). The macro emits full-height gap segments between cutouts, plus below/above boxes around each cutout. Supports `tags`, `surface`, and `material` inheritance. Cutout IDs must be valid identifiers (F116); overlapping cutouts are rejected.

**Semantic `tags`** — Primitives can declare `tags: [str, ...]`, an ordered list of non-geometric string labels. Tags from all primitives in a mesh are collected (deduplicated, order-preserving) and exported as `rigy_tags` in the glTF primitive's `extras` object. Version-gated to >= 0.11.

**Conformance fixtures** — Three positive test cases (H110–H112) covering AABB, box_decompose with single cutout, and box_decompose with multiple cutouts. Three negative test cases (F114–F116) covering macro ID collision, AABB with transform, and invalid cutout ID.

### Rigs v0.1 — Scene composition

A separate `.rigs.yaml` format that composes multiple Rigy assets into a single glTF scene. Deterministic, no scripting, no arbitrary transforms.

**Imports** — Alias-based references to `.rigy.yaml` asset files, resolved relative to the `.rigs.yaml` file's directory.

**Scene tree** — A strict tree of instances rooted at a `base` asset. Each child has a unique `id`, references an import alias via `base`, and specifies a `place` block.

**Slots and mounts** — Attachment frames defined by three Rigy anchors (`[p1, p2, p3]`). A **slot** is a target frame on the parent; a **mount** is an origin frame on the child. Both can be referenced by name (via Ricy contract `frame3_sets`) or by explicit anchor triple.

**Placement** — Snaps a child's mount frame onto a parent's slot frame. The transform is computed as `R = Rs * Rrot * inv(Rm)`, `T = (Os + Tnudge) - R * Om`, all in float64.

**Discrete rotation** — `rotate` accepts `0deg`, `90deg`, `180deg`, or `270deg`. Applied about the slot frame's up (Y) axis.

**Nudge** — Translation in slot-frame axes (`east`/`up`/`north`) with unit support: `m`, `cm`, `in`, `ft`. Examples: `20cm`, `1ft`, `0.25m`.

**Validation** — Unknown import aliases, duplicate instance IDs, missing anchors, unresolved named references, and degenerate frame3 constraints.

**Export** — Produces a single GLB with a `scene` root node, instance nodes named by `id`, and mesh deduplication (instances sharing the same alias share the same glTF mesh index). Deterministic output.

**CLI integration** — The `compile` command auto-detects `.rigs.yaml` files and routes to the Rigs pipeline.

## Coordinate System

Aligned with glTF 2.0: **Y-up**, **-Z forward**, **right-handed**. All units in meters.

## Spec

See [`spec/rigy_spec_v0.1-rc2_with_rigs_roadmap.md`](spec/rigy_spec_v0.1-rc2_with_rigs_roadmap.md) for the full specification, [`spec/rigy_spec_v0.2-rc2.md`](spec/rigy_spec_v0.2-rc2.md) for the v0.2 composition spec, [`spec/rigy_spec_v0.3-rc2.md`](spec/rigy_spec_v0.3-rc2.md) for the v0.3 weight maps spec, [`spec/rigy_spec_v0.4-rc3.md`](spec/rigy_spec_v0.4-rc3.md) for the v0.4 conformance and determinism spec, [`spec/rigy_spec_v0.5-amendment-rc2.md`](spec/rigy_spec_v0.5-amendment-rc2.md) for the v0.5 DQS amendment, [`spec/rigy_spec_v0.6-amendment-rc2.md`](spec/rigy_spec_v0.6-amendment-rc2.md) for the v0.6 materials amendment, [`spec/rigy_spec_v0.7-amendment-rc4.md`](spec/rigy_spec_v0.7-amendment-rc4.md) for the v0.7 UV roles amendment, [`spec/rigy_spec_v0.8-amendment-rc2.md`](spec/rigy_spec_v0.8-amendment-rc2.md) for the v0.8 UV generation amendment, [`spec/rigy_spec_v0.9-amendment-rc4.md`](spec/rigy_spec_v0.9-amendment-rc4.md) for the v0.9 wedge primitive amendment, [`spec/rigy_spec_v0.10_amendment_rc1.md`](spec/rigy_spec_v0.10_amendment_rc1.md) for the v0.10 preprocessing amendment, [`spec/rigy_spec_v0.11-amendment-rc2.md`](spec/rigy_spec_v0.11-amendment-rc2.md) for the v0.11 AABB/macros/tags amendment, and [`spec/rigs_spec_v0.1-rc1.md`](spec/rigs_spec_v0.1-rc1.md) for the Rigs v0.1 scene composition spec.

## Development

```bash
uv sync
uv run pytest
uv run ruff check src/
```
