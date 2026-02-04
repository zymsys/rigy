"""Build manifest for Rigy compile output."""

from __future__ import annotations

import hashlib
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from rigy import __version__


def _sha256_of_file(path: Path) -> str:
    """Return the hex SHA-256 digest of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _git_sha() -> str | None:
    """Return current git HEAD SHA, or None if unavailable."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


def build_manifest(
    *,
    input_path: Path,
    output_path: Path,
    expanded_yaml_path: Path | None = None,
    command_args: list[str] | None = None,
) -> dict:
    """Build a manifest dict describing a compile run.

    Should be called *after* the output GLB has been written.
    """
    manifest: dict = {
        "manifest_version": 1,
        "tool": {
            "name": "rigy",
            "version": __version__,
            "python": sys.version.split()[0],
            "git_sha": _git_sha(),
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "input": {
            "path": str(input_path),
            "sha256": _sha256_of_file(input_path),
        },
        "output": {
            "path": str(output_path),
            "sha256": _sha256_of_file(output_path),
        },
    }

    if expanded_yaml_path is not None and expanded_yaml_path.exists():
        manifest["expanded_yaml"] = {
            "path": str(expanded_yaml_path),
            "sha256": _sha256_of_file(expanded_yaml_path),
        }

    if command_args is not None:
        manifest["command_args"] = command_args

    return manifest
