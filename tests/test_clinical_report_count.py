"""Clinical report lists become a per-row clinicalReportCount."""

import pathlib
import re

import pytest

from opentargets_mcp.tools.drug import DrugApi
from opentargets_mcp.utils import promote_clinical_candidates

from .test_clinical_candidates import _staged_candidates

_SRC = pathlib.Path(__file__).resolve().parents[1] / "src" / "opentargets_mcp" / "tools"


class _StaticClient:
    def __init__(self, response):
        self.response = response

    async def _query(self, *_args, **_kwargs):
        return self.response


def test_page_rows_carry_report_count_in_display_order():
    parent = _staged_candidates()
    promote_clinical_candidates(parent, page_size=4)

    rows = parent["knownDrugs"]["rows"]
    assert [row["id"] for row in rows] == ["c", "f", "b", "e"]
    assert [row["clinicalReportCount"] for row in rows] == [5, 2, 1, 1]
    assert not any("clinicalReports" in row or "urls" in row for row in rows)


def test_status_comes_from_the_first_report_only():
    rows = [
        {
            "id": "a",
            "maxClinicalStage": "PHASE_3",
            "clinicalReports": [{"trialOverallStatus": None}, {"trialOverallStatus": "COMPLETED"}],
        },
        {"id": "b", "maxClinicalStage": "PHASE_2", "clinicalReports": []},
        {"id": "c", "maxClinicalStage": "PHASE_1", "clinicalReports": None},
    ]
    parent = {"drugAndClinicalCandidates": {"count": 3, "rows": rows}}
    promote_clinical_candidates(parent, page_size=3)

    first, second, third = parent["knownDrugs"]["rows"]
    assert first["status"] is None and first["clinicalReportCount"] == 2
    assert "status" not in second and second["clinicalReportCount"] == 0
    # Missing data is not zero reports.
    assert "clinicalReportCount" not in third


@pytest.mark.parametrize(
    "module, query_name",
    [
        ("target/associations.py", "TargetKnownDrugs"),
        ("disease.py", "DiseaseKnownDrugs"),
        ("drug/identity.py", "DrugInfo"),
        ("drug/associations.py", "DrugLinkedDiseases"),
    ],
)
def test_queries_select_only_the_report_status(module, query_name):
    """Known-drug `status` reads trialOverallStatus; any other scalar would null it."""
    body = (_SRC / module).read_text().split(f"query {query_name}", 1)[1].split('"""', 1)[0]
    selection = re.search(r"clinicalReports\s*\{([^}]*)\}", body).group(1).split()
    assert selection == ["trialOverallStatus"]


@pytest.mark.asyncio
async def test_drug_info_counts_indication_reports_and_keeps_mechanism_urls():
    references = [{"source": "DailyMed", "ids": ["x"], "urls": ["https://example.test/x"]}]
    response = {
        "drug": {
            "id": "CHEMBL1",
            "maximumClinicalStage": "APPROVAL",
            "drugWarnings": [],
            "mechanismsOfAction": {"rows": [{"targets": [], "references": references}]},
            "indications": {
                "count": 2,
                "rows": [
                    {"disease": {"id": "D1"}, "maxClinicalStage": "PHASE_2", "clinicalReports": [{}, {}]},
                    {"disease": {"id": "D2"}, "maxClinicalStage": "APPROVAL", "clinicalReports": []},
                ],
            },
        }
    }

    result = await DrugApi().get_drug_info(_StaticClient(response), "CHEMBL1")

    indications = result["drug"]["indications"]
    assert [row["clinicalReportCount"] for row in indications["rows"]] == [2, 0]
    assert not any("clinicalReports" in row for row in indications["rows"])
    assert indications["count"] == 2
    assert result["drug"]["mechanismsOfAction"]["rows"][0]["references"] == references


@pytest.mark.asyncio
async def test_drug_linked_diseases_rows_carry_report_counts():
    rows = [
        {"id": "i1", "maxClinicalStage": "PHASE_2", "disease": {"id": "D1"}, "clinicalReports": [{}] * 3},
        {"id": "i2", "maxClinicalStage": "APPROVAL", "disease": {"id": "D2"}, "clinicalReports": []},
        {"id": "i3", "maxClinicalStage": "PHASE_1", "disease": {"id": "D3"}, "clinicalReports": None},
    ]
    response = {"drug": {"id": "CHEMBL1", "indications": {"count": 9, "rows": rows}}}

    result = await DrugApi().get_drug_linked_diseases(_StaticClient(response), "CHEMBL1")

    linked = result["drug"]["linkedDiseases"]
    # count stays len(rows), not the upstream indications count.
    assert linked["count"] == 3
    assert linked["rows"] == [
        {"id": "D1", "maxClinicalStage": "PHASE_2", "clinicalReportCount": 3},
        {"id": "D2", "maxClinicalStage": "APPROVAL", "clinicalReportCount": 0},
        {"id": "D3", "maxClinicalStage": "PHASE_1"},
    ]
