"""Custom exceptions for Open Targets MCP server."""


class OpenTargetsError(Exception):
    """Base exception for all Open Targets MCP errors."""

    pass


class NetworkError(OpenTargetsError):
    """Raised when a network request fails."""

    pass


class ValidationError(OpenTargetsError):
    """Raised when input validation fails."""

    pass
