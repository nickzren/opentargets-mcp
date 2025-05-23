import aiohttp
import asyncio
from typing import Any, Dict, List, Optional
from functools import lru_cache
import time


class OpenTargetsClient:
    def __init__(self):
        self.base_url = "https://api.platform.opentargets.org/api/v4/graphql"
        self.session = None
        self._cache = {}
        self._cache_ttl = 3600  # 1 hour
    
    async def _ensure_session(self):
        if self.session is None:
            self.session = aiohttp.ClientSession()
    
    async def _query(self, query: str, variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        await self._ensure_session()
        
        cache_key = f"{query}:{str(variables)}"
        if cache_key in self._cache:
            cached_data, timestamp = self._cache[cache_key]
            if time.time() - timestamp < self._cache_ttl:
                return cached_data
        
        payload = {"query": query}
        if variables:
            payload["variables"] = variables
        
        async with self.session.post(
            self.base_url,
            json=payload,
            headers={"Content-Type": "application/json"}
        ) as response:
            result = await response.json()
            
            if "errors" in result:
                raise Exception(f"GraphQL errors: {result['errors']}")
            
            self._cache[cache_key] = (result, time.time())
            return result
    
    async def search_targets(self, query: str, size: int = 10) -> Dict[str, Any]:
        graphql_query = """
        query SearchTargets($query: String!, $size: Int!) {
            search(queryString: $query, entityNames: ["target"], page: {size: $size, index: 0}) {
                hits {
                    id
                    entity
                    name
                    description
                    score
                    object {
                        ... on Target {
                            id
                            approvedSymbol
                            approvedName
                            biotype
                            functionDescriptions
                        }
                    }
                }
                total
            }
        }
        """
        result = await self._query(graphql_query, {"query": query, "size": size})
        return result.get("data", {})
    
    async def get_target_info(self, ensembl_id: str) -> Dict[str, Any]:
        graphql_query = """
        query TargetInfo($ensemblId: String!) {
            target(ensemblId: $ensemblId) {
                id
                approvedSymbol
                approvedName
                biotype
                functionDescriptions
                synonyms {
                    label
                    source
                }
                genomicLocation {
                    chromosome
                    start
                    end
                    strand
                }
                pathways {
                    pathway
                    pathwayId
                    topLevelTerm
                }
                subcellularLocations {
                    location
                    source
                }
                tractability {
                    label
                    modality
                    value
                }
            }
        }
        """
        result = await self._query(graphql_query, {"ensemblId": ensembl_id})
        return result.get("data", {})
    
    async def get_target_diseases(self, ensembl_id: str, page: int = 0, size: int = 10) -> Dict[str, Any]:
        graphql_query = """
        query TargetAssociatedDiseases($ensemblId: String!, $page: Int!, $size: Int!) {
            target(ensemblId: $ensemblId) {
                associatedDiseases(page: {index: $page, size: $size}) {
                    count
                    rows {
                        disease {
                            id
                            name
                            description
                            therapeuticAreas {
                                id
                                name
                            }
                        }
                        score
                        datatypeScores {
                            id
                            score
                        }
                    }
                }
            }
        }
        """
        result = await self._query(
            graphql_query,
            {"ensemblId": ensembl_id, "page": page, "size": size}
        )
        return result.get("data", {})
    
    async def get_target_drugs(self, ensembl_id: str) -> Dict[str, Any]:
        graphql_query = """
        query TargetKnownDrugs($ensemblId: String!) {
            target(ensemblId: $ensemblId) {
                knownDrugs {
                    count
                    rows {
                        drug {
                            id
                            name
                            drugType
                            maximumClinicalTrialPhase
                            hasBeenWithdrawn
                            description
                            isApproved
                            mechanismsOfAction {
                                rows {
                                    mechanismOfAction
                                    targetName
                                    actionType
                                }
                            }
                        }
                        drugId
                        targetId
                        disease {
                            id
                            name
                        }
                        phase
                        status
                        urls {
                            name
                            url
                        }
                    }
                }
            }
        }
        """
        result = await self._query(graphql_query, {"ensemblId": ensembl_id})
        return result.get("data", {})
    
    async def search_diseases(self, query: str, size: int = 10) -> Dict[str, Any]:
        graphql_query = """
        query SearchDiseases($query: String!, $size: Int!) {
            search(queryString: $query, entityNames: ["disease"], page: {size: $size, index: 0}) {
                hits {
                    id
                    entity
                    name
                    description
                    score
                    object {
                        ... on Disease {
                            id
                            name
                            description
                            therapeuticAreas {
                                id
                                name
                            }
                            synonyms {
                                relation
                                terms
                            }
                        }
                    }
                }
                total
            }
        }
        """
        result = await self._query(graphql_query, {"query": query, "size": size})
        return result.get("data", {})
    
    async def get_disease_targets(self, efo_id: str, page: int = 0, size: int = 10) -> Dict[str, Any]:
        graphql_query = """
        query DiseaseAssociatedTargets($efoId: String!, $page: Int!, $size: Int!) {
            disease(efoId: $efoId) {
                id
                name
                associatedTargets(page: {index: $page, size: $size}) {
                    count
                    rows {
                        target {
                            id
                            approvedSymbol
                            approvedName
                            biotype
                        }
                        score
                        datatypeScores {
                            id
                            score
                        }
                    }
                }
            }
        }
        """
        result = await self._query(
            graphql_query,
            {"efoId": efo_id, "page": page, "size": size}
        )
        return result.get("data", {})
    
    async def get_evidence(
        self,
        ensembl_id: str,
        efo_id: str,
        datasource_ids: Optional[List[str]] = None,
        size: int = 10,
    ) -> Dict[str, Any]:
        # ── Open Targets v4: evidences moved under the `target` object ──
        graphql_query = """
        query TargetDiseaseEvidences(
            $ensemblId: String!
            $efoId: String!
            $size: Int!
            $datasourceIds: [String!]
        ) {
            target(ensemblId: $ensemblId) {
                evidences(
                    efoIds: [$efoId]
                    datasourceIds: $datasourceIds
                    size: $size
                ) {
                    count
                    rows {
                        score
                        datasourceId
                        datatypeId
                        diseaseFromSource
                        targetFromSource
                        id
                    }
                }
            }
        }
        """

        variables = {
            "ensemblId": ensembl_id,
            "efoId": efo_id,
            "size": size,
            "datasourceIds": datasource_ids or None,  # explicit null if not filtering
        }

        result = await self._query(graphql_query, variables)

        # Preserve the old return structure expected by Step 6
        target_block = result.get("data", {}).get("target", {})
        return {"evidences": target_block.get("evidences", {})}
    
    async def get_target_safety(self, ensembl_id: str) -> Dict[str, Any]:
        graphql_query = """
        query TargetSafety($ensemblId: String!) {
            target(ensemblId: $ensemblId) {
                id
                approvedSymbol
                safetyLiabilities {
                    event
                    eventId
                    effects {
                        direction
                        dosing
                    }
                }
            }
        }
        """
        result = await self._query(graphql_query, {"ensemblId": ensembl_id})
        return result.get("data", {})
    
    async def get_target_tractability(self, ensembl_id: str) -> Dict[str, Any]:
        graphql_query = """
        query TargetTractability($ensemblId: String!) {
            target(ensemblId: $ensemblId) {
                id
                approvedSymbol
                tractability {
                    id
                    modality
                    value
                }
            }
        }
        """
        result = await self._query(graphql_query, {"ensemblId": ensembl_id})
        return result.get("data", {})
    
    async def get_drug_warnings(self, chembl_id: str) -> Dict[str, Any]:
        graphql_query = """
        query DrugWarnings($chemblId: String!) {
            drug(chemblId: $chemblId) {
                id
                name
                hasBeenWithdrawn
                blackBoxWarning
                # The 'withdrawnNotice' block has been removed
                # as it is no longer supported by the API.
            }
        }
        """
        result = await self._query(graphql_query, {"chemblId": chembl_id})
        return result.get("data", {})
    
    async def close(self):
        if self.session:
            await self.session.close()