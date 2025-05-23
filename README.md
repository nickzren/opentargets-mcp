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

#### As a Standalone Server (Primary)

The main goal of this project is to run the MCP server. Once your environment is active, you can start the server with its installed command:
```bash
opentargets-mcp
```

This server can be connected to any MCP client. For example, to connect to Claude Desktop, you would configure it to use the full path to this command, which you can find by running `which opentargets-mcp`.

#### Configuring Claude Desktop

1. **Locate the configuration file** (macOS default):

   ```bash
   open "$HOME/Library/Application Support/Claude/claude_desktop_config.json"
   ```

2. **Add or merge** an entry that points Claude Desktop to your local MCP server (replace the cmd path with the one returned by `which opentargets-mcp`):

   ```json
   {
     "mcpServers": {
       "opentargets-mcp": {
         "command": "/Users/<you>/miniconda3/envs/opentargets-mcp/bin/opentargets-mcp"
       }
     }
   }
   ```

3. **Save** the file and **restart Claude Desktop**.  
   The *Open Targets MCP* server will appear in the “Search and tools” menu.

#### Running the Example AI Agent

The repository includes an example agent that demonstrates how to use the query library to build intelligent applications.

1.  **Set your API credentials:** Create or update a `.env` file in the project root:
    ```bash
    echo "OPENAI_MODEL=gpt-4.1-mini" > .env
    echo "OPENAI_API_KEY=YOUR_API_KEY" >> .env
    ```
2.  **Run the agent:**
    ```bash
    python examples/agent_app.py

    --- Open Targets ReAct Agent ---
    Ask a complex question. Type 'exit' to quit.
    
    > Find targets for metatropic dysplasia and see if TRPV4 is one of them.
    ```
***

### Testing

To verify that the query functions are working correctly, run the test suite:
```bash
pytest tests/ -v
```
