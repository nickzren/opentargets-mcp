"""Resolve user-provided names into canonical Open Targets identifiers."""
from __future__ import annotations

from dataclasses import dataclass
import asyncio
import re
from typing import Any, Iterable, Mapping

from .exceptions import ValidationError
from .queries import OpenTargetsClient


@dataclass(frozen=True)
class _ResolverSpec:
    entity_names: tuple[str, ...]
    id_patterns: tuple[re.Pattern[str], ...]
    expects_list: bool = False


_TARGET_ID_PATTERNS = (
    re.compile(r"^ENSG\d+$"),
)
_DISEASE_ID_PATTERNS = (
    re.compile(r"^EFO_\d+$"),
    re.compile(r"^MONDO_\d+$"),
    re.compile(r"^Orphanet_\d+$"),
    re.compile(r"^HP_\d+$"),
    re.compile(r"^DOID_\d+$"),
    re.compile(r"^OTAR_\d+$"),
)
_DRUG_ID_PATTERNS = (
    re.compile(r"^CHEMBL\d+$"),
)
_VARIANT_ID_PATTERNS = (
    re.compile(r"^(\d+|X|Y|MT)_\d+_[ACGT]+_[ACGT]+$"),
    re.compile(r"^OTVAR_(\d+|X|Y|MT)_\d+_[0-9a-f]{32}$"),
)
_STUDY_ID_PATTERNS = (
    re.compile(r"^GCST\d+$"),
    re.compile(r"^FINNGEN_.+$"),
    re.compile(r"^NEALE2_.+$"),
    re.compile(r"^SAIGE_.+$"),
    re.compile(r"^IEU-[A-Za-z0-9_-]+$"),
)
_ANY_ENTITY_ID_PATTERNS = (
    *_TARGET_ID_PATTERNS,
    *_DISEASE_ID_PATTERNS,
    *_DRUG_ID_PATTERNS,
    *_VARIANT_ID_PATTERNS,
    *_STUDY_ID_PATTERNS,
)


_PARAM_SPECS: Mapping[str, _ResolverSpec] = {
    "ensembl_id": _ResolverSpec(entity_names=("target",), id_patterns=_TARGET_ID_PATTERNS),
    "ensembl_ids": _ResolverSpec(
        entity_names=("target",),
        id_patterns=_TARGET_ID_PATTERNS,
        expects_list=True,
    ),
    "entity_id": _ResolverSpec(entity_names=("target",), id_patterns=_TARGET_ID_PATTERNS),
    "efo_id": _ResolverSpec(entity_names=("disease",), id_patterns=_DISEASE_ID_PATTERNS),
    "efo_ids": _ResolverSpec(
        entity_names=("disease",),
        id_patterns=_DISEASE_ID_PATTERNS,
        expects_list=True,
    ),
    "disease_ids": _ResolverSpec(
        entity_names=("disease",),
        id_patterns=_DISEASE_ID_PATTERNS,
        expects_list=True,
    ),
    "chembl_id": _ResolverSpec(entity_names=("drug",), id_patterns=_DRUG_ID_PATTERNS),
    "chembl_ids": _ResolverSpec(
        entity_names=("drug",),
        id_patterns=_DRUG_ID_PATTERNS,
        expects_list=True,
    ),
    "variant_id": _ResolverSpec(entity_names=("variant",), id_patterns=_VARIANT_ID_PATTERNS),
    "variant_ids": _ResolverSpec(
        entity_names=("variant",),
        id_patterns=_VARIANT_ID_PATTERNS,
        expects_list=True,
    ),
    "study_id": _ResolverSpec(entity_names=("study",), id_patterns=_STUDY_ID_PATTERNS),
    "study_ids": _ResolverSpec(
        entity_names=("study",),
        id_patterns=_STUDY_ID_PATTERNS,
        expects_list=True,
    ),
    "additional_entity_ids": _ResolverSpec(
        entity_names=("target", "disease", "drug", "variant", "study"),
        id_patterns=_ANY_ENTITY_ID_PATTERNS,
        expects_list=True,
    ),
}

_meta_api: Any | None = None


def _get_meta_api() -> Any:
    global _meta_api
    if _meta_api is None:
        from .tools.meta import MetaApi

        _meta_api = MetaApi()
    return _meta_api


def _looks_like_id(value: str, patterns: Iterable[re.Pattern[str]]) -> bool:
    return any(pattern.match(value) for pattern in patterns)


# Open Targets 26.06 search accepts colon-form ontology identifiers, but the
# stored IDs (and mapIds) use underscores. Rewrite the prefixes we know.
_ONTOLOGY_PREFIXES = {
    "EFO": "EFO",
    "MONDO": "MONDO",
    "ORPHANET": "Orphanet",
    "HP": "HP",
    "DOID": "DOID",
    "OTAR": "OTAR",
}
_ONTOLOGY_COLON_PATTERN = re.compile(r"^([A-Za-z]+):(\d+)$")


def _canonical_ontology_id(value: str) -> str:
    match = _ONTOLOGY_COLON_PATTERN.match(value)
    if not match:
        return value
    prefix = _ONTOLOGY_PREFIXES.get(match.group(1).upper())
    if prefix is None:
        return value
    return f"{prefix}_{match.group(2)}"


# mapIds misses `chr1:154453788:C:T`; the stored form is `1_154453788_C_T`.
_CHR_PREFIX_PATTERN = re.compile(r"^chr", re.IGNORECASE)


def _canonical_variant_id(value: str) -> str:
    return _CHR_PREFIX_PATTERN.sub("", value).replace(":", "_")


def _normalize_term(value: Any, patterns: Iterable[re.Pattern[str]]) -> Any:
    """Strip whitespace; apply notation fixes only when they yield an ID valid for this param."""
    if not isinstance(value, str):
        return value
    value = value.strip()
    for candidate in (_canonical_ontology_id(value), _canonical_variant_id(value)):
        if candidate != value and _looks_like_id(candidate, patterns):
            return candidate
    return value


def _fold(value: str) -> str:
    return " ".join(value.split()).casefold()


def _top_hits(mapping: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """Return the top-scoring hits, one per ID."""
    hits = [
        hit
        for hit in mapping.get("hits") or []
        if isinstance(hit, Mapping) and hit.get("id")
    ]
    if not hits:
        return []
    top_score = max(hit.get("score", 0) for hit in hits)
    top: dict[str, Mapping[str, Any]] = {}
    for hit in hits:
        if hit.get("score", 0) == top_score:
            top.setdefault(hit["id"], hit)
    return list(top.values())


def _is_exact_match(term: str, hit: Mapping[str, Any]) -> bool:
    entity = hit.get("object") or {}
    names = (
        hit.get("id"),
        hit.get("name"),
        entity.get("approvedSymbol"),
        entity.get("approvedName"),
    )
    return any(_fold(name) == _fold(term) for name in names if name)


def _best_hit(mapping: Mapping[str, Any]) -> Mapping[str, Any] | None:
    """Return the single top hit, else the unique exact match; None when ambiguous."""
    top = _top_hits(mapping)
    if len(top) == 1:
        return top[0]
    exact = [hit for hit in top if _is_exact_match(mapping.get("term") or "", hit)]
    return exact[0] if len(exact) == 1 else None


def _ambiguity_error(name: str, term: str, hits: list[Mapping[str, Any]]) -> ValidationError:
    candidates = [
        f"{hit['id']} ({hit['name']})"
        if hit.get("name") and hit["name"] != hit["id"]
        else hit["id"]
        for hit in hits[:5]
    ]
    more = f" (+{len(hits) - 5} more)" if len(hits) > 5 else ""
    return ValidationError(
        f"Ambiguous {name} '{term}': {', '.join(candidates)}{more}; pass an ID"
    )


def _best_hit_id(mapping: Mapping[str, Any]) -> str | None:
    best = _best_hit(mapping)
    return best.get("id") if best else None


async def _resolve_terms(
    client: OpenTargetsClient,
    name: str,
    terms: list[str],
    spec: _ResolverSpec,
) -> tuple[dict[str, str], list[str]]:
    result = await _get_meta_api().map_ids(client, terms, entity_names=list(spec.entity_names))
    mappings = result.get("mapIds", {}).get("mappings", [])
    resolved: dict[str, str] = {}
    unresolved: list[str] = []
    for mapping in mappings:
        term = mapping.get("term")
        if not term:
            continue
        best_id = _best_hit_id(mapping)
        if not best_id:
            top = _top_hits(mapping)
            if top:
                raise _ambiguity_error(name, term, top)
            unresolved.append(term)
            continue
        resolved[term] = best_id
    for term in terms:
        if term not in resolved and term not in unresolved:
            unresolved.append(term)
    return resolved, unresolved


async def resolve_param(
    client: OpenTargetsClient,
    name: str,
    value: Any,
) -> Any:
    spec = _PARAM_SPECS.get(name)
    if spec is None or value is None:
        return value

    if spec.expects_list:
        if not isinstance(value, list):
            return value
        value = [_normalize_term(term, spec.id_patterns) for term in value]
        terms = [term for term in value if isinstance(term, str)]
        unresolved = [term for term in terms if not _looks_like_id(term, spec.id_patterns)]
        if not unresolved:
            return value
        resolved_map, missing = await _resolve_terms(client, name, unresolved, spec)
        if missing:
            message = f"Unable to resolve {name}: {', '.join(missing)}"
            raise ValidationError(message)
        resolved_list = []
        for term in value:
            if isinstance(term, str):
                resolved_list.append(resolved_map.get(term, term))
            else:
                resolved_list.append(term)
        return resolved_list

    value = _normalize_term(value, spec.id_patterns)
    if not isinstance(value, str) or _looks_like_id(value, spec.id_patterns):
        return value

    resolved_map, missing = await _resolve_terms(client, name, [value], spec)
    if missing:
        message = f"Unable to resolve {name}: {value}"
        raise ValidationError(message)
    return resolved_map.get(value, value)


async def resolve_params(
    client: OpenTargetsClient,
    params: Mapping[str, Any],
) -> dict[str, Any]:
    names = list(params.keys())
    tasks = [resolve_param(client, name, params[name]) for name in names]
    results = await asyncio.gather(*tasks)
    return dict(zip(names, results, strict=True))
