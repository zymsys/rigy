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
from rigy.parser import parse_yaml
from rigy.symmetry import expand_symmetry
from rigy.validation import validate
from rigy.exporter import export_gltf
from pathlib import Path

spec = parse_yaml("humanoid.rigy.yaml")
spec = expand_symmetry(spec)
validate(spec)
export_gltf(spec, Path("humanoid.glb"))
```

## Example

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

## What's Implemented (v0.1)

**Primitives** — `box`, `sphere`, `capsule`, `cylinder` with fixed tessellation (`v0_1_default` profile), per-primitive transforms, and symbolic material references.

**Armatures** — Bone trees with head/tail positioning, roll, and parent hierarchy. Validated for cycles and zero-length bones.

**Skinning** — Primitive-level weight assignment (all vertices in a primitive get identical weights). Weights are normalized and capped to 4 bones per primitive for glTF compatibility.

**Bindings** — Connect a mesh to an armature with per-primitive bone weights. Each mesh may appear in only one binding.

**Symmetry** — Compile-time mirror-X expansion via prefix substitution. Deterministic and applied before validation.

**Validation** — Unique IDs, acyclic bone hierarchies, positive dimensions, weight range checks, reference integrity, unknown field rejection (strict mode).

**Export** — glTF 2.0 / GLB with positions, normals, indices, skinning joints/weights, and inverse bind matrices.

## Coordinate System

Aligned with glTF 2.0: **Y-up**, **-Z forward**, **right-handed**. All units in meters.

## Spec

See [`spec/rigy_spec_v0.1-rc2_with_rigs_roadmap.md`](spec/rigy_spec_v0.1-rc2_with_rigs_roadmap.md) for the full specification including the v0.2+ roadmap (composition, contracts, scene DSL).

## Development

```bash
uv sync
uv run pytest
uv run ruff check src/
```
