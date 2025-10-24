"""Custom exceptions for Open Targets MCP server."""


class OpenTargetsError(Exception):
    """Base exception for all Open Targets MCP errors."""

    pass


class OpenTargetsAPIError(OpenTargetsError):
    """Raised when the Open Targets GraphQL API returns an error."""

    def __init__(self, message: str, errors: list | None = None):
        super().__init__(message)
        self.errors = errors or []


class GraphQLError(OpenTargetsAPIError):
    """Raised when a GraphQL query fails."""

    pass


class NetworkError(OpenTargetsError):
    """Raised when a network request fails."""

    pass


class ValidationError(OpenTargetsError):
    """Raised when input validation fails."""

    pass


class CacheError(OpenTargetsError):
    """Raised when cache operations fail."""

    pass
