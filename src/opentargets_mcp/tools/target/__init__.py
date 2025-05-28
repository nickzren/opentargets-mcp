# src/opentargets_mcp/tools/target/__init__.py
"""
This package aggregates all tool definitions and their corresponding API classes
from the various target-related tool modules.
"""

from .identity import TARGET_IDENTITY_TOOLS, TargetIdentityApi
from .associations import TARGET_ASSOCIATIONS_TOOLS, TargetAssociationsApi
from .biology import TARGET_BIOLOGY_TOOLS, TargetBiologyApi
from .safety import TARGET_SAFETY_TOOLS, TargetSafetyApi

TARGET_TOOLS = (
    TARGET_IDENTITY_TOOLS +
    TARGET_ASSOCIATIONS_TOOLS +
    TARGET_BIOLOGY_TOOLS +
    TARGET_SAFETY_TOOLS
)

# A single, unified API class for simplicity in the server dispatcher.
# It inherits from all the smaller API classes.
class TargetApi(
    TargetIdentityApi,
    TargetAssociationsApi,
    TargetBiologyApi,
    TargetSafetyApi,
):
    """A unified API class for all target-related tools."""
    pass


__all__ = [
    "TARGET_TOOLS",
    "TargetApi",
]