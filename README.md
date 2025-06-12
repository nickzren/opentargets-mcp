# Open Targets MCP Server

A standalone Model Context Protocol (MCP) server that exposes the Open Targets Platform GraphQL API as a set of tools.

### Quick Start

1. **Install UV**
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. **Setup**
   ```bash
   git clone https://github.com/nickzren/opentargets-mcp.git
   cd opentargets-mcp
   uv venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   uv pip install -e .
   ```

3. **Configure Claude Desktop**
   ```bash
   python scripts/configure_claude.py
   ```
   Then restart Claude Desktop.

## Usage

### Running the Server
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