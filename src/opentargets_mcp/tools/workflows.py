"""Cross-entity workflow tools built from curated Open Targets endpoints."""

from __future__ import annotations

import asyncio
from typing import Any, Dict

from ..exceptions import ValidationError
from ..queries import OpenTargetsClient
from ..resolver import _DISEASE_ID_PATTERNS, _looks_like_id
from .disease import DiseaseApi
from .meta import MetaApi
from .target import TargetApi

MAX_WORKFLOW_TARGETS = 200
MAX_WORKFLOW_DRUGS_PER_TARGET = 100
MAX_WORKFLOW_CANDIDATES = 200
MAX_WORKFLOW_CONCURRENCY = 20


class WorkflowApi:
    """High-level tools that orchestrate multiple domain APIs."""

    def __init__(self) -> None:
        self._disease_api = DiseaseApi()
        self._target_api = TargetApi()
        self._meta_api = MetaApi()

    async def _resolve_disease_id(self, client: OpenTargetsClient, value: str) -> str:
        if _looks_like_id(value, _DISEASE_ID_PATTERNS):
            return value

        mapping = await self._meta_api.map_ids(
            client,
            [value],
            entity_names=["disease"],
        )
        mappings = mapping.get("mapIds", {}).get("mappings", [])
        if not mappings or not isinstance(mappings, list):
            raise ValidationError(f"Unable to resolve disease identifier: {value}")
        first_mapping = mappings[0] if isinstance(mappings[0], dict) else {}
        hits = first_mapping.get("hits", [])
        if not hits:
            raise ValidationError(f"Unable to resolve disease identifier: {value}")
        hit_dicts = [hit for hit in hits if isinstance(hit, dict)]
        best = max(hit_dicts, key=lambda hit: hit.get("score", 0), default=None)
        if best is None:
            raise ValidationError(f"Unable to resolve disease identifier: {value}")
        best_id = best.get("id")
        if not best_id:
            raise ValidationError(f"Unable to resolve disease identifier: {value}")
        return best_id

    async def get_drug_repurposing_candidates(
        self,
        client: OpenTargetsClient,
        efo_id: str,
        min_association_score: float = 0.2,
        max_targets: int = 20,
        min_clinical_phase: int = 2,
        approved_only: bool = False,
        max_drugs_per_target: int = 30,
        max_candidates: int = 50,
        max_concurrency: int = 4,
    ) -> Dict[str, Any]:
        """Find repurposing candidates by chaining disease, target, and drug evidence.

        **Workflow**
        1. Fetch targets associated with the disease.
        2. Keep targets above `min_association_score`.
        3. Fetch known drugs for each retained target.
        4. Rank unique drugs by target-association strength and clinical maturity.

        **Parameters**
        - `efo_id` (`str`): Disease identifier or disease name (auto-resolved).
        - `min_association_score` (`float`): Minimum disease-target score to keep a target.
        - `max_targets` (`int`): Maximum associated targets to evaluate.
        - `min_clinical_phase` (`int`): Minimum phase for returned drug candidates.
        - `approved_only` (`bool`): If true, only keep approved drugs.
        - `max_drugs_per_target` (`int`): Maximum known-drug rows to inspect per target.
        - `max_candidates` (`int`): Maximum unique drug candidates returned.
        - `max_concurrency` (`int`): Concurrent target-level drug lookups.

        **Returns**
        - `Dict[str, Any]` with `disease`, `summary`, `targets`, and ranked `candidates`.
        """
        if not 0 <= min_association_score <= 1:
            raise ValidationError("min_association_score must be between 0 and 1.")
        if max_targets < 1:
            raise ValidationError("max_targets must be >= 1.")
        if max_targets > MAX_WORKFLOW_TARGETS:
            raise ValidationError(
                f"max_targets must be <= {MAX_WORKFLOW_TARGETS}."
            )
        if min_clinical_phase < 0:
            raise ValidationError("min_clinical_phase must be >= 0.")
        if max_drugs_per_target < 1:
            raise ValidationError("max_drugs_per_target must be >= 1.")
        if max_drugs_per_target > MAX_WORKFLOW_DRUGS_PER_TARGET:
            raise ValidationError(
                "max_drugs_per_target must be <= "
                f"{MAX_WORKFLOW_DRUGS_PER_TARGET}."
            )
        if max_candidates < 1:
            raise ValidationError("max_candidates must be >= 1.")
        if max_candidates > MAX_WORKFLOW_CANDIDATES:
            raise ValidationError(
                f"max_candidates must be <= {MAX_WORKFLOW_CANDIDATES}."
            )
        if max_concurrency < 1:
            raise ValidationError("max_concurrency must be >= 1.")
        if max_concurrency > MAX_WORKFLOW_CONCURRENCY:
            raise ValidationError(
                f"max_concurrency must be <= {MAX_WORKFLOW_CONCURRENCY}."
            )

        resolved_efo_id = await self._resolve_disease_id(client, efo_id)

        associations = await self._disease_api.get_disease_associated_targets(
            client=client,
            efo_id=resolved_efo_id,
            page_index=0,
            page_size=max_targets,
        )

        disease = associations.get("disease") or {}
        if not isinstance(disease, dict) or not disease.get("id"):
            raise ValidationError(
                f"Disease not found for identifier: {resolved_efo_id}"
            )
        all_target_rows = disease.get("associatedTargets", {}).get("rows", [])
        if not isinstance(all_target_rows, list):
            all_target_rows = []

        selected_targets = []
        for row in all_target_rows:
            if not isinstance(row, dict):
                continue
            score = row.get("score")
            if not isinstance(score, (int, float)) or score < min_association_score:
                continue
            target = row.get("target") or {}
            target_id = target.get("id")
            if not target_id:
                continue
            selected_targets.append(
                {
                    "target_id": target_id,
                    "target_symbol": target.get("approvedSymbol"),
                    "target_name": target.get("approvedName"),
                    "association_score": float(score),
                }
            )

        semaphore = asyncio.Semaphore(max_concurrency)

        async def fetch_known_drugs(target_row: Dict[str, Any]) -> Dict[str, Any]:
            async with semaphore:
                payload = await self._target_api.get_target_known_drugs(
                    client=client,
                    ensembl_id=target_row["target_id"],
                    page_size=max_drugs_per_target,
                )

            known_drug_rows = (
                payload.get("target", {}).get("knownDrugs", {}).get("rows", [])
                if isinstance(payload, dict)
                else []
            )
            return {"target": target_row, "known_drugs": known_drug_rows}

        target_drug_results = await asyncio.gather(
            *(fetch_known_drugs(target) for target in selected_targets),
            return_exceptions=True,
        )
        targets_failed_drug_lookup = sum(
            1 for item in target_drug_results if isinstance(item, BaseException)
        )
        target_drug_sets = [
            item for item in target_drug_results if not isinstance(item, BaseException)
        ]

        candidates_by_drug: Dict[str, Dict[str, Any]] = {}
        targets_with_known_drugs = 0

        for item in target_drug_sets:
            target = item["target"]
            known_drugs = item["known_drugs"]
            if known_drugs:
                targets_with_known_drugs += 1

            for row in known_drugs[:max_drugs_per_target]:
                if not isinstance(row, dict):
                    continue
                drug = row.get("drug") or {}
                drug_id = drug.get("id") or row.get("drugId")
                if not drug_id:
                    continue

                phase = row.get("phase") or 0
                if not isinstance(phase, int):
                    phase = int(phase) if str(phase).isdigit() else 0
                if phase < min_clinical_phase:
                    continue

                is_approved = bool(drug.get("isApproved"))
                if approved_only and not is_approved:
                    continue

                existing = candidates_by_drug.get(drug_id)
                support_row = {
                    "targetId": target["target_id"],
                    "targetSymbol": target.get("target_symbol"),
                    "associationScore": target["association_score"],
                    "phase": phase,
                    "status": row.get("status"),
                    "mechanismOfAction": row.get("mechanismOfAction"),
                }

                if existing is None:
                    candidates_by_drug[drug_id] = {
                        "drug": {
                            "id": drug_id,
                            "name": drug.get("name"),
                            "drugType": drug.get("drugType"),
                            "isApproved": is_approved,
                            "maximumClinicalTrialPhase": drug.get(
                                "maximumClinicalTrialPhase"
                            ),
                        },
                        "bestAssociationScore": target["association_score"],
                        "bestPhase": phase,
                        "supportingTargets": [support_row],
                    }
                    continue

                existing["bestAssociationScore"] = max(
                    existing["bestAssociationScore"], target["association_score"]
                )
                existing["bestPhase"] = max(existing["bestPhase"], phase)
                if is_approved:
                    existing["drug"]["isApproved"] = True
                existing["supportingTargets"].append(support_row)

        candidates = []
        for candidate in candidates_by_drug.values():
            supporting_targets = candidate["supportingTargets"]
            candidate["supportingTargets"] = sorted(
                supporting_targets,
                key=lambda entry: (
                    entry.get("associationScore", 0),
                    entry.get("phase", 0),
                ),
                reverse=True,
            )
            candidate["supportingTargetCount"] = len(
                {entry.get("targetId") for entry in supporting_targets}
            )
            candidates.append(candidate)

        candidates.sort(
            key=lambda candidate: (
                candidate["drug"].get("isApproved", False),
                candidate.get("bestAssociationScore", 0),
                candidate.get("bestPhase", 0),
                candidate.get("supportingTargetCount", 0),
            ),
            reverse=True,
        )
        candidates = candidates[:max_candidates]

        return {
            "disease": {
                "id": disease.get("id") or resolved_efo_id,
                "name": disease.get("name"),
            },
            "summary": {
                "targetsEvaluated": len(all_target_rows),
                "targetsPassedScoreFilter": len(selected_targets),
                "targetsWithKnownDrugs": targets_with_known_drugs,
                "targetsFailedDrugLookup": targets_failed_drug_lookup,
                "uniqueDrugCandidates": len(candidates),
                "filters": {
                    "minAssociationScore": min_association_score,
                    "minClinicalPhase": min_clinical_phase,
                    "approvedOnly": approved_only,
                },
            },
            "targets": selected_targets,
            "candidates": candidates,
        }
