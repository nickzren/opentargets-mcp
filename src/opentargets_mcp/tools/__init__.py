"""Public API surfaces for Open Targets MCP tool classes.

`ALL_TOOLS` and `API_CLASS_MAP` were removed in v0.2.0. FastMCP now handles tool
registration and dispatching directly in `opentargets_mcp.server`.
"""

from .disease import DiseaseApi
from .drug import DrugApi
from .evidence import EvidenceApi
from .meta import MetaApi
from .search import SearchApi
from .study import StudyApi
from .target import TargetApi
from .variant import VariantApi

__all__ = [
    "DiseaseApi",
    "DrugApi",
    "EvidenceApi",
    "MetaApi",
    "SearchApi",
    "StudyApi",
    "TargetApi",
    "VariantApi",
]


def __getattr__(name: str):  # pragma: no cover - transitional guidance
    if name == "ALL_TOOLS":
        import warnings

        warnings.warn(
            "ALL_TOOLS is deprecated in v0.2.0. Tools are now managed by FastMCP.",
            DeprecationWarning,
            stacklevel=2,
        )
        return []
    if name == "API_CLASS_MAP":
        import warnings

        warnings.warn(
            "API_CLASS_MAP is deprecated in v0.2.0. FastMCP handles tool dispatch.",
            DeprecationWarning,
            stacklevel=2,
        )
        return {}
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
