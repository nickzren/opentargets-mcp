# Open Targets MCP Server

A Model Context Protocol (MCP) server that exposes the Open Targets Platform GraphQL API as a set of tools for use with Claude Desktop and other MCP-compatible clients.

## Prerequisites

- Python 3.12+ with pip

## Quick Start

### 1. Install UV
UV is a fast Python package and project manager.

```bash
pip install uv
```

### 2. Install MCPM (MCP Manager)
MCPM is a package manager for MCP servers that simplifies installation and configuration.

```bash
pip install mcpm
```

This works on Windows, macOS, and Linux.

### 3. Setup the MCP Server
```bash
cd opentargets-mcp
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -e .
```

### 4. Add the Server to Claude Desktop
```bash
# Make sure you're in the project directory
cd opentargets-mcp

# Set Claude as the target client
mcpm target set @claude-desktop

# Get the full Python path from your virtual environment
# On macOS/Linux:
source .venv/bin/activate
PYTHON_PATH=$(which python)

# On Windows (PowerShell):
# .venv\Scripts\activate
# $PYTHON_PATH = (Get-Command python).Path

# Add the OpenTargets MCP server
mcpm import stdio opentargets \
  --command "$PYTHON_PATH" \
  --args "-m opentargets_mcp.server"
```
Then restart Claude Desktop.

## Usage

### Running the Server Standalone
```bash
opentargets-mcp
```

### Example Scripts
```bash
python examples/target_validation_profile.py EGFR
python examples/disease_to_drug.py "schizophrenia"
python examples/drug_safety_profile.py "osimertinib"
python examples/genetic_target_prioritization.py "inflammatory bowel disease"
```

### AI Agent Example
```bash
# Create .env file with your OpenAI API key
echo "OPENAI_API_KEY=your_key_here" > .env

# Run agent
python examples/react_agent.py
```

## Development

```bash
# Run tests
pytest tests/ -v
```