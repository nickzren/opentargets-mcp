import json
import os
import platform
import shutil
import sys

# The name of our MCP server entry
SERVER_NAME = "opentargets-mcp"

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

def find_executable_path():
    """
    Finds the full path to the opentargets-mcp executable in the current environment.
    """
    path = shutil.which(SERVER_NAME)
    if not path:
        print(f"Error: Could not find the '{SERVER_NAME}' command in your PATH.", file=sys.stderr)
        print("Please make sure you have activated the correct conda/virtual environment.", file=sys.stderr)
        return None
    return path

def main():
    """
    Main function to configure the Claude Desktop client.
    """
    print("--- Open Targets MCP Server Configuration for Claude Desktop ---")

    # 1. Find the path to the opentargets-mcp executable
    executable_path = find_executable_path()
    if not executable_path:
        sys.exit(1)
    print(f"✅ Found '{SERVER_NAME}' executable at: {executable_path}")

    # 2. Find the path to the Claude config file
    config_path = get_claude_config_path()
    if not config_path:
        sys.exit(1)
    print(f"✅ Target Claude config file path: {config_path}")

    # 3. Read existing configuration
    config_dir = os.path.dirname(config_path)
    config_data = {}
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config_data = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Could not read or parse existing config file. A new one will be created. Error: {e}", file=sys.stderr)
            config_data = {} # Reset to create a fresh config

    # 4. Update the configuration data
    if "mcpServers" not in config_data:
        config_data["mcpServers"] = {}
    
    config_data["mcpServers"][SERVER_NAME] = {
        "command": executable_path
    }

    # 5. Write the updated configuration back to the file
    try:
        os.makedirs(config_dir, exist_ok=True)
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=2)
        print(f"✅ Successfully configured '{SERVER_NAME}' in Claude Desktop.")
        print("\nPlease restart Claude Desktop for the changes to take effect.")
    except IOError as e:
        print(f"Error: Could not write to the configuration file. Please check permissions.", file=sys.stderr)
        print(f"Details: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()