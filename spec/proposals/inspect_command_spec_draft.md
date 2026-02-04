# Rigy Compiler Tooling: `rigy inspect`

*Status: Compiler / tooling feature (non-language, non-normative)*
*Applies to: Rigy v0.9+ (surface keys required for face diagnostics)*

## 1. Purpose

`rigy inspect` provides **numeric, structural geometry diagnostics** for a Rigy asset **without rendering**.

It exposes measurable properties of the compiled geometry to support:

* debugging and validation
* CI and automated checks
* LLM-driven authoring loops
* early detection of gross spatial or orientation errors

This command is **observational only** and MUST NOT affect validation results or exported GLB bytes.

---

## 2. Evaluation Pipeline (Normative for This Tool)

Unless otherwise specified, `rigy inspect` MUST evaluate the asset through the following stages:

```
YAML load
→ preprocess (v0.10+)
→ parse
→ expand symmetry
→ validate
→ tessellate
```

Notes:

* Inspection operates on **tessellated geometry**, not authored primitives.
* Skinning and pose evaluation are **not applied by default**.
* All reported geometry is in **asset space** (after primitive transforms and symmetry, before instancing by composition).

If future flags introduce skinning or pose evaluation, they MUST be explicit.

---

## 3. Command Surface

```bash
rigy inspect <input.rigy.yaml>
```

### Common Options

```bash
--format json            # machine-readable output
--expanded               # also emit expanded YAML (equivalent to --emit-expanded-yaml)
--primitive <id>         # restrict output to selected primitive(s)
--pairwise-gaps          # compute AABB-based gaps/overlaps
--intent-checks          # evaluate external intent checks (if provided)
--fail-on-intent         # non-zero exit if any intent check fails
```

---

## 4. Output: Text Mode

### 4.1 Model Summary

* Rigy version
* mesh count
* primitive count (post-symmetry)
* asset-space bounds (AABB: min/max)

### 4.2 Per-Primitive Diagnostics

For each selected primitive:

* `id`
* `type`
* `material` (resolved ID or implicit default)
* **asset-space AABB**

  * `min: [x,y,z]`
  * `max: [x,y,z]`
* derived:

  * `center: (min + max) / 2`
  * `extents: (max - min)`

These values are computed from the tessellated vertex buffer in float64.

---

## 5. Face Diagnostics (Surface-Key Primitives Only)

For primitives that define **surface keys** (e.g., `box`, `wedge`):

For each surface:

* `primitive_id`
* `surface_key`
* **face normal** (unit-length, asset-space)

  * Derived from canonical face winding / flat normals
* **face plane equation** (optional but recommended):

  * `n · x + d = 0`
  * where:

    * `n` = face normal
    * `d = -dot(n, p0)` for any vertex `p0` on that face
* Optionally include:

  * one canonical point on the face (for debugging)

Notes:

* Face diagnostics are only emitted for planar faces.
* No averaging or smoothing is permitted.
* All calculations are float64.

---

## 6. Pairwise Gap / Overlap Diagnostics (Optional)

Enabled with `--pairwise-gaps`.

### 6.1 Scope

* Computed **only using per-primitive AABBs**
* No triangle–triangle or mesh-distance calculations
* By default, only evaluated for:

  * selected primitives (`--primitive`)
  * or explicitly paired sets (implementation choice)

### 6.2 Metrics

For each evaluated primitive pair:

* **axis-separated gaps**:

  * `gap_x`, `gap_y`, `gap_z`
  * Positive = separation
  * Negative = overlap
* **overall gap / overlap**:

  * `max(gap_x, gap_y, gap_z)`

This is sufficient to detect:

* unintended separation
* unintended penetration
* gross spatial misalignment

---

## 7. JSON Output Mode

When `--format json` is specified, output MUST conform to a stable, machine-readable structure.

### 7.1 Top-Level Shape

```json
{
  "summary": {
    "rigy_version": "0.11",
    "mesh_count": 1,
    "primitive_count": 12,
    "bounds": {
      "min": [x,y,z],
      "max": [x,y,z]
    }
  },
  "primitives": [
    {
      "id": "p0",
      "type": "box",
      "material": "wall_mat",
      "aabb": { "min": [...], "max": [...] },
      "center": [...],
      "extents": [...]
    }
  ],
  "faces": [
    {
      "primitive_id": "p0",
      "surface_key": "+z",
      "normal": [...],
      "plane": { "n": [...], "d": value }
    }
  ],
  "pairs": [
    {
      "a": "p0",
      "b": "p1",
      "gap": {
        "x": value,
        "y": value,
        "z": value,
        "overall": value
      }
    }
  ],
  "checks": []
}
```

### 7.2 Rules

* All vectors are fixed-length numeric arrays
* Field names are stable
* Absent sections MAY be omitted if not requested
* Ordering of arrays MUST be deterministic

---

## 8. Intent Checks (External, Optional)

If `--intent-checks` is provided and an intent definition is available:

* Intent checks are evaluated **after inspection metrics are computed**
* They MAY reference:

  * primitive IDs
  * AABBs
  * face normals / planes
  * gap metrics
* Intent checks:

  * MUST NOT modify geometry
  * MUST NOT affect validation
  * MUST NOT affect export output

Results are reported under `checks[]` with:

* check ID
* measured values
* pass/fail status

Intent checks are **tooling-level contracts**, not Rigy language semantics.

---

## 9. Exit Codes

* `0` — inspection completed (warnings allowed)
* `1` — parse or validation failure
* `2` — inspect configuration / argument error
* `3` — intent check failure with `--fail-on-intent`

---

## 10. Determinism and Scope

* `rigy inspect` MUST NOT:

  * change GLB output bytes
  * influence validation results
  * introduce new language semantics
* All reported metrics are derived from the same geometry used for export.
* Formatting and presentation are non-semantic.

---

## 11. Summary

`rigy inspect` provides a **domain-agnostic, numeric introspection layer** over Rigy’s compiled geometry.

It makes geometry:

* measurable instead of visual
* assertable instead of subjective
* debuggable by humans and tools
* usable in automated and LLM-driven workflows

Without expanding Rigy’s scope beyond being a deterministic geometry compile target.
