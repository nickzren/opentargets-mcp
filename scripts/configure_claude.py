## scripts/configure_claude.py
"""Configure Claude Desktop to use OpenTargets MCP server."""

import json
import os
import platform
import sys

# The name of our MCP server entry
SERVER_NAME = "opentargets"
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_claude_config_path():
    """
    Determines the platform-specific path for Claude Desktop's config file.
    """
    system = platform.system()
    home = os.path.expanduser("~")
    
    if system == "Darwin":  # macOS
        return os.path.join(home, "Library", "Application Support", "Claude", "claude_desktop_config.json")
    elif system == "Windows":
        # %APPDATA%
        app_data = os.getenv("APPDATA")
        if not app_data:
            print("Error: APPDATA environment variable not found.", file=sys.stderr)
            return None
        return os.path.join(app_data, "Claude", "claude_desktop_config.json")
    elif system == "Linux":
        # Follows XDG Base Directory Specification
        xdg_config_home = os.getenv("XDG_CONFIG_HOME", os.path.join(home, ".config"))
        return os.path.join(xdg_config_home, "Claude", "claude_desktop_config.json")
    else:
        print(f"Error: Unsupported operating system '{system}'.", file=sys.stderr)
        return None


def find_python_executable():
    """
    Finds the Python executable in the current environment.
    """
    # First check if we're in a virtual environment
    if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        # We're in a virtual environment
        python_path = sys.executable
        
        # Verify the environment has our package installed
        try:
            import opentargets_mcp
            return python_path
        except ImportError:
            print("Error: opentargets-mcp package not found in the current environment.", file=sys.stderr)
            print("Please install it with: uv pip install -e .", file=sys.stderr)
            return None
    
    # Check for .venv in the project directory (UV default)
    venv_path = os.path.join(PROJECT_DIR, ".venv")
    if os.path.exists(venv_path):
        if platform.system() == "Windows":
            python_path = os.path.join(venv_path, "Scripts", "python.exe")
        else:
            python_path = os.path.join(venv_path, "bin", "python")
        
        if os.path.exists(python_path):
            return python_path
    
    print("Error: No virtual environment found.", file=sys.stderr)
    print("Please create and activate a virtual environment:", file=sys.stderr)
    print("  uv venv", file=sys.stderr)
    print("  source .venv/bin/activate  # On macOS/Linux", file=sys.stderr)
    print("  .venv\\Scripts\\activate     # On Windows", file=sys.stderr)
    print("  uv pip install -e .", file=sys.stderr)
    return None


def test_server():
    """
    Test if the server can be started successfully.
    """
    print(f"Testing server module...")
    try:
        import opentargets_mcp.server
        print("✅ Server module imported successfully")
        return True
    except ImportError as e:
        print(f"Error: Failed to import opentargets_mcp.server: {e}", file=sys.stderr)
        print("Please ensure the package is installed: uv pip install -e .", file=sys.stderr)
        return False
    except Exception as e:
        print(f"Error testing server: {e}", file=sys.stderr)
        return False


def main():
    """
    Main function to configure the Claude Desktop client.
    """
    print("--- OpenTargets MCP Server Configuration for Claude Desktop ---")
    
    # 1. Find the Python executable
    python_path = find_python_executable()
    if not python_path:
        sys.exit(1)
    
    print(f"✅ Found Python executable at: {python_path}")
    print(f"✅ Project directory: {PROJECT_DIR}")
    
    # 2. Test the server
    if not test_server():
        print("\nError: Server test failed. Please ensure all dependencies are installed:", file=sys.stderr)
        print("  uv pip install -e .", file=sys.stderr)
        sys.exit(1)
    
    # 3. Find the path to the Claude config file
    config_path = get_claude_config_path()
    if not config_path:
        sys.exit(1)
    
    print(f"✅ Target Claude config file path: {config_path}")
    
    # 4. Read existing configuration
    config_dir = os.path.dirname(config_path)
    config_data = {}
    
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config_data = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Could not read existing config. A new one will be created. Error: {e}", file=sys.stderr)
            config_data = {}
    
    # 5. Update the configuration data
    if "mcpServers" not in config_data:
        config_data["mcpServers"] = {}
    
    config_data["mcpServers"][SERVER_NAME] = {
        "command": python_path,
        "args": ["-m", "opentargets_mcp.server"],
        "cwd": PROJECT_DIR
    }
    
    # 6. Write the updated configuration back to the file
    try:
        os.makedirs(config_dir, exist_ok=True)
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=2)
        
        print(f"\n✅ Successfully configured '{SERVER_NAME}' MCP server in Claude Desktop.")
        print(f"\nConfiguration details:")
        print(f"  - Server name: {SERVER_NAME}")
        print(f"  - Python path: {python_path}")
        print(f"  - Working directory: {PROJECT_DIR}")
        print("\n🔄 Please restart Claude Desktop for the changes to take effect.")
        
    except IOError as e:
        print(f"Error: Could not write to the configuration file. Please check permissions.", file=sys.stderr)
        print(f"Details: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()