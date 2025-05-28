# examples/target_validation_profile.py

import asyncio
import json
import sys
from typing import Dict, Any

from opentargets_mcp.queries import OpenTargetsClient
from opentargets_mcp.tools.search import SearchApi
from opentargets_mcp.tools.target import TargetApi


async def generate_target_validation_profile(target_symbol: str):
    """
    An example workflow that starts with a target symbol, and builds a profile
    to help assess its potential as a drug target.
    """
    client = OpenTargetsClient()
    search_api = SearchApi()
    target_api = TargetApi()

    print(f"--- Starting validation profile workflow for target: {target_symbol} ---")

    try:
        # 1. Find the Ensembl ID for the target symbol
        print(f"\nStep 1: Searching for target '{target_symbol}' to get its Ensembl ID...")
        search_results = await search_api.search_entities(client, target_symbol, entity_names=["target"], page_size=1)
        target_search_info = search_results.get("search", {}).get("hits", [])

        if not target_search_info:
            print(f"Error: Could not find target '{target_symbol}'. Please try another name.")
            return

        target_id = target_search_info[0]["id"]
        display_symbol = target_search_info[0].get("object", {}).get("approvedSymbol", target_symbol)
        print(f"Found: '{display_symbol}' with Ensembl ID: {target_id}")

        # 2. Assess the target's tractability for small molecules and antibodies
        print(f"\nStep 2: Assessing druggability and tractability...")
        tractability_result = await target_api.get_target_tractability(client, target_id)
        tractability_data = tractability_result.get("target", {}).get("tractability", [])

        # 3. Find any known drugs that already modulate this target
        print("\nStep 3: Fetching known drugs...")
        known_drugs_result = await target_api.get_target_known_drugs(client, target_id, page_size=10)
        known_drugs = known_drugs_result.get("target", {}).get("knownDrugs", {}).get("rows", [])

        # 4. Find the most significant associated diseases to understand its therapeutic context
        print("\nStep 4: Fetching top associated diseases...")
        diseases_result = await target_api.get_target_associated_diseases(client, target_id, page_size=5)
        associated_diseases = diseases_result.get("target", {}).get("associatedDiseases", {}).get("rows", [])

        # 5. Assemble and print the final summary
        summary: Dict[str, Any] = {
            "target": {"symbol": display_symbol, "id": target_id},
            "tractability_assessment": tractability_data,
            "known_drugs": [
                {
                    "name": drug.get("drug", {}).get("name"),
                    "phase": drug.get("phase"),
                    "mechanism": drug.get("mechanismOfAction"),
                    "disease": drug.get("disease", {}).get("name")
                } for drug in known_drugs
            ],
            "top_associated_diseases": [
                {
                    "name": disease.get("disease", {}).get("name"),
                    "score": disease.get("score")
                } for disease in associated_diseases
            ]
        }

        print("\n--- Workflow Complete: Target Validation Profile ---")
        print(json.dumps(summary, indent=2))
        print("\nThis profile provides an overview of the target's potential for drug development.")

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
        print("Usage: python examples/target_validation_profile.py <target_symbol>")
        print("Example: python examples/target_validation_profile.py BRAF")
        sys.exit(1)

    target_symbol = sys.argv[1]

    try:
        asyncio.run(generate_target_validation_profile(target_symbol))
    except KeyboardInterrupt:
        print("\nExiting...")


if __name__ == "__main__":
    main()