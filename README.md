# Open Targets MCP Server

A standalone Model Context Protocol (MCP) server that exposes the Open Targets Platform GraphQL API as a set of tools.

This server allows MCP-compatible clients (like Claude Desktop) to query and reason over the rich datasets available in Open Targets.

### Core Features
* Provides a comprehensive set of tools for querying Open Targets data including targets, diseases, drugs, evidence, and safety information.
* Implements the MCP standard for robust integration with external client applications.
* Includes an example AI agent demonstrating how to use the underlying library to answer complex, multi-step questions.

***

### Prerequisites
* **Mamba** or **Conda** for environment management.

***

### Setup
1.  **Clone the repository and navigate into it.**
2.  **Create and activate the environment** using the provided file. This also installs the package in editable mode.
    ```bash
    mamba env create -f environment.yml
    mamba activate opentargets-mcp
    ```

***

### Usage

#### As a Standalone Server

The main goal of this project is to run the MCP server. Once your environment is active, you can start the server with its installed command:
```bash
opentargets-mcp
```

This server can be connected to any MCP client. For example, to connect to Claude Desktop, you would configure it to use the full path to this command, which you can find by running `which opentargets-mcp`.

#### Automated Configuration for Claude Desktop

To automatically configure Claude Desktop to use this server, you can run the provided setup script. This script will find your Claude configuration file and add the necessary entries.

1.  **Make sure your conda/virtual environment is active.**
    ```bash
    mamba activate opentargets-mcp
    ```

2.  **Run the configuration script:**
    ```bash
    python scripts/configure_claude.py
    ```

3.  **Restart Claude Desktop.**
    The *Open Targets MCP* server will now appear in the “Search and tools” menu.

#### Example Scripts

The `examples` directory contains scripts that demonstrate how to use the toolset.

##### Interactive ReAct Agent

The repository includes an example agent that demonstrates how to use the query library to build intelligent applications.

1.  Set your API credentials: Create or update a .env file in the project root:
    ```bash
    echo "OPENAI_MODEL=gpt-4.1-mini" > .env
    echo "OPENAI_API_KEY=YOUR_API_KEY" >> .env
    ```

2.  Run the agent:
    ```bash
    python examples/react_agent.py

    --- Open Targets ReAct Agent ---
    Ask a complex question. Type 'exit' to quit.

    > Find targets for metatropic dysplasia and see if TRPV4 is one of them.
    ```

##### Example Workflow

```bash
python examples/target_validation_profile.py EGFR
python examples/disease_to_drug.py "schizophrenia"
python examples/drug_safety_profile.py "osimertinib"
python examples/genetic_target_prioritization.py "inflammatory bowel disease"
```

***

### Testing

To verify that the query functions are working correctly, run the test suite:
```bash
pytest tests/ -v
```
