# Appendix B: Normative Conformance Fixtures

This appendix embeds the current v0.11 conformance inputs verbatim. Implementations MUST treat the contents below as the normative source for these fixtures.

## I01 — arm_weight_maps.rigy.yaml

```yaml
version: "0.11"
units: meters
coordinate_system:
  up: Y
  forward: -Z
  handedness: right
tessellation_profile: v0_1_default
meshes:
- id: arm_mesh
  primitives:
  - type: capsule
    id: upper_arm
    dimensions:
      radius: 0.05
      height: 0.25
    transform:
      translation:
      - 0
      - 1.0
      - 0
  - type: capsule
    id: forearm
    dimensions:
      radius: 0.04
      height: 0.25
    transform:
      translation:
      - 0
      - 0.65
      - 0
armatures:
- id: arm_armature
  bones:
  - id: shoulder
    parent: none
    head:
    - 0
    - 1.15
    - 0
    tail:
    - 0
    - 0.9
    - 0
  - id: elbow
    parent: shoulder
    head:
    - 0
    - 0.9
    - 0
    tail:
    - 0
    - 0.65
    - 0
  - id: wrist
    parent: elbow
    head:
    - 0
    - 0.65
    - 0
    tail:
    - 0
    - 0.5
    - 0
bindings:
- mesh_id: arm_mesh
  armature_id: arm_armature
  weights:
  - primitive_id: upper_arm
    bones:
    - bone_id: shoulder
      weight: 1.0
  - primitive_id: forearm
    bones:
    - bone_id: elbow
      weight: 1.0
  weight_maps:
  - primitive_id: upper_arm
    gradients:
    - axis: y
      range:
      - 0.88
      - 1.02
      from:
      - bone_id: elbow
        weight: 1.0
      to:
      - bone_id: shoulder
        weight: 1.0
```

---

## E01 — humanoid.rigy.yaml

```yaml
version: "0.11"
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
  name: Humanoid
  primitives:
  - type: capsule
    id: torso
    dimensions:
      radius: 0.15
      height: 0.3
    transform:
      translation:
      - 0
      - 1.15
      - 0
    material: skin
  - type: sphere
    id: head
    dimensions:
      radius: 0.12
    transform:
      translation:
      - 0
      - 1.6
      - 0
    material: skin
  - type: capsule
    id: legL_upper
    dimensions:
      radius: 0.07
      height: 0.25
    transform:
      translation:
      - 0.12
      - 0.65
      - 0
    material: skin
  - type: capsule
    id: legL_lower
    dimensions:
      radius: 0.05
      height: 0.28
    transform:
      translation:
      - 0.12
      - 0.24
      - 0
    material: skin
armatures:
- id: humanoid_armature
  name: HumanoidArmature
  bones:
  - id: root
    parent: none
    head:
    - 0
    - 0.9
    - 0
    tail:
    - 0
    - 0.95
    - 0
    roll: 0.0
  - id: spine
    parent: root
    head:
    - 0
    - 0.95
    - 0
    tail:
    - 0
    - 1.4
    - 0
    roll: 0.0
  - id: neck
    parent: spine
    head:
    - 0
    - 1.4
    - 0
    tail:
    - 0
    - 1.6
    - 0
    roll: 0.0
  - id: legL_upper
    parent: root
    head:
    - 0.12
    - 0.9
    - 0
    tail:
    - 0.12
    - 0.48
    - 0
    roll: 0.0
  - id: legL_lower
    parent: legL_upper
    head:
    - 0.12
    - 0.48
    - 0
    tail:
    - 0.12
    - 0.05
    - 0
    roll: 0.0
bindings:
- mesh_id: humanoid_mesh
  armature_id: humanoid_armature
  weights:
  - primitive_id: torso
    bones:
    - bone_id: spine
      weight: 1.0
  - primitive_id: head
    bones:
    - bone_id: neck
      weight: 1.0
  - primitive_id: legL_upper
    bones:
    - bone_id: legL_upper
      weight: 1.0
  - primitive_id: legL_lower
    bones:
    - bone_id: legL_lower
      weight: 1.0
symmetry:
  mirror_x:
    prefix_from: legL_
    prefix_to: legR_
```

---

**End of Appendix B**
