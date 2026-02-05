# Repository Guidelines

## Project Structure & Module Organization
- `src/rigy/`: core package (parser, preprocessing, validation, composition, exporters, CLI).
- `tests/`: unit and integration tests (`test_*.py`), plus fixtures in `tests/fixtures/`, `tests/composition/`, and `tests/rigs_fixtures/`.
- `conformance/`: normative regression corpus (`inputs/`, `outputs/`, `manifest.json`) used for byte-stable output checks.
- `spec/rigy/` and `spec/rigs/`: canonical specification chapters; update these with behavior changes.
- `examples/` and `README.md`: user-facing usage patterns and quick-start docs.

## Build, Test, and Development Commands
- `uv sync`: install runtime + dev dependencies from `pyproject.toml` / `uv.lock`.
- `uv run pytest`: run full test suite.
- `uv run pytest tests/test_v012.py -k expression`: run a focused test subset during feature work.
- `uv run ruff check src tests`: lint code and catch style/import issues.
- `uv run rigy compile tests/fixtures/humanoid.rigy.yaml -o /tmp/humanoid.glb`: smoke-test CLI compilation.

## Coding Style & Naming Conventions
- Python 3.12+, 4-space indentation, and keep lines within Ruff’s configured limit (`100`).
- Use descriptive `snake_case` for functions/variables, `PascalCase` for classes, and `UPPER_SNAKE_CASE` for constants.
- Keep modules narrowly scoped (e.g., preprocessing logic in `preprocessing.py`, UV logic in `uv.py`).
- Prefer explicit error codes/messages aligned to spec validation codes (e.g., `V77`, `F115`).

## Testing Guidelines
- Framework: `pytest` (configured via `pyproject.toml` with `tests` as test path).
- Add or update tests in the closest domain file (`tests/test_preprocessing.py`, `tests/test_rigs_*.py`, etc.).
- For spec-visible behavior changes, add conformance fixtures and update `conformance/manifest.json` expectations.
- Keep fixture names descriptive and version-aware (example: `H110_box_aabb_basic.rigy.yaml`).

## Commit & Pull Request Guidelines
- Follow existing history style: imperative, concise subject lines (e.g., `Implement v0.12 ...`, `Fix ...`).
- Keep commits focused to one behavior area (parser, validation, exporter, docs) when possible.
- PRs should include: what changed, why, impacted spec sections, and test/lint commands run.
- If GLB outputs change, call out conformance impact explicitly (which fixtures/hashes changed and why).

## Determinism & Spec Sync
- This project treats determinism as a core contract: avoid nondeterministic ordering, float drift, and unstable serialization.
- Any behavioral change should be reflected in both code and spec/docs (`spec/rigy/`, `README.md`) in the same PR.
