# Appendix A: Conformance Test Example

**Input** (`A01_single_bone_identity.rigy.yaml`):

```yaml
version: "0.11"

meshes:
  - id: cube
    primitives:
      - id: body
        type: box
        dimensions:
          width: 1.0
          height: 1.0
          depth: 1.0

armatures:
  - id: skeleton
    bones:
      - id: root
        head: [0, 0, 0]
        tail: [0, 1, 0]
        parent: none

bindings:
  - mesh_id: cube
    armature_id: skeleton
    weights:
      - primitive_id: body
        bones:
          - bone_id: root
            weight: 1.0
```

**Expected behavior:**

* 24 vertices, 36 indices (box tessellation)
* All vertices bound to joint 0 (root) with weight 1.0
* JOINTS_0: all `[0, 0, 0, 0]`
* WEIGHTS_0: all `[1.0, 0.0, 0.0, 0.0]`
* One inverse bind matrix: identity (root bone at origin)
* Byte-identical GLB on every run

---

**End of Appendix A**
