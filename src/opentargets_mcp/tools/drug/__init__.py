# src/opentargets_mcp/tools/drug/__init__.py
"""
This package aggregates all tool definitions and their corresponding API classes
from the various drug-related tool modules.
"""

from .identity import DRUG_IDENTITY_TOOLS, DrugIdentityApi
from .associations import DRUG_ASSOCIATIONS_TOOLS, DrugAssociationsApi
from .safety import DRUG_SAFETY_TOOLS, DrugSafetyApi

DRUG_TOOLS = (
    DRUG_IDENTITY_TOOLS +
    DRUG_ASSOCIATIONS_TOOLS +
    DRUG_SAFETY_TOOLS
)

# A single, unified API class for simplicity in the server dispatcher.
# It inherits from all the smaller API classes.
class DrugApi(
    DrugIdentityApi,
    DrugAssociationsApi,
    DrugSafetyApi,
):
    """A unified API class for all drug-related tools."""
    pass


__all__ = [
    "DRUG_TOOLS",
    "DrugApi",
]