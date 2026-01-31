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
```

### Library

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

## Examples

### Humanoid with symmetry (v0.1)

A minimal humanoid with symmetry-expanded legs (`tests/fixtures/humanoid.rigy.yaml`):

```yaml
version: "0.1"
units: meters
coordinate_system:
  up: Y
  forward: -Z
  handedness: right
tessellation_profile: v0_1_default

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

The compiler expands `symmetry` before validation, producing mirrored `legR_*` primitives, bones, and weights automatically.

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

## What's Implemented

### v0.1 — Rigged primitives

**Primitives** — `box`, `sphere`, `capsule`, `cylinder` with fixed tessellation (`v0_1_default` profile), per-primitive transforms, and symbolic material references.

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

## Coordinate System

Aligned with glTF 2.0: **Y-up**, **-Z forward**, **right-handed**. All units in meters.

## Spec

See [`spec/rigy_spec_v0.1-rc2_with_rigs_roadmap.md`](spec/rigy_spec_v0.1-rc2_with_rigs_roadmap.md) for the full specification and [`spec/rigy_spec_v0.2-rc2.md`](spec/rigy_spec_v0.2-rc2.md) for the v0.2 composition spec.

## Development

```bash
uv sync
uv run pytest
uv run ruff check src/
```
