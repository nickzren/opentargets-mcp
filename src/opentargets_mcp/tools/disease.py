# src/opentargets_mcp/tools/disease.py
"""
Defines API methods and MCP tools related to 'Disease' entities in Open Targets.
"""
from typing import Any, Dict, Optional
import mcp.types as types
from ..queries import OpenTargetsClient # Relative import

class DiseaseApi:
    """
    Contains methods to query disease-specific data from the Open Targets GraphQL API.
    """

    async def get_disease_info(self, client: OpenTargetsClient, efo_id: str) -> Dict[str, Any]:
        """Get detailed information about a specific disease by its EFO ID."""
        graphql_query = """
        query DiseaseInfo($efoId: String!) {
            disease(efoId: $efoId) {
                id
                name
                description
                synonyms { # DiseaseSynonym
                    relation
                    terms
                }
                therapeuticAreas { # OntologyTerm
                     id
                     name
                }
                dbXRefs # list of strings
                # Removed 'ontology' field as it's not directly on Disease type as structured before.
                # Ontology information is typically within therapeuticAreas or implied by EFO structure.
            }
        }
        """
        return await client._query(graphql_query, {"efoId": efo_id})

    async def get_disease_associated_targets(self, client: OpenTargetsClient, efo_id: str, page_index: int = 0, page_size: int = 10) -> Dict[str, Any]:
        """Get targets associated with a specific disease."""
        graphql_query = """
        query DiseaseAssociatedTargets($efoId: String!, $pageIndex: Int!, $pageSize: Int!) {
            disease(efoId: $efoId) {
                id
                name
                associatedTargets(page: {index: $pageIndex, size: $pageSize}) {
                    count
                    rows { # TargetDiseaseAssociation
                        target { # Target
                            id
                            approvedSymbol
                            approvedName
                            biotype
                        }
                        score # Overall association score
                        datatypeScores { # AssociationScore
                            id # datasourceId
                            score
                        }
                    }
                }
            }
        }
        """
        return await client._query(graphql_query, {"efoId": efo_id, "pageIndex": page_index, "pageSize": page_size})

    async def get_disease_phenotypes(self, client: OpenTargetsClient, efo_id: str, page_index: int = 0, page_size: int = 10) -> Dict[str, Any]:
        """Get HPO phenotype annotations for a disease."""
        graphql_query = """
        query DiseasePhenotypes($efoId: String!, $pageIndex: Int!, $pageSize: Int!) {
            disease(efoId: $efoId) {
                id
                name
                phenotypes(page: {index: $pageIndex, size: $pageSize}) { # Paginated DiseasePhenotype
                    count
                    rows { # DiseasePhenotype
                        phenotypeHPO { # OntologyTerm (HPO)
                            id
                            name
                            description
                        }
                        phenotypeEFO { # OntologyTerm (EFO, if available)
                            id
                            name
                        }
                        evidence { # DiseasePhenotypeEvidence (Array)
                            aspect 
                            bioCuration 
                            diseaseFromSource
                            diseaseFromSourceId
                            evidenceType 
                            frequency # Corrected: Now a String, not an object
                            # modifiers # Assuming modifiers is also a String or list of Strings based on schema
                            # onset # Assuming onset is also a String or list of Strings based on schema
                            # If modifiers and onset are objects, they need specific subfields.
                            # For now, let's assume they are simple strings if the API returns them as such.
                            # If they are objects, the API error would guide further correction.
                            # Based on schema, DiseasePhenotypeEvidence has:
                            # frequency: String (e.g. "HP:0040283")
                            # modifiers: [OntologyTerm!] (so this should be modifiers { id name })
                            # onset: [OntologyTerm!] (so this should be onset { id name })
                            modifiers { id name } # Corrected based on schema
                            onset { id name }     # Corrected based on schema
                            qualifierNot 
                            references 
                            resource 
                            sex
                        }
                    }
                }
            }
        }
        """
        return await client._query(graphql_query, {"efoId": efo_id, "pageIndex": page_index, "pageSize": page_size})

    async def get_disease_otar_projects(self, client: OpenTargetsClient, efo_id: str) -> Dict[str, Any]:
        """Get OTAR (Open Targets Associated Research) projects related to a disease."""
        graphql_query = """
        query DiseaseOTARProjects($efoId: String!) {
            disease(efoId: $efoId) {
                id
                name
                otarProjects { # Array of OTARProject
                    otarCode
                    projectName
                    status
                    reference
                    integratesInPPP # Public Private Partnership
                }
            }
        }
        """
        return await client._query(graphql_query, {"efoId": efo_id})


DISEASE_TOOLS = [
    types.Tool(
        name="get_disease_info",
        description="Get detailed information about a specific disease by its EFO ID (e.g., EFO_0000270 for asthma).",
        inputSchema={
            "type": "object",
            "properties": {"efo_id": {"type": "string", "description": "EFO ID of the disease."}},
            "required": ["efo_id"]
        }
    ),
    types.Tool(
        name="get_disease_associated_targets",
        description="Get targets associated with a specific disease.",
        inputSchema={
            "type": "object",
            "properties": {
                "efo_id": {"type": "string", "description": "EFO ID of the disease."},
                "page_index": {"type": "number", "description": "Page number for results (default: 0).", "default": 0},
                "page_size": {"type": "number", "description": "Number of results per page (default: 10).", "default": 10}
            },
            "required": ["efo_id"]
        }
    ),
    types.Tool(
        name="get_disease_phenotypes",
        description="Get HPO (Human Phenotype Ontology) phenotype annotations for a disease.",
        inputSchema={
            "type": "object",
            "properties": {
                "efo_id": {"type": "string", "description": "EFO ID of the disease."},
                "page_index": {"type": "number", "description": "Page number for results (default: 0).", "default": 0},
                "page_size": {"type": "number", "description": "Number of results per page (default: 10).", "default": 10}
            },
            "required": ["efo_id"]
        }
    ),
    types.Tool(
        name="get_disease_otar_projects",
        description="Get OTAR (Open Targets Associated Research) projects related to a disease.",
        inputSchema={
            "type": "object",
            "properties": {"efo_id": {"type": "string", "description": "EFO ID of the disease."}},
            "required": ["efo_id"]
        }
    )
]
