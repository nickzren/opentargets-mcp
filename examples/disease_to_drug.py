# examples/disease_to_drug.py

import asyncio
import json
import sys
from typing import Dict, Any

from opentargets_mcp.queries import OpenTargetsClient
from opentargets_mcp.tools.disease import DiseaseApi
from opentargets_mcp.tools.search import SearchApi
from opentargets_mcp.tools.target import TargetApi


async def find_drugs_for_disease(disease_name: str):
    """
    An example workflow that starts with a disease, finds associated targets,
    and then identifies drugs known to modulate those targets.
    """
    client = OpenTargetsClient()
    search_api = SearchApi()
    disease_api = DiseaseApi()
    target_api = TargetApi()

    print(f"--- Starting workflow for disease: {disease_name} ---")

    try:
        # 1. Find the disease ID (EFO ID) using the search tool
        print(f"\nStep 1: Searching for disease '{disease_name}' to get its EFO ID...")
        search_results = await search_api.search_entities(client, disease_name, entity_names=["disease"], page_size=1)
        disease_info = search_results.get("search", {}).get("hits", [])

        if not disease_info:
            print(f"Error: Could not find disease '{disease_name}'. Please try another name.")
            return

        disease_id = disease_info[0]["id"]
        disease_display_name = disease_info[0]["name"]
        print(f"Found: '{disease_display_name}' with EFO ID: {disease_id}")

        # 2. Find the top 5 targets associated with the disease
        print(f"\nStep 2: Finding top 5 associated targets for '{disease_display_name}'...")
        associated_targets_result = await disease_api.get_disease_associated_targets(client, disease_id, page_size=5)
        targets = associated_targets_result.get("disease", {}).get("associatedTargets", {}).get("rows", [])

        if not targets:
            print(f"No associated targets found for '{disease_display_name}'.")
            return

        print(f"Found {len(targets)} targets. Now finding known drugs for each.")

        # 3. For each target, find known drugs that modulate it
        results: Dict[str, Any] = {
            "disease": {"name": disease_display_name, "id": disease_id},
            "associated_drugs_by_target": []
        }

        for assoc in targets:
            target = assoc.get('target', {})
            target_id = target.get('id')
            target_symbol = target.get('approvedSymbol')
            association_score = assoc.get('score')

            if not target_id:
                continue

            print(f"\nStep 3: Finding drugs for target '{target_symbol}' (ID: {target_id})...")
            known_drugs_result = await target_api.get_target_known_drugs(client, target_id)
            drugs = known_drugs_result.get("target", {}).get("knownDrugs", {}).get("rows", [])

            drug_info_list = []
            if drugs:
                for drug_entry in drugs:
                    drug = drug_entry.get('drug', {})
                    drug_info_list.append({
                        "name": drug.get("name"),
                        "id": drug.get("id"),
                        "phase": drug_entry.get("phase"),
                        "mechanism": drug_entry.get("mechanismOfAction")
                    })

            results["associated_drugs_by_target"].append({
                "target_symbol": target_symbol,
                "target_id": target_id,
                "association_score": association_score,
                "known_drugs": drug_info_list
            })

        # 4. Print the final summary
        print("\n--- Workflow Complete: Summary ---")
        print(json.dumps(results, indent=2))
        print("\nThis summary shows the top targets for the disease and the drugs known to interact with them.")

    except Exception as e:
        print(f"An unexpected error occurred: {e}", file=sys.stderr)
    finally:
        await client.close()
        print("\nAPI client session closed.")


def main():
    """
    Main function to run the example application.
    """
    if len(sys.argv) < 2:
        print("Usage: python examples/disease_to_drug.py \"<disease_name>\"")
        print("Example: python examples/disease_to_drug.py \"melanoma\"")
        sys.exit(1)

    disease_name = sys.argv[1]

    try:
        asyncio.run(find_drugs_for_disease(disease_name))
    except KeyboardInterrupt:
        print("\nExiting...")


if __name__ == "__main__":
    main()