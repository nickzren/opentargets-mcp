# examples/genetic_target_prioritization.py

import asyncio
import json
import sys
from typing import Dict, Any, List, Optional

from opentargets_mcp.queries import OpenTargetsClient
from opentargets_mcp.tools.disease import DiseaseApi
from opentargets_mcp.tools.meta import MetaApi
from opentargets_mcp.tools.study import StudyApi
from opentargets_mcp.tools.target import TargetApi


async def prioritize_target_from_genetics(disease_name: str):
    """
    A complex drug discovery workflow that identifies and validates a drug target
    for a disease based on human genetics.
    """
    client = OpenTargetsClient()
    meta_api = MetaApi()
    study_api = StudyApi()
    target_api = TargetApi()

    print(f"--- Starting Genetic Target Prioritization for: {disease_name} ---")

    try:
        # 1. Use map_ids and iterate through hits to find a valid disease ID
        print(f"\nStep 1: Finding EFO ID for '{disease_name}' using map_ids...")
        map_results = await meta_api.map_ids(client, [disease_name], entity_names=["disease"])
        
        mappings = map_results.get("mapIds", {}).get("mappings", [])
        if not mappings or not mappings[0].get("hits"):
            print(f"Error: Could not find a mapping for disease '{disease_name}'.")
            return
            
        # CORRECTED LOGIC: Find the first valid EFO or MONDO id in the list of hits
        disease_hit = None
        for hit in mappings[0]["hits"]:
            if hit["id"].startswith('EFO') or hit["id"].startswith('MONDO'):
                disease_hit = hit
                break # Found the first valid disease, stop looking

        if not disease_hit:
            print(f"Error: Could not find a suitable EFO or MONDO ID for '{disease_name}' in the mapping results.")
            return

        disease_id = disease_hit["id"]
        disease_display_name = disease_hit["name"]
        print(f"-> Found '{disease_display_name}' (ID: {disease_id})")

        # 2. Find associated GWAS studies for the disease
        print("\nStep 2: Finding associated GWAS studies...")
        studies_result = await study_api.get_studies_by_disease(client, [disease_id], page_size=50)
        studies = studies_result.get("studies", {}).get("rows", [])
        if not studies:
            print(f"No GWAS studies found for '{disease_display_name}'.")
            return
        
        sorted_studies = sorted(studies, key=lambda s: s.get("nSamples") or 0, reverse=True)
        
        # 3. Find a study that HAS credible sets by iterating through the top studies
        print("\nStep 3: Searching for a study with available credible sets...")
        top_study_id = None
        lead_credible_set = None

        for study in sorted_studies[:10]: # Check top 10
            print(f"  - Checking study {study['id']}...")
            credible_sets_result = await study_api.get_study_credible_sets(client, study['id'], page_size=1)
            credible_sets = credible_sets_result.get("study", {}).get("credibleSets", {}).get("rows", [])
            if credible_sets:
                top_study_id = study['id']
                lead_credible_set = credible_sets[0]
                print(f"-> Found credible set in study '{top_study_id}'")
                break
        
        if not top_study_id or not lead_credible_set:
            print("-> Could not find any studies with available credible sets in the top 10 results.")
            return

        study_locus_id = lead_credible_set.get("studyLocusId")
        print(f"-> Focusing on lead credible set: {study_locus_id}")

        # 4. Analyze the lead credible set to find the most likely causal gene (via L2G)
        print("\nStep 4: Analyzing credible set to find the prioritized gene (L2G)...")
        locus_details_result = await study_api.get_credible_set_by_id(client, study_locus_id)
        l2g_predictions = locus_details_result.get("credibleSet", {}).get("l2GPredictions", {}).get("rows", [])
        if not l2g_predictions:
            print(f"No Locus-to-Gene predictions found for {study_locus_id}.")
            return
            
        prioritized_target_info = l2g_predictions[0].get("target", {})
        target_id = prioritized_target_info.get("id")
        target_symbol = prioritized_target_info.get("approvedSymbol")
        l2g_score = l2g_predictions[0].get("score")
        print(f"-> Prioritized Target: '{target_symbol}' (Ensembl: {target_id}) with L2G score: {l2g_score:.2f}")

        # 5. Perform a validation/druggability assessment on the prioritized target
        print(f"\nStep 5: Building validation profile for '{target_symbol}'...")
        tractability_result = await target_api.get_target_tractability(client, target_id)
        safety_result = await target_api.get_target_safety_information(client, target_id)
        known_drugs_result = await target_api.get_target_known_drugs(client, target_id, page_size=5)

        # 6. Assemble and print the final "Target Dossier"
        dossier = {
            "query_disease": disease_display_name,
            "genetic_evidence": {
                "top_gwas_study": top_study_id,
                "lead_credible_set": study_locus_id,
                "l2g_prediction_score": l2g_score
            },
            "prioritized_target": {
                "symbol": target_symbol,
                "ensembl_id": target_id
            },
            "validation_profile": {
                "tractability": tractability_result.get("target", {}).get("tractability", []),
                "safety_liabilities_count": len(safety_result.get("target", {}).get("safetyLiabilities", [])),
                "known_drugs_count": known_drugs_result.get("target", {}).get("knownDrugs", {}).get("count", 0),
                "known_drugs_examples": [drug.get("drug", {}).get("name") for drug in known_drugs_result.get("target", {}).get("knownDrugs", {}).get("rows", [])]
            }
        }

        print("\n--- Workflow Complete: Genetically-Validated Target Dossier ---")
        print(json.dumps(dossier, indent=2))

    except Exception as e:
        print(f"An unexpected error occurred: {e}", file=sys.stderr)
    finally:
        await client.close()
        print("\nAPI client session closed.")


def main():
    if len(sys.argv) < 2:
        print("Usage: python examples/genetic_target_prioritization.py \"<disease_name>\"")
        print("Example: python examples/genetic_target_prioritization.py \"inflammatory bowel disease\"")
        sys.exit(1)
    
    disease_name = sys.argv[1]
    asyncio.run(prioritize_target_from_genetics(disease_name))

if __name__ == "__main__":
    main()