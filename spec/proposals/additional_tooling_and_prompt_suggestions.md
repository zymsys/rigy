### 1) `rigy fmt`

Add:

```bash
rigy fmt <input.rigy.yaml> [-o <out.yaml>] [--in-place]
```

Behavior (v1):

* round-trip parse with comment preservation (you’re already on ruamel.yaml)
* normalize:

  * rotations to `transform.rotation_degrees` only
  * box dimensions to canonical `x/y/z` (README says aliases exist, but canonical is x/y/z) 
* stable key ordering + indentation
* idempotent (`fmt(fmt(x)) == fmt(x)`)

This will touch author files, so provide `--check` if you want CI-friendly behavior:

```bash
rigy fmt <file> --check   # exit non-zero if changes would be made
```

### 2) `rigy compile --emit-manifest`

Since you already have `rigy compile`, bolt it on there:

```bash
rigy compile model.rigy.yaml -o out.glb --emit-manifest out.manifest.json
```

Manifest contents (v1):

* tool version + git SHA if available
* input path + sha256 of input bytes
* expanded yaml path + sha256 (if emitted)
* output glb path + sha256
* command line args
* timestamp

(Optionally add inspect json hash if you ever emit it during compile, but not required.)

### 3) Warning policy controls

Add to both `compile` and `inspect`:

```bash
--warn-as-error W10,W11
--suppress-warning W12,W13
```

Your `geometry_checks` already has an explicit failure policy (`--fail-on-checks`). Keep that. 
These flags are for other warnings (and any future advisory diagnostics).

### 4) `inspect_schema_version`

In `rigy inspect --format json`, include:

```json
"inspect_schema_version": 1
```

That’s a tiny change but prevents downstream churn.
