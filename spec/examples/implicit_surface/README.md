# Implicit Surface Examples

Practical advice for authoring `implicit_surface` primitives in Rigy v0.13.

## Field type choice

| Field | Falloff | Support radius | Best for |
|-------|---------|----------------|----------|
| `metaball_sphere@1` | Quadratic `(1 - r/R)²` | 1× radius | Compact blobby shapes, organic forms |
| `metaball_capsule@1` | Quadratic along segment | 1× radius | Elongated limbs, smooth bridges |
| `sdf_sphere@1` | Linear | 2× radius | Subtractive carving (chips, gouges) |
| `sdf_capsule@1` | Linear along segment | 2× radius | Subtractive grooves, channels |

**`metaball_*`** fields are the workhorse for additive shape-building. Their
quadratic falloff keeps shapes compact and the iso threshold intuitive
(0.15–0.25 is a good starting range).

**`sdf_*`** fields extend to 2× their radius and the iso threshold behaves
very differently — values that work for metaball will produce thin shells or
nothing at all with SDF. SDF fields shine in subtractive roles (see
E-SIG-02, E-SIG-03) where their linear falloff gives clean, predictable cuts.

## Shaping curved / kidney forms

Placing two equal spheres on a straight line produces a **peanut**, not a bean.
To get an organic curved shape:

1. **Arrange spheres along an arc**, not a line. The concavity emerges
   naturally from the inside of the arc — no subtract ops needed for the
   basic curve.
2. **Taper the radii** from one end to the other for asymmetry (fat end →
   narrow end).
3. **Use 5+ spheres** for smooth outer contours. With only 3, visible saddle
   dips appear between spheres on the convex side — this is inherent to
   metaball blending and difficult to fix without adding more sources.
4. **Add a subtract sphere** at the concavity to deepen it if the arc alone
   isn't enough (see E-SIG-01).

## Tuning the iso threshold

- **Lower iso** → inflates the surface outward, smooths saddle dips between
  metaballs, but may also inflate over concavities you want to keep.
- **Higher iso** → tighter surface that reveals individual sphere shapes more.
- When combining add and subtract ops, lower iso first to smooth the additive
  shape, then adjust subtract strength to recover concavities.

## Controlling bulge and proportion

- The **position** of arc spheres controls the silhouette curve. Move them
  toward the center of mass to reduce back-bulge; move them outward for more
  curvature.
- The **radius** of middle spheres controls how much the back "humps out."
  Smaller middle spheres let the tips dominate; larger ones fill the bridge
  but can create a visible bump.
- The **strength** parameter scales a sphere's field contribution without
  changing its support radius. Boosting strength on a bridge sphere inflates
  that area but can create a hump — prefer adjusting iso instead for uniform
  inflation.

## Practical workflow

1. Start with the overall silhouette: place spheres, pick an iso, compile and
   render.
2. **Render from multiple camera angles** — the default 3/4 view hides
   problems that are obvious from the front (XY plane) or top (XZ plane).
3. Change **one parameter at a time** when fine-tuning. Metaball fields
   interact nonlinearly, so changing two things at once makes it hard to
   attribute what helped and what hurt.
4. Use `f3d model.glb --output render.png --resolution 800,600` for quick
   CLI renders, or open in Blender for interactive inspection of specific
   viewing axes.

## Domain and grid sizing

- The AABB must fully enclose the shape with some margin — any surface that
  extends past the boundary gets clipped.
- Grid resolution controls mesh quality. Higher values give smoother surfaces
  but cost memory (`nx × ny × nz ≤ 2,000,000`). Start coarse (30–50 per
  axis) for iteration, increase for final output.
- Match grid density to the AABB proportions. A flat bean (short in Z) should
  have fewer Z cells than X or Y cells.
