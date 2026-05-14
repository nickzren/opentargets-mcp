"""Cross-entity workflow tools built from curated Open Targets endpoints."""

from __future__ import annotations

import asyncio
from typing import Any, Dict

from ..exceptions import ValidationError
from ..queries import OpenTargetsClient
from ..resolver import _DISEASE_ID_PATTERNS, _best_hit, _looks_like_id
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
        best = _best_hit(first_mapping)
        if best is None:
            raise ValidationError(f"Unable to resolve disease identifier: {value}")
        best_id = best.get("id")
        if not best_id:
            raise ValidationError(f"Unable to resolve disease identifier: {value}")
        return best_id

    @staticmethod
    def _validate_repurposing_inputs(
        min_association_score: float,
        max_targets: int,
        min_clinical_phase: int,
        max_drugs_per_target: int,
        max_candidates: int,
        max_concurrency: int,
    ) -> None:
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

    async def _fetch_disease_target_rows(
        self,
        client: OpenTargetsClient,
        efo_id: str,
        max_targets: int,
    ) -> tuple[str, dict[str, Any], list[Any]]:
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

        target_rows = disease.get("associatedTargets", {}).get("rows", [])
        if not isinstance(target_rows, list):
            target_rows = []
        return resolved_efo_id, disease, target_rows

    @staticmethod
    def _select_targets(
        target_rows: list[Any],
        min_association_score: float,
    ) -> list[dict[str, Any]]:
        selected_targets = []
        for row in target_rows:
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
        return selected_targets

    async def _fetch_known_drug_sets(
        self,
        client: OpenTargetsClient,
        selected_targets: list[dict[str, Any]],
        max_drugs_per_target: int,
        max_concurrency: int,
    ) -> tuple[list[dict[str, Any]], int]:
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
        failed_count = sum(
            1 for item in target_drug_results if isinstance(item, BaseException)
        )
        target_drug_sets = [
            item for item in target_drug_results if not isinstance(item, BaseException)
        ]
        return target_drug_sets, failed_count

    @staticmethod
    def _row_phase(row: dict[str, Any]) -> int:
        phase = row.get("phase") or 0
        if isinstance(phase, int):
            return phase
        return int(phase) if str(phase).isdigit() else 0

    @staticmethod
    def _aggregate_candidates(
        target_drug_sets: list[dict[str, Any]],
        min_clinical_phase: int,
        approved_only: bool,
        max_drugs_per_target: int,
    ) -> tuple[dict[str, dict[str, Any]], int]:
        candidates_by_drug: dict[str, dict[str, Any]] = {}
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

                phase = WorkflowApi._row_phase(row)
                if phase < min_clinical_phase:
                    continue

                is_approved = bool(drug.get("isApproved"))
                if approved_only and not is_approved:
                    continue

                support_row = {
                    "targetId": target["target_id"],
                    "targetSymbol": target.get("target_symbol"),
                    "associationScore": target["association_score"],
                    "phase": phase,
                    "status": row.get("status"),
                    "mechanismOfAction": row.get("mechanismOfAction"),
                }
                WorkflowApi._merge_candidate(
                    candidates_by_drug,
                    drug_id,
                    drug,
                    target,
                    phase,
                    is_approved,
                    support_row,
                )

        return candidates_by_drug, targets_with_known_drugs

    @staticmethod
    def _merge_candidate(
        candidates_by_drug: dict[str, dict[str, Any]],
        drug_id: str,
        drug: dict[str, Any],
        target: dict[str, Any],
        phase: int,
        is_approved: bool,
        support_row: dict[str, Any],
    ) -> None:
        existing = candidates_by_drug.get(drug_id)
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
                    "maximumClinicalStage": drug.get("maximumClinicalStage"),
                },
                "bestAssociationScore": target["association_score"],
                "bestPhase": phase,
                "supportingTargets": [support_row],
            }
            return

        existing["bestAssociationScore"] = max(
            existing["bestAssociationScore"], target["association_score"]
        )
        existing["bestPhase"] = max(existing["bestPhase"], phase)
        if is_approved:
            existing["drug"]["isApproved"] = True
        existing["supportingTargets"].append(support_row)

    @staticmethod
    def _rank_candidates(
        candidates_by_drug: dict[str, dict[str, Any]],
        max_candidates: int,
    ) -> list[dict[str, Any]]:
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
        return candidates[:max_candidates]

    @staticmethod
    def _build_repurposing_response(
        disease: dict[str, Any],
        resolved_efo_id: str,
        target_rows: list[Any],
        selected_targets: list[dict[str, Any]],
        targets_with_known_drugs: int,
        targets_failed_drug_lookup: int,
        candidates: list[dict[str, Any]],
        min_association_score: float,
        min_clinical_phase: int,
        approved_only: bool,
    ) -> dict[str, Any]:
        return {
            "disease": {
                "id": disease.get("id") or resolved_efo_id,
                "name": disease.get("name"),
            },
            "summary": {
                "targetsEvaluated": len(target_rows),
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
        self._validate_repurposing_inputs(
            min_association_score,
            max_targets,
            min_clinical_phase,
            max_drugs_per_target,
            max_candidates,
            max_concurrency,
        )
        resolved_efo_id, disease, target_rows = await self._fetch_disease_target_rows(
            client,
            efo_id,
            max_targets,
        )
        selected_targets = self._select_targets(
            target_rows,
            min_association_score,
        )
        target_drug_sets, targets_failed_drug_lookup = (
            await self._fetch_known_drug_sets(
                client,
                selected_targets,
                max_drugs_per_target,
                max_concurrency,
            )
        )
        candidates_by_drug, targets_with_known_drugs = self._aggregate_candidates(
            target_drug_sets,
            min_clinical_phase,
            approved_only,
            max_drugs_per_target,
        )
        candidates = self._rank_candidates(candidates_by_drug, max_candidates)
        return self._build_repurposing_response(
            disease,
            resolved_efo_id,
            target_rows,
            selected_targets,
            targets_with_known_drugs,
            targets_failed_drug_lookup,
            candidates,
            min_association_score,
            min_clinical_phase,
            approved_only,
        )
