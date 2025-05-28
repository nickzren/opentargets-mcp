# src/opentargets_mcp/tools/__init__.py
"""
This package aggregates all tool definitions and their corresponding API classes
from the various tool modules (target, disease, drug, evidence, search, variant, study).
"""

from .target import TARGET_TOOLS, TargetApi
from .disease import DISEASE_TOOLS, DiseaseApi
from .drug import DRUG_TOOLS, DrugApi
from .evidence import EVIDENCE_TOOLS, EvidenceApi
from .search import SEARCH_TOOLS, SearchApi
from .variant import VARIANT_TOOLS, VariantApi
from .study import STUDY_TOOLS, StudyApi

# A comprehensive list of all available tools from all tool modules.
# This list is used by the MCP server to announce its capabilities.
ALL_TOOLS = (
    TARGET_TOOLS +
    DISEASE_TOOLS +
    DRUG_TOOLS +
    EVIDENCE_TOOLS +
    SEARCH_TOOLS +
    VARIANT_TOOLS +
    STUDY_TOOLS
)

# A mapping from tool names (strings) to the API class that implements the tool's logic.
# This helps the server dispatch a tool call to the correct handler method.
API_CLASS_MAP = {
    **{tool.name: TargetApi for tool in TARGET_TOOLS},
    **{tool.name: DiseaseApi for tool in DISEASE_TOOLS},
    **{tool.name: DrugApi for tool in DRUG_TOOLS},
    **{tool.name: EvidenceApi for tool in EVIDENCE_TOOLS},
    **{tool.name: SearchApi for tool in SEARCH_TOOLS},
    **{tool.name: VariantApi for tool in VARIANT_TOOLS},
    **{tool.name: StudyApi for tool in STUDY_TOOLS},
}

# __all__ defines the public API of this module.
__all__ = [
    "ALL_TOOLS",
    "API_CLASS_MAP",
    "TargetApi",
    "TARGET_TOOLS",
    "DiseaseApi",
    "DISEASE_TOOLS",
    "DrugApi",
    "DRUG_TOOLS",
    "EvidenceApi",
    "EVIDENCE_TOOLS",
    "SearchApi",
    "SEARCH_TOOLS",
    "VariantApi",
    "VARIANT_TOOLS",
    "StudyApi",
    "STUDY_TOOLS",
]