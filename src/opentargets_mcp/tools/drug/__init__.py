"""Drug tool API aggregation."""

from .identity import DrugIdentityApi
from .associations import DrugAssociationsApi
from .safety import DrugSafetyApi


class DrugApi(
    DrugIdentityApi,
    DrugAssociationsApi,
    DrugSafetyApi,
):
    """Unified API surface for all drug-related tools."""


__all__ = ["DrugApi"]
