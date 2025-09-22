"""Target tool API aggregation."""

from .identity import TargetIdentityApi
from .associations import TargetAssociationsApi
from .biology import TargetBiologyApi
from .safety import TargetSafetyApi


class TargetApi(
    TargetIdentityApi,
    TargetAssociationsApi,
    TargetBiologyApi,
    TargetSafetyApi,
):
    """Unified API surface for all target-related tools."""


__all__ = ["TargetApi"]
