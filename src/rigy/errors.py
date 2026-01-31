"""Custom exception hierarchy for the Rigy compiler."""


class RigyError(Exception):
    """Base exception for all Rigy errors."""


class ParseError(RigyError):
    """Raised when YAML parsing or schema deserialization fails."""


class ValidationError(RigyError):
    """Raised when semantic validation fails (cycles, bad refs, etc.)."""


class TessellationError(RigyError):
    """Raised when geometry generation fails."""


class ExportError(RigyError):
    """Raised when glTF/GLB export fails."""
