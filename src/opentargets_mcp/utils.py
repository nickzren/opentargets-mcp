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

    return _project_field_tree(payload, _build_field_tree(fields))


def _build_field_tree(fields: Iterable[str]) -> dict[str, Any]:
    tree: dict[str, Any] = {}
    for path in fields:
        if not path:
            continue
        node = tree
        for part in filter(None, path.split(".")):
            node = node.setdefault(part, {})
    return tree


def _project_field_tree(value: Any, spec: dict[str, Any]) -> Any:
    if not spec:
        return value
    if isinstance(value, list):
        return [_project_field_tree(item, spec) for item in value]
    if isinstance(value, dict):
        output: dict[str, Any] = {}
        for key, child in spec.items():
            if key in value:
                output[key] = _project_field_tree(value[key], child)
        return output
    return value


def promote_clinical_candidates(
    parent: Any,
    *,
    limit: int,
    source_key: str = "drugAndClinicalCandidates",
    target_key: str = "knownDrugs",
) -> Any:
    """Move clinical candidates to the legacy known-drugs shape."""
    if not isinstance(parent, dict):
        return parent

    candidates = parent.pop(source_key, None)
    if isinstance(candidates, dict):
        rows = candidates.get("rows")
        if isinstance(rows, list):
            normalized_rows = [
                normalize_clinical_candidate(row) for row in rows[:limit]
            ]
            candidates["rows"] = normalized_rows
            candidates["count"] = len(normalized_rows)
        parent[target_key] = candidates
    return parent


def page_list(items: Any, page_index: int, page_size: int) -> Any:
    """Return a page from list-like API fields; leave non-lists untouched."""
    if not isinstance(items, list):
        return items
    start = page_index * page_size
    return items[start : start + page_size]


def build_literature_variables(
    entity_key: str,
    entity_id: str,
    *,
    additional_entity_ids: Optional[Iterable[str]] = None,
    start_year: Optional[int] = None,
    start_month: Optional[int] = None,
    end_year: Optional[int] = None,
    end_month: Optional[int] = None,
    cursor: Optional[str] = None,
) -> Dict[str, Any]:
    """Build optional variables for literature occurrence queries."""
    return filter_none_values(
        {
            entity_key: entity_id,
            "additionalIds": additional_entity_ids,
            "startYear": start_year,
            "startMonth": start_month,
            "endYear": end_year,
            "endMonth": end_month,
            "cursor": cursor,
        }
    )


def trim_literature_occurrences(payload: Any, parent_key: str, size: Any) -> Any:
    """Apply client-side row trimming for literature occurrence payloads."""
    if (
        size is None
        or not isinstance(size, int)
        or size < 0
        or not isinstance(payload, dict)
    ):
        return payload

    parent = payload.get(parent_key)
    if not isinstance(parent, dict):
        return payload

    literature = parent.get("literatureOcurrences")
    if not isinstance(literature, dict):
        return payload

    rows = literature.get("rows")
    if isinstance(rows, list):
        literature["rows"] = rows[:size]
    return payload


def flatten_mechanism_targets(
    rows: Any,
    *,
    copy_mechanism_fields: bool = False,
) -> list[dict[str, Any]]:
    """Return unique targets from mechanisms-of-action rows."""
    targets_by_id: dict[str, dict[str, Any]] = {}
    for mechanism in rows or []:
        if not isinstance(mechanism, dict):
            continue
        for target in mechanism.get("targets", []) or []:
            if not isinstance(target, dict) or not target.get("id"):
                continue
            if copy_mechanism_fields:
                target.setdefault(
                    "mechanismOfAction", mechanism.get("mechanismOfAction")
                )
                target.setdefault("actionType", mechanism.get("actionType"))
            targets_by_id.setdefault(target["id"], target)
    return list(targets_by_id.values())


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
    maximum: Optional[int] = None,
) -> int:
    """Validate that value is an int within the requested inclusive range."""
    if value is None:
        raise ValidationError(f"{field_name} is required and cannot be None.")
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValidationError(
            f"{field_name} must be an integer >= {minimum}."
        )
    if maximum is not None and value > maximum:
        raise ValidationError(f"{field_name} must be <= {maximum}.")
    return value
