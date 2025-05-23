import mcp.types as types

TOOLS = [
    types.Tool(
        name="search_targets",
        description="Search for drug targets by gene symbol or name",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Gene symbol or target name to search"
                },
                "size": {
                    "type": "number",
                    "description": "Number of results to return (default: 10)",
                    "default": 10
                }
            },
            "required": ["query"]
        }
    ),
    types.Tool(
        name="get_target_info",
        description="Get detailed information about a specific target",
        inputSchema={
            "type": "object",
            "properties": {
                "ensembl_id": {
                    "type": "string",
                    "description": "Ensembl ID of the target (e.g., ENSG00000141510)"
                }
            },
            "required": ["ensembl_id"]
        }
    ),
    types.Tool(
        name="get_target_diseases",
        description="Get diseases associated with a target",
        inputSchema={
            "type": "object",
            "properties": {
                "ensembl_id": {
                    "type": "string",
                    "description": "Ensembl ID of the target"
                },
                "page": {
                    "type": "number",
                    "description": "Page number (default: 0)",
                    "default": 0
                },
                "size": {
                    "type": "number",
                    "description": "Results per page (default: 10)",
                    "default": 10
                }
            },
            "required": ["ensembl_id"]
        }
    ),
    types.Tool(
        name="get_target_drugs",
        description="Get drugs/compounds targeting a specific gene",
        inputSchema={
            "type": "object",
            "properties": {
                "ensembl_id": {
                    "type": "string",
                    "description": "Ensembl ID of the target"
                }
            },
            "required": ["ensembl_id"]
        }
    ),
    types.Tool(
        name="search_diseases",
        description="Search for diseases by name or EFO ID",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Disease name or EFO ID"
                },
                "size": {
                    "type": "number",
                    "description": "Number of results (default: 10)",
                    "default": 10
                }
            },
            "required": ["query"]
        }
    ),
    types.Tool(
        name="get_disease_targets",
        description="Get targets associated with a disease",
        inputSchema={
            "type": "object",
            "properties": {
                "efo_id": {
                    "type": "string",
                    "description": "EFO ID of the disease (e.g., EFO_0000270)"
                },
                "page": {
                    "type": "number",
                    "description": "Page number (default: 0)",
                    "default": 0
                },
                "size": {
                    "type": "number",
                    "description": "Results per page (default: 10)",
                    "default": 10
                }
            },
            "required": ["efo_id"]
        }
    ),
    types.Tool(
        name="get_evidence",
        description="Get evidence linking a target to a disease",
        inputSchema={
            "type": "object",
            "properties": {
                "ensembl_id": {
                    "type": "string",
                    "description": "Ensembl ID of the target"
                },
                "efo_id": {
                    "type": "string",
                    "description": "EFO ID of the disease"
                },
                "datasourceIds": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Filter by specific datasources (optional)"
                },
                "size": {
                    "type": "number",
                    "description": "Number of evidence items to return (default: 10)",
                    "default": 10
                }
            },
            "required": ["ensembl_id", "efo_id"]
        }
    ),
    types.Tool(
        name="get_target_safety",
        description="Get safety information for a target",
        inputSchema={
            "type": "object",
            "properties": {
                "ensembl_id": {
                    "type": "string",
                    "description": "Ensembl ID of the target"
                }
            },
            "required": ["ensembl_id"]
        }
    ),
    types.Tool(
        name="get_target_tractability",
        description="Get tractability assessment for a target",
        inputSchema={
            "type": "object",
            "properties": {
                "ensembl_id": {
                    "type": "string",
                    "description": "Ensembl ID of the target"
                }
            },
            "required": ["ensembl_id"]
        }
    ),
    types.Tool(
        name="get_drug_warnings",
        description="Get safety warnings and adverse events for a drug",
        inputSchema={
            "type": "object",
            "properties": {
                "chembl_id": {
                    "type": "string",
                    "description": "ChEMBL ID of the drug (e.g., CHEMBL1201583)"
                }
            },
            "required": ["chembl_id"]
        }
    )
]