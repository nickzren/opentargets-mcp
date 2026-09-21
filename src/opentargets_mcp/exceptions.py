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


class UpstreamQueryError(OpenTargetsError):
    """Raised when the Open Targets API rejects a query or returns GraphQL errors.

    Carries the upstream ``errors[].message`` text so callers can act on it
    (for example, a renamed field after a data release).
    """

    def __init__(self, messages: list[str], status: int | None = None):
        self.messages = messages
        self.status = status
        super().__init__("; ".join(messages))
