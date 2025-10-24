"""Utility functions for Open Targets MCP server."""
import json
from typing import Any, Dict, Optional


def filter_none_values(variables: Dict[str, Any]) -> Dict[str, Any]:
    """Remove None values from a dictionary.

    This is commonly used to filter GraphQL variables before sending queries,
    as None values should not be sent to the API.

    Args:
        variables: Dictionary that may contain None values

    Returns:
        New dictionary with None values removed

    Example:
        >>> filter_none_values({"a": 1, "b": None, "c": "test"})
        {"a": 1, "c": "test"}
    """
    return {k: v for k, v in variables.items() if v is not None}


def generate_cache_key(query: str, variables: Optional[Dict[str, Any]] = None) -> str:
    """Generate a cache key from a GraphQL query and variables.

    Uses JSON serialization to avoid collisions from special characters.

    Args:
        query: GraphQL query string
        variables: Optional dictionary of query variables

    Returns:
        Cache key string

    Example:
        >>> generate_cache_key("query { target }", {"id": "ENSG123"})
        "query { target }:{\"id\":\"ENSG123\"}"
    """
    if not variables:
        return query
    # Use JSON serialization with sorted keys for consistent, collision-free cache keys
    vars_str = json.dumps(variables, sort_keys=True, separators=(',', ':'))
    return f"{query}:{vars_str}"
