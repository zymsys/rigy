# Rigy Tooling: `geometry_checks` (v1)

*Status: Compiler / tooling feature (non-language, non-normative)*
*Goal: Optional, read-only geometric assertions to catch “valid-but-wrong” assemblies.*

## 1. Purpose

`geometry_checks` provides optional, declarative checks over compiled geometry to detect **spatial/orientation mismatches** and **unexpected clearances/penetrations** *without rendering*.

Checks are evaluated over the same computed metrics produced by `rigy inspect` (AABBs, face normals/planes, optional pairwise AABB gaps). They:

* MUST be read-only
* MUST NOT modify geometry
* MUST NOT affect exported GLB bytes (unless the user opts into a “fail” policy that only changes the process exit status)

## 2. Non-goals

* No new primitives or macros
* No snapping, correction, or geometry mutation
* No participation in Rigy conformance/determinism
* No replacement for semantic/domain validation in upstream authoring tools

## 3. Schema

`geometry_checks` is an optional top-level block in a Rigy document **or** may be supplied externally (e.g., `--geometry-checks <file>`). This spec defines the content model, not the transport.

```yaml
geometry_checks:
  version: 1
  default_tolerance: 0.001   # optional, > 0
  checks:
    - id: check_0
      type: point_order
      a: { primitive_id: part_a, point: max_y }
      b: { primitive_id: part_b, point: max_y }
      relation: gt
      min_delta: 0.2
```

### 3.1 Fields

* `geometry_checks` (optional)

  * `version` (required) — integer, must be `1` for this spec
  * `default_tolerance` (optional float, > 0, default `0.001`)
  * `checks` (required if `geometry_checks` exists) — non-empty list

Each check:

* `id` (required) — unique identifier within `checks`
* `type` (required) — string in the v1 vocabulary
* type-specific fields (see §6)

### 3.2 Identifier Rules

* `checks[].id` MUST be unique within the list
* `primitive_id` references MUST refer to a resolved primitive ID after preprocessing/symmetry

## 4. Evaluation Stage

`geometry_checks` MUST be evaluated only if explicitly enabled (e.g., `rigy inspect --geometry-checks` or `rigy compile --geometry-checks`).

When enabled, checks MUST run:

```
preprocess → parse → expand symmetry → validate → tessellate → compute inspect metrics → evaluate checks
```

Defaults:

* Checks are evaluated on **asset-space**, **rest**, **pre-skin** tessellated geometry (same as `rigy inspect` default).
* If future tooling adds “post-skin” or “pose” inspection, it MUST be selected explicitly, and checks must state which evaluation space they target.

## 5. Results Model

Check evaluation produces **results**, not Rigy validation errors.

Each check yields a result object containing:

* `id`
* `type`
* `status`: `pass | fail`
* `measured`: type-specific measured values
* `expected`: thresholds/ranges used
* optional `notes`

The compiler/tool MUST NOT treat a failed check as a parse/validation error by default.

## 6. Check Types (v1)

### 6.1 `coplanar_faces`

Asserts two planar faces are coplanar within a maximum distance.

```yaml
- id: face_coplanar
  type: coplanar_faces
  a: { primitive_id: p0, face: "+z" }
  b: { primitive_id: p1, face: "slope" }
  max_distance: 0.03
```

Rules:

* `face` MUST be a valid surface key for the referenced primitive type (see §7)
* Metric:

  * Let plane `Pa` be `(n_a, d_a)` for face `a`
  * Sample a finite set of points on face `b` (see Sampling)
  * Compute `dist_i = abs(n_a · p_i + d_a)` (point-to-plane distance)
  * `measured.max_distance = max(dist_i)`
* Pass if `measured.max_distance <= max_distance`

Sampling (deterministic):

* For `box` and `wedge` (flat-shaded, surface-keyed), the sample set MUST be the **emitted face vertices** for that surface, in canonical vertex emission order.

### 6.2 `gap_axis`

Asserts AABB separation along a single axis is within `[min, max]`.

```yaml
- id: axis_gap_ok
  type: gap_axis
  a: { primitive_id: p0 }
  b: { primitive_id: p1 }
  axis: z
  min: -0.05
  max: 0.10
```

Rules:

* Compute asset-space AABBs for `a` and `b`
* Compute signed axis gap `g`:

  * If `A.max[axis] < B.min[axis]`: `g = B.min - A.max` (positive gap)
  * Else if `B.max[axis] < A.min[axis]`: `g = A.min - B.max` (positive gap)
  * Else: `g = -overlap` where `overlap = min(A.max, B.max) - max(A.min, B.min)` (negative means penetration)
* Pass if `min <= g <= max`

### 6.3 `point_order`

Asserts one derived scalar value is above/below another, optionally with a minimum delta.

```yaml
- id: order_ok
  type: point_order
  a: { primitive_id: p0, point: max_y }
  b: { primitive_id: p1, point: max_y }
  relation: gt
  min_delta: 0.2
```

Allowed `point` values:

* `min_x|max_x|min_y|max_y|min_z|max_z|center_x|center_y|center_z`

Relations:

* `gt`, `ge`, `lt`, `le`, `eq`

Semantics:

* Compute scalar `A` from `a`
* Compute scalar `B` from `b`
* Evaluate relation, with optional `min_delta`:

  * For `gt`: require `A > B + min_delta` (if `min_delta` present, else `A > B`)
  * For `ge`: require `A >= B + min_delta` (if present)
  * For `lt/le`: analogous
  * For `eq`: require `abs(A - B) <= tolerance` where `tolerance` = check’s `tolerance` or `default_tolerance`

### 6.4 `normal_alignment`

Asserts a face normal aligns to a target direction within an angular tolerance.

```yaml
- id: normal_ok
  type: normal_alignment
  a: { primitive_id: p0, face: "+x" }
  target_axis: [1, 0, 0]
  max_angle_deg: 30
```

Rules:

* `target_axis` MUST be a finite non-zero vector
* Face normal `n` MUST be the asset-space face normal from surface-key diagnostics
* Normalize `t = normalize(target_axis)`
* Compute `angle = acos(clamp(dot(n, t), -1, 1))` in radians, then convert to degrees
* Pass if `angle <= max_angle_deg`

Reported:

* `measured.angle_deg`

## 7. Surface Keys

Checks that reference `face` (`coplanar_faces`, `normal_alignment`) may only be used with primitives that define surface keys.

For v1:

* `box`: `+x`, `-x`, `+y`, `-y`, `+z`, `-z`
* `wedge`: `-z`, `-x`, `slope`, `-y`, `+y`

If a primitive type does not define surface keys, referencing `face` is a **check definition error** (see §8).

## 8. Errors vs Failures

### 8.1 Check Definition Errors (Tooling Errors)

The tool MUST report a **definition error** (and typically exit non-zero) if:

* duplicate `checks[].id`
* unknown `type`
* referenced `primitive_id` does not exist
* invalid `face` for the primitive type
* invalid numeric bounds (NaN/Infinity, negative tolerances, min > max, etc.)
* invalid enum values (axis, relation, point)

These are configuration problems, not “failed checks.”

### 8.2 Check Failures (Diagnostic Results)

A check failure means:

* the check was well-defined
* the measured value was outside thresholds/ranges

Failures are reported in `checks[]` results and do not affect GLB output.

## 9. CLI / Tool Behavior

Suggested CLI integration (names may vary):

* `rigy inspect <file> --geometry-checks`

  * evaluates embedded `geometry_checks` if present

* `rigy inspect <file> --geometry-checks <checks.yaml>`

  * evaluates an external checks file

* `--fail-on-checks`

  * if set, any check result with `status: fail` causes non-zero exit

### Exit Codes (recommended)

* `0` — inspection completed; all checks passed or checks not enabled
* `1` — Rigy parse/validation failure
* `2` — tooling/config error (including check definition errors)
* `3` — checks enabled and at least one check failed with `--fail-on-checks`

## 10. JSON Output

When `rigy inspect --format json` is used, check results MUST appear in the top-level `checks` array:

```json
"checks": [
  {
    "id": "normal_ok",
    "type": "normal_alignment",
    "status": "fail",
    "measured": { "angle_deg": 42.1 },
    "expected": { "max_angle_deg": 30 }
  }
]
```

Ordering MUST be deterministic (same order as `geometry_checks.checks`).

## 11. Determinism and Conformance

* `geometry_checks` MUST NOT affect:

  * primitive ordering
  * transforms
  * tessellation
  * materials
  * skinning/export data
* A conforming Rigy implementation’s GLB output MUST be byte-identical regardless of check pass/fail.
* `geometry_checks` is a tooling feature and is not part of Rigy conformance requirements.
