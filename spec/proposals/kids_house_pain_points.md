# Kids House: Spec Pain Points

1. **Wedge rotation is hard to reason about.** The wedge's default orientation (right angle at `-hx, -hz` in XZ plane, extruded along Y) is mathematically precise but unintuitive for the common use case of gable fills. The spec provides a "Common Rotation Recipes" table, but gable construction still requires careful computation of 4 distinct rotation+translation combos for left/right halves of front/back ends. A "gable fill" example showing all 4 wedges for a symmetric gable (not just one) would help.

2. **`box_decompose` `mesh` field ambiguity.** The spec syntax example includes a `mesh` field, but the implementation ignores it since the macro is already placed inline inside a mesh's primitives list. The spec should clarify whether `mesh` is required, optional, or deprecated.

3. **`box_decompose` `offset` semantics require careful reading.** The parameter displaces the wall *centerline*, not the outer face. For architectural modeling where you think in terms of "front wall at Z=-2", you have to mentally account for half-thickness offset. Documenting this as "centerline position" more prominently would help.

4. **AABB + material interaction is underdocumented.** The spec says AABB can't coexist with transforms, but doesn't explicitly say `material` is allowed alongside AABB. It works fine (material is on the primitive, not on the transform), but could cause author hesitation.

5. **No "isosceles triangle" primitive.** Building a symmetric gable requires 2 right-triangle wedges per end (4 total for front+back), each with its own rotation. A single `gable` or `isosceles_prism` primitive would reduce a common 4-primitive task to 2. However, `box_decompose` + wedge composition does work -- it's just verbose.

6. **Roof/gable ridge axis alignment is easy to get wrong.** The roof panels (tilted boxes) and gable end caps (wedges) must share the same ridge line, but the spec's "Common Rotation Recipes" table only describes individual wedge orientations, not how they relate to the roof panels. In my first iteration, the roof ridge ran along X (rotation about X) while the gable apexes traced a line along Z -- perpendicular and geometrically inconsistent. `rigy inspect` was essential for catching this: comparing the gable AABB apex coordinates against the roof panel AABBs made the mismatch obvious. The spec should emphasize that the roof rotation axis and the gable ridge axis must be the same axis, or provide an integrated "gable roof" recipe that covers both roof panels and gable caps together.

7. **`rigy inspect` is underadvertised.** The `rigy inspect` command with per-primitive AABBs, face normals, and pairwise gaps is extremely useful for spatial debugging -- it caught the ridge-axis misalignment that visual inspection of the renders missed (the first renders looked plausible from both camera angles). Consider mentioning `inspect` in the spec's "Common Rotation Recipes" as a verification step.
