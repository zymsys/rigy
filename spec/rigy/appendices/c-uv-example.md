# Appendix C: Complete UV Example

This example demonstrates UV roles, UV sets, and material UV role references.

```yaml
version: "0.11"

materials:
  nickel:
    base_color: [0.75, 0.75, 0.78, 1.0]
    uses_uv_roles: [radial, detail]

meshes:
  - id: coin
    primitives:
      - id: body
        type: cylinder
        dimensions:
          radius: 0.02
          height: 0.002
    uv_sets:
      uv0: { generator: cylindrical@1 }
      uv1: { generator: planar_xy@1 }
    uv_roles:
      radial: { set: uv0 }
      detail: { set: uv1 }

bindings: []
```

**Explanation:**

1. **Material `nickel`** declares it uses UV roles `radial` and `detail`
2. **Mesh `coin`** declares two UV sets:
   - `uv0` using the `cylindrical@1` generator
   - `uv1` using the `planar_xy@1` generator
3. **UV role mapping**:
   - `radial` maps to `uv0` (cylindrical coordinates for the coin face)
   - `detail` maps to `uv1` (planar XY for overlay textures)

**Export result:**

- `TEXCOORD_0` contains cylindrical UV coordinates
- `TEXCOORD_1` contains planar XY UV coordinates
- The material references are validated against the exposed UV roles

---

**End of Appendix C**
