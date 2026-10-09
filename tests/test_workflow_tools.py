import copy

import pytest

from opentargets_mcp.exceptions import ValidationError
from opentargets_mcp.tools.workflows import WorkflowApi


@pytest.mark.asyncio
async def test_get_drug_repurposing_candidates_aggregates_and_ranks(monkeypatch):
    api = WorkflowApi()

    async def fake_associations(*_args, **_kwargs):
        return {
            "disease": {
                "id": "EFO_0000311",
                "name": "Breast carcinoma",
                "associatedTargets": {
                    "rows": [
                        {
                            "target": {
                                "id": "ENSG000001",
                                "approvedSymbol": "T1",
                                "approvedName": "Target One",
                            },
                            "score": 0.91,
                        },
                        {
                            "target": {
                                "id": "ENSG000002",
                                "approvedSymbol": "T2",
                                "approvedName": "Target Two",
                            },
                            "score": 0.74,
                        },
                        {
                            "target": {"id": "ENSG000003", "approvedSymbol": "T3"},
                            "score": 0.09,
                        },
                    ]
                },
            }
        }

    async def fake_known_drugs(*_args, **kwargs):
        ensembl_id = kwargs["ensembl_id"]
        if ensembl_id == "ENSG000001":
            return {
                "target": {
                    "knownDrugs": {
                        "rows": [
                            {
                                "drugId": "CHEMBL_A",
                                "phase": 4,
                                "status": "Approved",
                                "mechanismOfAction": "MOA-A",
                                "drug": {
                                    "id": "CHEMBL_A",
                                    "name": "Drug A",
                                    "isApproved": True,
                                    "drugType": "small molecule",
                                    "maximumClinicalTrialPhase": 4,
                                },
                            },
                            {
                                "drugId": "CHEMBL_B",
                                "phase": 1,
                                "status": "Active",
                                "mechanismOfAction": "MOA-B",
                                "drug": {
                                    "id": "CHEMBL_B",
                                    "name": "Drug B",
                                    "isApproved": False,
                                },
                            },
                        ]
                    }
                }
            }
        if ensembl_id == "ENSG000002":
            return {
                "target": {
                    "knownDrugs": {
                        "rows": [
                            {
                                "drugId": "CHEMBL_A",
                                "phase": 3,
                                "status": "Active",
                                "mechanismOfAction": "MOA-A2",
                                "drug": {
                                    "id": "CHEMBL_A",
                                    "name": "Drug A",
                                    "isApproved": False,
                                    "drugType": "small molecule",
                                },
                            },
                            {
                                "drugId": "CHEMBL_C",
                                "phase": 2,
                                "status": "Active",
                                "mechanismOfAction": "MOA-C",
                                "drug": {
                                    "id": "CHEMBL_C",
                                    "name": "Drug C",
                                    "isApproved": False,
                                    "drugType": "biologic",
                                },
                            },
                        ]
                    }
                }
            }
        return {"target": {"knownDrugs": {"rows": []}}}

    monkeypatch.setattr(api._disease_api, "get_disease_associated_targets", fake_associations)
    monkeypatch.setattr(api._target_api, "get_target_known_drugs", fake_known_drugs)

    result = await api.get_drug_repurposing_candidates(
        client=object(),
        efo_id="EFO_0000311",
        min_association_score=0.2,
        min_clinical_phase=2,
    )

    assert result["disease"]["name"] == "Breast carcinoma"
    assert result["summary"]["targetsEvaluated"] == 3
    assert result["summary"]["targetsPassedScoreFilter"] == 2
    assert result["summary"]["targetsFailedDrugLookup"] == 0
    assert result["summary"]["uniqueDrugCandidates"] == 2
    assert [candidate["drug"]["id"] for candidate in result["candidates"]] == [
        "CHEMBL_A",
        "CHEMBL_C",
    ]
    assert result["candidates"][0]["supportingTargetCount"] == 2


@pytest.mark.asyncio
async def test_get_drug_repurposing_candidates_respects_approved_only(monkeypatch):
    api = WorkflowApi()

    async def fake_associations(*_args, **_kwargs):
        return {
            "disease": {
                "id": "EFO_123",
                "name": "Disease",
                "associatedTargets": {
                    "rows": [
                        {"target": {"id": "ENSG_A", "approvedSymbol": "A"}, "score": 0.8}
                    ]
                },
            }
        }

    async def fake_known_drugs(*_args, **_kwargs):
        return {
            "target": {
                "knownDrugs": {
                    "rows": [
                        {
                            "drugId": "CHEMBL_X",
                            "phase": 4,
                            "drug": {"id": "CHEMBL_X", "name": "X", "isApproved": True},
                        },
                        {
                            "drugId": "CHEMBL_Y",
                            "phase": 4,
                            "drug": {"id": "CHEMBL_Y", "name": "Y", "isApproved": False},
                        },
                    ]
                }
            }
        }

    monkeypatch.setattr(api._disease_api, "get_disease_associated_targets", fake_associations)
    monkeypatch.setattr(api._target_api, "get_target_known_drugs", fake_known_drugs)

    result = await api.get_drug_repurposing_candidates(
        client=object(),
        efo_id="EFO_123",
        approved_only=True,
        min_clinical_phase=0,
    )

    assert [candidate["drug"]["id"] for candidate in result["candidates"]] == ["CHEMBL_X"]


@pytest.mark.asyncio
async def test_get_drug_repurposing_candidates_survives_partial_target_failures(
    monkeypatch,
):
    api = WorkflowApi()

    async def fake_associations(*_args, **_kwargs):
        return {
            "disease": {
                "id": "EFO_123",
                "name": "Disease",
                "associatedTargets": {
                    "rows": [
                        {"target": {"id": "ENSG_GOOD", "approvedSymbol": "GOOD"}, "score": 0.8},
                        {"target": {"id": "ENSG_BAD", "approvedSymbol": "BAD"}, "score": 0.7},
                    ]
                },
            }
        }

    async def fake_known_drugs(*_args, **kwargs):
        if kwargs["ensembl_id"] == "ENSG_BAD":
            raise RuntimeError("transient target failure")
        return {
            "target": {
                "knownDrugs": {
                    "rows": [
                        {
                            "drugId": "CHEMBL_X",
                            "phase": 3,
                            "drug": {"id": "CHEMBL_X", "name": "X", "isApproved": False},
                        }
                    ]
                }
            }
        }

    monkeypatch.setattr(api._disease_api, "get_disease_associated_targets", fake_associations)
    monkeypatch.setattr(api._target_api, "get_target_known_drugs", fake_known_drugs)

    result = await api.get_drug_repurposing_candidates(
        client=object(),
        efo_id="EFO_123",
        min_association_score=0.2,
        min_clinical_phase=0,
    )

    assert result["summary"]["targetsPassedScoreFilter"] == 2
    assert result["summary"]["targetsWithKnownDrugs"] == 1
    assert result["summary"]["targetsFailedDrugLookup"] == 1
    assert result["summary"]["uniqueDrugCandidates"] == 1
    assert [candidate["drug"]["id"] for candidate in result["candidates"]] == ["CHEMBL_X"]


@pytest.mark.asyncio
async def test_get_drug_repurposing_candidates_validates_inputs():
    api = WorkflowApi()

    with pytest.raises(ValidationError):
        await api.get_drug_repurposing_candidates(
            client=object(),
            efo_id="EFO_1",
            min_association_score=1.2,
        )


@pytest.mark.asyncio
async def test_get_drug_repurposing_candidates_enforces_limits():
    api = WorkflowApi()

    with pytest.raises(ValidationError, match="max_targets must be <="):
        await api.get_drug_repurposing_candidates(
            client=object(),
            efo_id="EFO_1",
            max_targets=10_000,
        )

    with pytest.raises(ValidationError, match="max_drugs_per_target must be <="):
        await api.get_drug_repurposing_candidates(
            client=object(),
            efo_id="EFO_1",
            max_drugs_per_target=10_000,
        )

    with pytest.raises(ValidationError, match="max_candidates must be <="):
        await api.get_drug_repurposing_candidates(
            client=object(),
            efo_id="EFO_1",
            max_candidates=10_000,
        )

    with pytest.raises(ValidationError, match="max_concurrency must be <="):
        await api.get_drug_repurposing_candidates(
            client=object(),
            efo_id="EFO_1",
            max_concurrency=10_000,
        )


@pytest.mark.asyncio
async def test_get_drug_repurposing_candidates_resolves_disease_name(monkeypatch):
    api = WorkflowApi()
    calls = {"resolved_id": None}

    async def fake_map_ids(*_args, **_kwargs):
        return {
            "mapIds": {
                "mappings": [{"hits": [{"id": "EFO_9999999", "score": 0.9}]}]
            }
        }

    async def fake_associations(*_args, **kwargs):
        calls["resolved_id"] = kwargs["efo_id"]
        return {"disease": {"id": kwargs["efo_id"], "name": "Resolved disease", "associatedTargets": {"rows": []}}}

    monkeypatch.setattr(api._meta_api, "map_ids", fake_map_ids)
    monkeypatch.setattr(api._disease_api, "get_disease_associated_targets", fake_associations)

    result = await api.get_drug_repurposing_candidates(
        client=object(),
        efo_id="disease by name",
    )

    assert calls["resolved_id"] == "EFO_9999999"
    assert result["disease"]["id"] == "EFO_9999999"


@pytest.mark.asyncio
async def test_get_drug_repurposing_candidates_lists_ambiguous_disease_names(
    monkeypatch,
):
    api = WorkflowApi()

    async def fake_map_ids(*_args, **_kwargs):
        hits = [
            {"id": "MONDO_1", "name": "lung carcinoma", "score": 1},
            {"id": "MONDO_2", "name": "lung neoplasm", "score": 1},
        ]
        return {"mapIds": {"mappings": [{"term": "lung tumour", "hits": hits}]}}

    monkeypatch.setattr(api._meta_api, "map_ids", fake_map_ids)

    with pytest.raises(ValidationError, match="Ambiguous efo_id 'lung tumour': MONDO_1"):
        await api.get_drug_repurposing_candidates(client=object(), efo_id="lung tumour")


@pytest.mark.asyncio
async def test_get_drug_repurposing_candidates_rejects_invalid_canonical_id(
    monkeypatch,
):
    api = WorkflowApi()

    async def fake_associations(*_args, **_kwargs):
        return {"disease": None}

    monkeypatch.setattr(api._disease_api, "get_disease_associated_targets", fake_associations)

    with pytest.raises(ValidationError, match="Disease not found"):
        await api.get_drug_repurposing_candidates(
            client=object(),
            efo_id="EFO_9999999",
        )


@pytest.mark.asyncio
async def test_get_drug_repurposing_candidates_handles_empty_mappings(monkeypatch):
    api = WorkflowApi()

    async def fake_map_ids(*_args, **_kwargs):
        return {"mapIds": {"mappings": []}}

    monkeypatch.setattr(api._meta_api, "map_ids", fake_map_ids)

    with pytest.raises(ValidationError, match="Unable to resolve disease identifier"):
        await api.get_drug_repurposing_candidates(
            client=object(),
            efo_id="disease by name",
        )


async def _two_target_associations(*_args, **_kwargs):
    return {
        "disease": {
            "id": "EFO_123",
            "name": "Disease",
            "associatedTargets": {
                "rows": [
                    {"target": {"id": "ENSG_A", "approvedSymbol": "A"}, "score": 0.8},
                    {"target": {"id": "ENSG_B", "approvedSymbol": "B"}, "score": 0.7},
                ]
            },
        }
    }


@pytest.mark.asyncio
async def test_get_drug_repurposing_candidates_reports_when_every_lookup_fails(
    monkeypatch,
):
    api = WorkflowApi()

    async def failing_known_drugs(*_args, **_kwargs):
        raise RuntimeError("upstream down")

    monkeypatch.setattr(api._disease_api, "get_disease_associated_targets", _two_target_associations)
    monkeypatch.setattr(api._target_api, "get_target_known_drugs", failing_known_drugs)

    result = await api.get_drug_repurposing_candidates(client=object(), efo_id="EFO_123")

    assert result["candidates"] == []
    assert result["summary"]["targetsPassedScoreFilter"] == 2
    assert result["summary"]["targetsFailedDrugLookup"] == 2
    assert result["summary"]["targetsWithKnownDrugs"] == 0


@pytest.mark.asyncio
async def test_get_drug_repurposing_candidates_keeps_row_stage_on_support_rows(
    monkeypatch,
):
    api = WorkflowApi()

    async def fake_known_drugs(*_args, **kwargs):
        stage = "WITHDRAWAL" if kwargs["ensembl_id"] == "ENSG_A" else "PHASE_3"
        return {
            "target": {
                "knownDrugs": {
                    "rows": [
                        {
                            "maxClinicalStage": stage,
                            "phase": 0 if stage == "WITHDRAWAL" else 3,
                            "drug": {"id": "CHEMBL_X", "name": "X", "isApproved": True},
                        }
                    ]
                }
            }
        }

    monkeypatch.setattr(api._disease_api, "get_disease_associated_targets", _two_target_associations)
    monkeypatch.setattr(api._target_api, "get_target_known_drugs", fake_known_drugs)

    every_phase = await api.get_drug_repurposing_candidates(
        client=object(), efo_id="EFO_123", min_clinical_phase=0
    )
    support = every_phase["candidates"][0]["supportingTargets"]
    assert {(row["targetId"], row["maxClinicalStage"], row["phase"]) for row in support} == {
        ("ENSG_A", "WITHDRAWAL", 0),
        ("ENSG_B", "PHASE_3", 3),
    }

    # The legacy phase filter is unchanged: withdrawn rows (phase 0) fail phase >= 2.
    default_phase = await api.get_drug_repurposing_candidates(
        client=object(), efo_id="EFO_123"
    )
    support = default_phase["candidates"][0]["supportingTargets"]
    assert [row["targetId"] for row in support] == ["ENSG_B"]


def _report(n, status):
    return {
        "id": f"NCT{n:08d}",
        "source": "clinicaltrials",
        "clinicalStage": "PHASE_3",
        "trialPhase": "PHASE3",
        "trialOverallStatus": status,
        "url": f"https://clinicaltrials.gov/study/NCT{n:08d}",
    }


def _known_drug_row(row_id, stage, drug_id, statuses):
    return {
        "id": row_id,
        "maxClinicalStage": stage,
        "drug": {
            "id": drug_id,
            "name": drug_id.lower(),
            "drugType": "Small molecule",
            "maximumClinicalStage": stage,
            "description": None,
            "drugWarnings": [],
        },
        "diseases": [{"diseaseFromSource": "x", "disease": {"id": "MONDO_1", "name": "d"}}],
        "clinicalReports": [_report(i, s) for i, s in enumerate(statuses)],
    }


# Stage ties are broken only by report count, and the first report sets status.
_KNOWN_DRUG_ROWS = {
    "ENSG_T1": [
        _known_drug_row("r1", "APPROVAL", "CHEMBL_A", ["COMPLETED"]),
        _known_drug_row("r2", "APPROVAL", "CHEMBL_B", [None, "COMPLETED", "COMPLETED"]),
        _known_drug_row("r3", "APPROVAL", "CHEMBL_C", ["RECRUITING", "COMPLETED"]),
        _known_drug_row("r4", "PHASE_2", "CHEMBL_D", ["COMPLETED"] * 9),
    ],
    "ENSG_T2": [
        _known_drug_row("r5", "PHASE_3", "CHEMBL_A", []),
        _known_drug_row("r6", "PHASE_3", "CHEMBL_E", ["TERMINATED", "COMPLETED", None, "COMPLETED"]),
        _known_drug_row("r7", "WITHDRAWAL", "CHEMBL_C", ["WITHDRAWN"]),
    ],
}


class _UpstreamClient:
    """Answers the workflow's raw queries so the real known-drugs path runs."""

    async def _query(self, query, variables=None):
        if "query DiseaseAssociatedTargets" in query:
            rows = [
                {"target": {"id": "ENSG_T1", "approvedSymbol": "T1", "approvedName": "one"}, "score": 0.9},
                {"target": {"id": "ENSG_T2", "approvedSymbol": "T2", "approvedName": "two"}, "score": 0.5},
            ]
            return {"disease": {"id": "MONDO_1", "name": "d", "associatedTargets": {"count": 2, "rows": rows}}}
        if "query TargetKnownDrugs" in query:
            rows = copy.deepcopy(_KNOWN_DRUG_ROWS[variables["ensemblId"]])
            return {"target": {"drugAndClinicalCandidates": {"count": len(rows), "rows": rows}}}
        raise AssertionError(query)


# Frozen from 0.6.1: the clinical-report payload change must not alter it.
_EXPECTED_REPURPOSING = {'candidates': [{'bestAssociationScore': 0.9,
                     'bestPhase': 4,
                     'drug': {'drugType': 'Small molecule',
                              'id': 'CHEMBL_C',
                              'isApproved': True,
                              'maximumClinicalStage': 'APPROVAL',
                              'maximumClinicalTrialPhase': 4,
                              'name': 'chembl_c'},
                     'supportingTargetCount': 2,
                     'supportingTargets': [{'associationScore': 0.9,
                                            'maxClinicalStage': 'APPROVAL',
                                            'mechanismOfAction': None,
                                            'phase': 4,
                                            'status': 'RECRUITING',
                                            'targetId': 'ENSG_T1',
                                            'targetSymbol': 'T1'},
                                           {'associationScore': 0.5,
                                            'maxClinicalStage': 'WITHDRAWAL',
                                            'mechanismOfAction': None,
                                            'phase': 0,
                                            'status': 'WITHDRAWN',
                                            'targetId': 'ENSG_T2',
                                            'targetSymbol': 'T2'}]},
                    {'bestAssociationScore': 0.9,
                     'bestPhase': 4,
                     'drug': {'drugType': 'Small molecule',
                              'id': 'CHEMBL_B',
                              'isApproved': True,
                              'maximumClinicalStage': 'APPROVAL',
                              'maximumClinicalTrialPhase': 4,
                              'name': 'chembl_b'},
                     'supportingTargetCount': 1,
                     'supportingTargets': [{'associationScore': 0.9,
                                            'maxClinicalStage': 'APPROVAL',
                                            'mechanismOfAction': None,
                                            'phase': 4,
                                            'status': None,
                                            'targetId': 'ENSG_T1',
                                            'targetSymbol': 'T1'}]},
                    {'bestAssociationScore': 0.5,
                     'bestPhase': 3,
                     'drug': {'drugType': 'Small molecule',
                              'id': 'CHEMBL_E',
                              'isApproved': False,
                              'maximumClinicalStage': 'PHASE_3',
                              'maximumClinicalTrialPhase': 3,
                              'name': 'chembl_e'},
                     'supportingTargetCount': 1,
                     'supportingTargets': [{'associationScore': 0.5,
                                            'maxClinicalStage': 'PHASE_3',
                                            'mechanismOfAction': None,
                                            'phase': 3,
                                            'status': 'TERMINATED',
                                            'targetId': 'ENSG_T2',
                                            'targetSymbol': 'T2'}]}],
     'disease': {'id': 'MONDO_1', 'name': 'd'},
     'summary': {'filters': {'approvedOnly': False,
                             'minAssociationScore': 0.2,
                             'minClinicalPhase': 0},
                 'targetsEvaluated': 2,
                 'targetsFailedDrugLookup': 0,
                 'targetsPassedScoreFilter': 2,
                 'targetsWithKnownDrugs': 2,
                 'uniqueDrugCandidates': 3},
     'targets': [{'association_score': 0.9,
                  'target_id': 'ENSG_T1',
                  'target_name': 'one',
                  'target_symbol': 'T1'},
                 {'association_score': 0.5,
                  'target_id': 'ENSG_T2',
                  'target_name': 'two',
                  'target_symbol': 'T2'}]}


@pytest.mark.asyncio
async def test_repurposing_output_unchanged_by_report_counts():
    result = await WorkflowApi().get_drug_repurposing_candidates(
        _UpstreamClient(), "MONDO_1", max_drugs_per_target=2, min_clinical_phase=0
    )
    assert result == _EXPECTED_REPURPOSING
