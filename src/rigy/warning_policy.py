"""Warning policy controls for Rigy diagnostics."""

from __future__ import annotations

import warnings
from dataclasses import dataclass

from rigy.errors import ValidationError

KNOWN_CODES: frozenset[str] = frozenset({"W01", "W02", "W03"})


class RigyWarning(UserWarning):
    """Warning with a machine-readable code."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"[{code}] {message}")


@dataclass(frozen=True)
class WarningPolicy:
    """Controls how individual warning codes are handled."""

    warn_as_error: frozenset[str] = frozenset()
    suppress: frozenset[str] = frozenset()


def emit_warning(code: str, message: str, *, policy: WarningPolicy | None = None) -> None:
    """Emit a warning, respecting the active policy.

    - If code is in ``policy.suppress``, the warning is silently dropped.
    - If code is in ``policy.warn_as_error``, a ``ValidationError`` is raised.
    - Otherwise a ``RigyWarning`` is issued via ``warnings.warn``.
    """
    if policy is not None:
        if code in policy.suppress:
            return
        if code in policy.warn_as_error:
            raise ValidationError(f"[{code}] {message}")

    warnings.warn(RigyWarning(code, message), stacklevel=2)


def parse_code_list(raw: str) -> frozenset[str]:
    """Parse a comma-separated string of W-codes and validate them.

    Raises ``ValueError`` for unknown codes.
    """
    codes: set[str] = set()
    for token in raw.split(","):
        token = token.strip()
        if not token:
            continue
        if token not in KNOWN_CODES:
            raise ValueError(f"Unknown warning code: {token!r} (known: {sorted(KNOWN_CODES)})")
        codes.add(token)
    return frozenset(codes)
