"""Resolve user-provided names into canonical Open Targets identifiers."""
from __future__ import annotations

from dataclasses import dataclass
import asyncio
import re
from typing import Any, Iterable, Mapping

from .exceptions import ValidationError
from .tools.meta import MetaApi
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
)
_DRUG_ID_PATTERNS = (
    re.compile(r"^CHEMBL\d+$"),
)
_VARIANT_ID_PATTERNS = (
    re.compile(r"^rs\d+$", re.IGNORECASE),
    re.compile(r"^chr[0-9XYMT]+[:_].+$", re.IGNORECASE),
    re.compile(r"^\d+_\d+_[ACGT]+_[ACGT]+$", re.IGNORECASE),
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
    "study_id": _ResolverSpec(entity_names=("study",), id_patterns=_STUDY_ID_PATTERNS),
    "additional_entity_ids": _ResolverSpec(
        entity_names=("target", "disease", "drug", "variant", "study"),
        id_patterns=_ANY_ENTITY_ID_PATTERNS,
        expects_list=True,
    ),
}

_meta_api = MetaApi()


def _looks_like_id(value: str, patterns: Iterable[re.Pattern[str]]) -> bool:
    return any(pattern.match(value) for pattern in patterns)


def _best_hit_id(mapping: Mapping[str, Any]) -> str | None:
    hits = mapping.get("hits", [])
    if not hits:
        return None
    best = max(hits, key=lambda hit: hit.get("score", 0), default=None)
    if not best:
        return None
    return best.get("id")


async def _resolve_terms(
    client: OpenTargetsClient,
    terms: list[str],
    spec: _ResolverSpec,
) -> tuple[dict[str, str], list[str]]:
    result = await _meta_api.map_ids(client, terms, entity_names=list(spec.entity_names))
    mappings = result.get("mapIds", {}).get("mappings", [])
    resolved: dict[str, str] = {}
    unresolved: list[str] = []
    for mapping in mappings:
        term = mapping.get("term")
        if not term:
            continue
        best_id = _best_hit_id(mapping)
        if not best_id:
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
        terms = [term for term in value if isinstance(term, str)]
        unresolved = [term for term in terms if not _looks_like_id(term, spec.id_patterns)]
        if not unresolved:
            return value
        resolved_map, missing = await _resolve_terms(client, unresolved, spec)
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

    if not isinstance(value, str) or _looks_like_id(value, spec.id_patterns):
        return value

    resolved_map, missing = await _resolve_terms(client, [value], spec)
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
    return dict(zip(names, results))
