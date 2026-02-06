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
