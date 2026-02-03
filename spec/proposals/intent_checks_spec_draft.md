# Draft Spec: Intent Checks for Geometric Feedback (Rigy v0.12 proposal)

## 1. Purpose

This proposal adds optional geometric intent checks to catch "valid-but-wrong" assemblies (e.g., rotated roofs, misaligned gables) without adding new primitives.

Intent checks are diagnostics over transformed geometry.

## 2. Non-goals

- No changes to primitive vocabulary.
- No changes to tessellation outputs.
- No snapping or automatic geometry correction.
- No impact on deterministic GLB bytes.

## 3. Top-level schema

```yaml
intent_checks:
  default_tolerance: 0.01
  checks:
    - id: ridge_above_eave
      type: point_order
      a: { primitive_id: roof_front, point: max_y }
      b: { primitive_id: front_wall_gap_0, point: max_y }
      relation: gt
      min_delta: 0.2
```

### 3.1 Fields

- `intent_checks` (optional)
  - `default_tolerance` (optional float, > 0, default `0.001`)
  - `checks` (required non-empty list if `intent_checks` is present)

Each check:
- `id` (required unique identifier)
- `type` (required string)
- type-specific fields

## 4. Evaluation stage

Intent checks MUST run after:
1. preprocessing expansion
2. parsing
3. semantic validation
4. transform application

and before export finalization.

Checks MUST be read-only and MUST NOT modify scene state.

## 5. Check types (v1)

## 5.1 `coplanar_faces`

Asserts two primitive faces are coplanar within tolerance.

```yaml
- id: roof_front_matches_gable_front
  type: coplanar_faces
  a: { primitive_id: roof_front, face: "+z" }
  b: { primitive_id: gable_front_left, face: "slope" }
  max_distance: 0.03
```

Rules:
- `face` MUST be valid for primitive type.
- Distance metric: max signed point-to-plane distance of sampled face vertices.
- Pass if distance <= `max_distance`.

## 5.2 `gap_axis`

Asserts AABB separation along one axis falls in a range.

```yaml
- id: roof_overhang_z
  type: gap_axis
  a: { primitive_id: roof_front }
  b: { primitive_id: front_wall_gap_0 }
  axis: z
  min: 0.0
  max: 0.35
```

Rules:
- Compute world AABBs for both primitives.
- Compute signed gap/overlap on axis (`<0` overlap, `>0` gap).
- Pass if value in `[min, max]`.

## 5.3 `point_order`

Asserts one derived scalar point value is above/below another.

```yaml
- id: ridge_above_eave
  type: point_order
  a: { primitive_id: roof_front, point: max_y }
  b: { primitive_id: front_wall_gap_0, point: max_y }
  relation: gt
  min_delta: 0.2
```

Allowed points:
- `min_x|max_x|min_y|max_y|min_z|max_z|center_x|center_y|center_z`

Relations:
- `gt`, `ge`, `lt`, `le`, `eq`

## 5.4 `normal_alignment`

Asserts a face normal aligns to a target axis within angular tolerance.

```yaml
- id: roof_front_slopes_pos_x
  type: normal_alignment
  a: { primitive_id: roof_front, face: "+x" }
  target_axis: [1, 0, 0]
  max_angle_deg: 30
```

Rules:
- `target_axis` MUST be finite non-zero vector.
- Angle from world face normal to normalized `target_axis` must be <= `max_angle_deg`.

## 6. Error model additions

### 6.1 Hard validation errors

- `V67`: duplicate intent check IDs
- `V68`: unknown primitive ID referenced
- `V69`: invalid face key for primitive type
- `V70`: invalid numeric bounds/tolerance/range
- `V71`: unknown intent check type

### 6.2 Warnings (default behavior)

- `W10`: `coplanar_faces` failed
- `W11`: `gap_axis` out of range
- `W12`: `point_order` failed
- `W13`: `normal_alignment` failed

Warnings MUST include:
- check `id`
- measured value(s)
- threshold/range

## 7. CLI behavior

Default:
- Emit warnings and continue compilation.

Optional strict mode:
- `--fail-on-intent` promotes `W10..W13` to fatal failure.

## 8. Determinism contract

A conforming implementation MUST produce byte-identical GLB output regardless of whether intent checks pass or fail (in non-strict mode).

Intent checks MUST NOT alter:
- primitive ordering
- transforms
- tessellation
- material assignment
- skinning/export data

## 9. Surface key usage

`coplanar_faces` and `normal_alignment` may use `face` only where surface keys are defined.

For v0.12 scope:
- `box`: `+x`, `-x`, `+y`, `-y`, `+z`, `-z`
- `wedge`: `-z`, `-x`, `slope`, `-y`, `+y`

## 10. Example for house roof/gable validation

```yaml
intent_checks:
  default_tolerance: 0.02
  checks:
    - id: ridge_above_eave
      type: point_order
      a: { primitive_id: roof_front, point: max_y }
      b: { primitive_id: front_wall_gap_0, point: max_y }
      relation: gt
      min_delta: 0.15

    - id: roof_depth_reasonable
      type: gap_axis
      a: { primitive_id: roof_front }
      b: { primitive_id: back_wall }
      axis: z
      min: -2.5
      max: 2.5

    - id: front_gable_plane_touch
      type: coplanar_faces
      a: { primitive_id: gable_front_left, face: "+y" }
      b: { primitive_id: gable_front_right, face: "-y" }
      max_distance: 0.03
```

## 11. Why this helps

This catches common assembly mistakes early:
- 90-degree roof orientation mismatch
- inverted or misplaced gable faces
- unexpected roof-wall gaps

without increasing primitive complexity.
