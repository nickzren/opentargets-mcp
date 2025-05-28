# examples/drug_safety_profile.py

import asyncio
import json
import sys
from typing import Dict, Any

from opentargets_mcp.queries import OpenTargetsClient
from opentargets_mcp.tools.drug import DrugApi
from opentargets_mcp.tools.search import SearchApi


async def generate_drug_safety_profile(drug_name: str):
    """
    An example workflow that starts with a drug, investigates its safety warnings,
    adverse events, and mechanism of action.
    """
    client = OpenTargetsClient()
    search_api = SearchApi()
    drug_api = DrugApi()

    print(f"--- Starting safety profile workflow for drug: {drug_name} ---")

    try:
        # 1. Find the drug ID (ChEMBL ID) using the search tool
        print(f"\nStep 1: Searching for drug '{drug_name}' to get its ChEMBL ID...")
        search_results = await search_api.search_entities(client, drug_name, entity_names=["drug"], page_size=1)
        drug_search_info = search_results.get("search", {}).get("hits", [])

        if not drug_search_info:
            print(f"Error: Could not find drug '{drug_name}'. Please try another name.")
            return

        drug_id = drug_search_info[0]["id"]
        drug_display_name = drug_search_info[0]["name"]
        print(f"Found: '{drug_display_name}' with ChEMBL ID: {drug_id}")

        # 2. Get drug warnings and withdrawal information
        print(f"\nStep 2: Checking for black box warnings and withdrawal status...")
        drug_warnings = await drug_api.get_drug_warnings(client, drug_id)
        drug_data = drug_warnings.get("drug", {})
        has_black_box_warning = drug_data.get("blackBoxWarning", False)
        is_withdrawn = drug_data.get("hasBeenWithdrawn", False)
        print(f" - Black Box Warning: {has_black_box_warning}")
        print(f" - Has Been Withdrawn: {is_withdrawn}")

        # 3. Get the top 5 most significant adverse events
        print("\nStep 3: Fetching top 5 significant adverse events...")
        adverse_events_result = await drug_api.get_drug_adverse_events(client, drug_id, page_size=5)
        adverse_events = adverse_events_result.get("drug", {}).get("adverseEvents", {}).get("rows", [])

        # 4. Get the drug's mechanism of action by finding its linked targets
        print("\nStep 4: Fetching linked targets to understand mechanism of action...")
        linked_targets_result = await drug_api.get_drug_linked_targets(client, drug_id)
        linked_targets = linked_targets_result.get("drug", {}).get("linkedTargets", {}).get("rows", [])

        # 5. Assemble and print the final summary
        summary: Dict[str, Any] = {
            "drug": {"name": drug_display_name, "id": drug_id},
            "safety_summary": {
                "has_black_box_warning": has_black_box_warning,
                "is_withdrawn_from_market": is_withdrawn,
                "top_adverse_events": [{"event": event.get("name"), "count": event.get("count"), "logLR": event.get("logLR")} for event in adverse_events]
            },
            "mechanism_of_action_targets": [{"symbol": target.get("approvedSymbol"), "id": target.get("id")} for target in linked_targets]
        }

        print("\n--- Workflow Complete: Drug Safety Profile Summary ---")
        print(json.dumps(summary, indent=2))

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
        print("Usage: python examples/drug_safety_profile.py \"<drug_name>\"")
        print("Example: python examples/drug_safety_profile.py \"vemurafenib\"")
        sys.exit(1)

    drug_name = sys.argv[1]

    try:
        asyncio.run(generate_drug_safety_profile(drug_name))
    except KeyboardInterrupt:
        print("\nExiting...")


if __name__ == "__main__":
    main()