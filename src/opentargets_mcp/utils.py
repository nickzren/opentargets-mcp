"""Utility functions for Open Targets MCP server."""
import json
from typing import Any, Dict, Iterable, Optional

from .exceptions import ValidationError


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


def select_fields(payload: Any, fields: Optional[Iterable[str]] = None) -> Any:
    """Return a filtered payload containing only the requested field paths."""
    if not fields:
        return payload

    tree: dict[str, Any] = {}
    for path in fields:
        if not path:
            continue
        node = tree
        for part in filter(None, path.split(".")):
            node = node.setdefault(part, {})

    def project(value: Any, spec: dict[str, Any]) -> Any:
        if not spec:
            return value
        if isinstance(value, list):
            return [project(item, spec) for item in value]
        if isinstance(value, dict):
            output: dict[str, Any] = {}
            for key, child in spec.items():
                if key in value:
                    output[key] = project(value[key], child)
            return output
        return value

    return project(payload, tree)


def clinical_stage_to_phase(stage: Any) -> int:
    """Convert Open Targets clinical stage strings to the legacy numeric phase."""
    if isinstance(stage, bool):
        return 0
    if isinstance(stage, int):
        return stage
    if not isinstance(stage, str):
        return 0

    normalized = stage.upper()
    stage_map = {
        "UNKNOWN": 0,
        "PHASE_0": 0,
        "PHASE_1": 1,
        "PHASE_1_2": 1,
        "PHASE_2": 2,
        "PHASE_2_3": 2,
        "PHASE_3": 3,
        "PHASE_4": 4,
        "APPROVAL": 4,
    }
    return stage_map.get(normalized, 0)


def add_legacy_drug_fields(drug: Any) -> Any:
    """Populate removed drug fields from the current Open Targets schema."""
    if not isinstance(drug, dict):
        return drug

    stage = drug.get("maximumClinicalStage")
    phase = clinical_stage_to_phase(stage)
    drug.setdefault("maximumClinicalTrialPhase", phase)
    drug.setdefault("isApproved", stage == "APPROVAL" or phase >= 4)

    warnings = drug.get("drugWarnings") or []
    if isinstance(warnings, list):
        warning_text = " ".join(
            " ".join(str(item.get(key, "")) for key in ("warningType", "toxicityClass"))
            for item in warnings
            if isinstance(item, dict)
        ).lower()
        drug.setdefault("hasBeenWithdrawn", "withdraw" in warning_text)
        drug.setdefault(
            "blackBoxWarning",
            "black box" in warning_text or "blackbox" in warning_text,
        )
    else:
        drug.setdefault("hasBeenWithdrawn", False)
        drug.setdefault("blackBoxWarning", False)

    return drug


def normalize_clinical_candidate(row: Any) -> Any:
    """Add legacy known-drug row fields to current clinical candidate rows."""
    if not isinstance(row, dict):
        return row

    row.setdefault("phase", clinical_stage_to_phase(row.get("maxClinicalStage")))
    reports = row.get("clinicalReports") or []
    if isinstance(reports, list) and reports:
        first_report = next((item for item in reports if isinstance(item, dict)), {})
        row.setdefault("status", first_report.get("trialOverallStatus"))
        urls = [
            {"name": item.get("id") or item.get("source"), "url": item.get("url")}
            for item in reports
            if isinstance(item, dict) and item.get("url")
        ]
        if urls:
            row.setdefault("urls", urls)

    add_legacy_drug_fields(row.get("drug"))

    diseases = row.get("diseases")
    if isinstance(diseases, list) and diseases:
        disease = next(
            (
                item.get("disease")
                for item in diseases
                if isinstance(item, dict) and isinstance(item.get("disease"), dict)
            ),
            None,
        )
        if disease is not None:
            row.setdefault("disease", disease)

    return row


def validate_required_int(
    value: Any,
    field_name: str,
    *,
    minimum: int = 1,
) -> int:
    """Validate that value is an int and greater than or equal to minimum."""
    if value is None:
        raise ValidationError(f"{field_name} is required and cannot be None.")
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValidationError(
            f"{field_name} must be an integer >= {minimum}."
        )
    return value
