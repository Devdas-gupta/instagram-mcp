"""
setup.py — Venv-first portable setup wizard for Instagram MCP.

Handles:
  1. Creation of local virtual environment (.venv) using target validated interpreter
  2. Isolated pip updates and dependency installation
  3. Playwright browser downloading inside venv
  4. Merging JSON-RPC configurations with space and backslash support
  5. Post-installation startup self-checks
"""

import sys
import os
import json
import subprocess
from pathlib import Path

# Resolve relocatable paths relative to this script
PROJECT_ROOT = Path(__file__).parent.resolve()


def run_command(args: list[str], cwd: Path | None = None) -> bool:
    """Run shell command silently in subprocess, logging output on failure."""
    try:
        subprocess.run(args, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return True
    except subprocess.CalledProcessError as exc:
        print(f"\n❌ Command failed: {' '.join(args)}")
        if exc.stdout:
            print(f"Stdout:\n{exc.stdout.decode('utf-8', errors='ignore')}")
        if exc.stderr:
            print(f"Stderr:\n{exc.stderr.decode('utf-8', errors='ignore')}")
        return False
    except Exception as exc:
        print(f"\n❌ Unexpected error running command: {exc}")
        return False


def get_venv_paths() -> tuple[Path, Path]:
    """Return paths to virtualenv folder and python executable based on OS."""
    venv_dir = PROJECT_ROOT / ".venv"
    if sys.platform == "win32":
        venv_python = venv_dir / "Scripts" / "python.exe"
    else:
        venv_python = venv_dir / "bin" / "python"
    return venv_dir, venv_python


def merge_claude_config(venv_python: Path) -> str | None:
    """Safely merge instagram-mcp configuration into Claude Desktop config."""
    if sys.platform == "win32":
        appdata = os.getenv("APPDATA")
        if not appdata:
            return None
        claude_path = Path(appdata) / "Claude" / "claude_desktop_config.json"
    elif sys.platform == "darwin":
        claude_path = Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    else:
        return None

    # Ensure config folder exists
    claude_path.parent.mkdir(parents=True, exist_ok=True)

    config_data = {}
    if claude_path.exists():
        try:
            with open(claude_path, "r", encoding="utf-8") as f:
                config_data = json.load(f)
        except Exception as exc:
            print(f"⚠️ Existing Claude config was not readable: {exc}. Creating fresh config.")

    if not isinstance(config_data, dict):
        config_data = {}

    if "mcpServers" not in config_data:
        config_data["mcpServers"] = {}

    # Generate portable posix paths for JSON safety (resolves space and escaping issues)
    cmd_path = venv_python.as_posix()
    script_path = (PROJECT_ROOT / "server.py").as_posix()
    py_path_env = PROJECT_ROOT.as_posix()

    config_data["mcpServers"]["instagram-mcp"] = {
        "command": cmd_path,
        "args": [script_path, "--transport", "stdio"],
        "env": {
            "PYTHONPATH": py_path_env
        }
    }

    try:
        with open(claude_path, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=2)
        return str(claude_path)
    except Exception as exc:
        print(f"❌ Failed writing Claude config: {exc}")
        return None


def write_local_configs(venv_python: Path) -> None:
    """Create local configuration snapshots in configs/ directory."""
    configs_dir = PROJECT_ROOT / "configs"
    configs_dir.mkdir(exist_ok=True)

    cmd_path = venv_python.as_posix()
    script_path = (PROJECT_ROOT / "server.py").as_posix()
    py_path_env = PROJECT_ROOT.as_posix()

    mcp_block = {
        "instagram-mcp": {
            "command": cmd_path,
            "args": [script_path, "--transport", "stdio"],
            "env": {
                "PYTHONPATH": py_path_env
            }
        }
    }

    # Claude/Cursor/Antigravity format
    claude_cursor_format = {"mcpServers": mcp_block}
    with open(configs_dir / "claude_desktop_config.json", "w", encoding="utf-8") as f:
        json.dump(claude_cursor_format, f, indent=2)
    with open(configs_dir / "cursor_mcp_config.json", "w", encoding="utf-8") as f:
        json.dump(claude_cursor_format, f, indent=2)
    with open(configs_dir / "antigravity_config.json", "w", encoding="utf-8") as f:
        json.dump(claude_cursor_format, f, indent=2)

    # Gemini CLI settings format
    gemini_cli_format = {
        "mcpServers": {
            "instagram-mcp": {
                "command": cmd_path,
                "args": [script_path, "--transport", "stdio"],
                "env": {
                    "PYTHONPATH": py_path_env
                },
                "timeout": 60
            }
        }
    }
    with open(configs_dir / "gemini_cli_config.json", "w", encoding="utf-8") as f:
        json.dump(gemini_cli_format, f, indent=2)


def main() -> None:
    # 1. Parse validated interpreter from arguments
    interpreter = sys.executable
    if "--interpreter" in sys.argv:
        try:
            idx = sys.argv.index("--interpreter")
            if idx + 1 < len(sys.argv):
                interpreter = sys.argv[idx + 1]
        except Exception:
            pass

    # Validate version of target interpreter
    try:
        res = subprocess.run(
            [interpreter, "-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"],
            capture_output=True, text=True, check=True
        )
        version_str = res.stdout.strip()
        print(f"[✓] Python {version_str} detected")
    except Exception as exc:
        print(f"❌ Target Python interpreter validation failed: {exc}")
        sys.exit(1)

    # 2. Build local directories
    for sub in ["data/sessions", "data/screenshots", "logs", "configs"]:
        (PROJECT_ROOT / sub).mkdir(parents=True, exist_ok=True)

    # 3. Create virtualenv
    venv_dir, venv_python = get_venv_paths()
    if not venv_dir.exists():
        try:
            subprocess.run(
                [interpreter, "-m", "venv", ".venv"],
                check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            print("[✓] Virtual environment created")
        except Exception as exc:
            print(f"❌ Failed to create virtual environment: {exc}")
            sys.exit(1)
    else:
        print("[✓] Virtual environment verified")

    # 4. Install dependencies inside .venv
    pip_upgrade = run_command([str(venv_python), "-m", "pip", "install", "--upgrade", "pip", "-q"])
    reqs_installed = run_command([str(venv_python), "-m", "pip", "install", "-r", "requirements.txt", "-q"])
    if pip_upgrade and reqs_installed:
        print("[✓] Dependencies installed")
    else:
        print("❌ Failed to install dependencies.")
        sys.exit(1)

    # 5. Install Playwright Chromium inside .venv
    pw_installed = run_command([str(venv_python), "-m", "playwright", "install", "chromium"])
    if pw_installed:
        print("[✓] Playwright Chromium installed")
    else:
        print("❌ Failed to install Playwright Chromium browser.")
        sys.exit(1)

    # 6. Update configurations using the absolute venv path
    claude_saved_path = merge_claude_config(venv_python)
    write_local_configs(venv_python)
    if claude_saved_path:
        print("[✓] Claude MCP config updated")
    else:
        print("[✓] Local MCP configs updated (Claude Desktop merge skipped)")

    # 7. Post-install startup validation checks
    # A. FastMCP and MCP import
    try:
        subprocess.run([str(venv_python), "-c", "import mcp, fastmcp"], check=True, capture_output=True)
    except Exception as exc:
        print(f"❌ Startup validation failed: mcp/fastmcp imports are broken inside .venv: {exc}")
        sys.exit(1)

    # B. SQLite connection & init
    try:
        script = (
            "import asyncio\n"
            "from memory import memory\n"
            "async def test():\n"
            "    await memory.connect()\n"
            "    await memory.close()\n"
            "asyncio.run(test())\n"
        )
        subprocess.run([str(venv_python), "-c", script], check=True, capture_output=True, cwd=str(PROJECT_ROOT))
    except Exception as exc:
        print(f"❌ Startup validation failed: SQLite memory database connection failed: {exc}")
        sys.exit(1)

    # C. Playwright Chromium boot check
    try:
        script = (
            "from playwright.sync_api import sync_playwright\n"
            "with sync_playwright() as p:\n"
            "    browser = p.chromium.launch(headless=True)\n"
            "    browser.close()\n"
        )
        subprocess.run([str(venv_python), "-c", script], check=True, capture_output=True)
    except Exception as exc:
        print(f"❌ Startup validation failed: Playwright Chromium verification failed: {exc}")
        sys.exit(1)

    # D. Config path resolution
    try:
        script = (
            "from config import Config\n"
            "Config.ensure_dirs()\n"
        )
        subprocess.run([str(venv_python), "-c", script], check=True, capture_output=True, cwd=str(PROJECT_ROOT))
    except Exception as exc:
        print(f"❌ Startup validation failed: Directory path generation failed: {exc}")
        sys.exit(1)

    # E. FastMCP schema validation check
    try:
        script = (
            "import asyncio\n"
            "from server import mcp\n"
            "async def test():\n"
            "    tools = await mcp.list_tools()\n"
            "    print(f'Verified {len(tools)} schemas')\n"
            "asyncio.run(test())\n"
        )
        res = subprocess.run([str(venv_python), "-c", script], check=True, capture_output=True, text=True, cwd=str(PROJECT_ROOT))
        # Log tools count
        print(f"[✓] Tool schema validation passed ({res.stdout.strip()})")
    except Exception as exc:
        print(f"❌ Startup validation failed: FastMCP tool schema generation failed: {exc}")
        if hasattr(exc, "stderr") and exc.stderr:
            print(exc.stderr)
        sys.exit(1)

    print("[✓] Startup validation passed")
    print("==========================================")
    print("🎉 Setup completed successfully!")
    print("==========================================")


if __name__ == "__main__":
    main()
