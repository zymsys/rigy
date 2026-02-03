# Draft Spec: `rigy inspect`

## Goal

Provide fast, numeric geometry diagnostics without rendering.

## Command surface

```bash
rigy inspect <input.rigy.yaml>
```

Common options:

```bash
rigy inspect <input> --format json
rigy inspect <input> --expanded
rigy inspect <input> --primitive roof_front
rigy inspect <input> --pairwise-gaps
rigy inspect <input> --intent-checks
```

## Output (text mode)

1. Model summary
- version
- mesh count / primitive count
- world bounds

2. Per-primitive diagnostics
- primitive id/type/material
- world AABB: `min/max`
- center
- extents

3. Face diagnostics (for primitives with surface keys)
- face key
- world face normal
- face plane equation

4. Pair diagnostics (optional)
- nearest gap/overlap values between selected primitive pairs
- axis-separated gap values (x/y/z)

## JSON mode

Machine-readable schema for CI tooling and prompt-time checks:

```json
{
  "summary": {"primitive_count": 12},
  "primitives": [{"id": "roof_front", "aabb": {"min": [...], "max": [...]}}],
  "faces": [{"primitive_id": "gable_front_left", "face": "slope", "normal": [...]}],
  "checks": []
}
```

## Integration with intent checks

If `intent_checks` exists and `--intent-checks` is set:
- evaluate and report pass/fail + measured values
- do not modify output geometry

## Exit codes

- `0`: inspect completed; warnings may still be present
- `1`: parse/validation failure
- `2`: inspect argument/config error
- `3`: intent check failed in strict mode (`--fail-on-intent`)

## Why this helps

This catches common mistakes before rendering:
- roof ridge along wrong axis
- gable/roof planes not aligned
- unexpected overhang/gap magnitudes

It is especially useful for LLM-driven loops where numeric guardrails reduce trial-and-error.
