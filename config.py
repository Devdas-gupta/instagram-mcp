"""
config.py — Central configuration for Instagram MCP Server.

Loads settings from .env, auto-detects browser paths on macOS (Apple Silicon & Intel),
and exposes a single Config singleton used throughout the project.
"""

from __future__ import annotations

import os
import platform
import sys
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv

# ─── Resolve project root & load .env ────────────────────────────────────────
PROJECT_ROOT: Path = Path(__file__).parent.resolve()
ENV_FILE: Path = PROJECT_ROOT / ".env"
load_dotenv(ENV_FILE)


# ─── Windows & macOS Browser Path Resolution ──────────────────────────────────
_LOCAL_APP_DATA = os.getenv("LOCALAPPDATA", "")
_PROGRAM_FILES = os.getenv("PROGRAMFILES", "C:\\Program Files")
_PROGRAM_FILES_X86 = os.getenv("PROGRAMFILES(X86)", "C:\\Program Files (x86)")

_CHROME_PATHS_MACOS: list[str] = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    str(Path.home() / "Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
]

_BRAVE_PATHS_MACOS: list[str] = [
    "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
    str(Path.home() / "Applications/Brave Browser.app/Contents/MacOS/Brave Browser"),
]

_CHROME_PATHS_WINDOWS: list[str] = [
    os.path.join(_PROGRAM_FILES, "Google\\Chrome\\Application\\chrome.exe"),
    os.path.join(_PROGRAM_FILES_X86, "Google\\Chrome\\Application\\chrome.exe"),
]
if _LOCAL_APP_DATA:
    _CHROME_PATHS_WINDOWS.append(os.path.join(_LOCAL_APP_DATA, "Google\\Chrome\\Application\\chrome.exe"))

_BRAVE_PATHS_WINDOWS: list[str] = [
    os.path.join(_PROGRAM_FILES, "BraveSoftware\\Brave-Browser\\Application\\brave.exe"),
    os.path.join(_PROGRAM_FILES_X86, "BraveSoftware\\Brave-Browser\\Application\\brave.exe"),
]
if _LOCAL_APP_DATA:
    _BRAVE_PATHS_WINDOWS.append(os.path.join(_LOCAL_APP_DATA, "BraveSoftware\\Brave-Browser\\Application\\brave.exe"))

_CHROME_PROFILES_MACOS: list[str] = [
    str(Path.home() / "Library/Application Support/Google/Chrome"),
]

_BRAVE_PROFILES_MACOS: list[str] = [
    str(Path.home() / "Library/Application Support/BraveSoftware/Brave-Browser"),
]

_CHROME_PROFILES_WINDOWS: list[str] = []
if _LOCAL_APP_DATA:
    _CHROME_PROFILES_WINDOWS.append(os.path.join(_LOCAL_APP_DATA, "Google\\Chrome\\User Data"))

_BRAVE_PROFILES_WINDOWS: list[str] = []
if _LOCAL_APP_DATA:
    _BRAVE_PROFILES_WINDOWS.append(os.path.join(_LOCAL_APP_DATA, "BraveSoftware\\Brave-Browser\\User Data"))


def _find_executable(candidates: list[str]) -> str | None:
    """Return the first existing path from a list of candidates."""
    for path in candidates:
        if Path(path).exists():
            return path
    return None


class ConfigMeta(type):
    @property
    def session_file(cls) -> Path:
        username = cls.get_active_username()
        if username:
            return cls.sessions_dir / username / "storage_state.json"
        return cls.sessions_dir / "instagram_session.json"

    @property
    def cookies_file(cls) -> Path:
        username = cls.get_active_username()
        if username:
            return cls.sessions_dir / username / "instagram_cookies.json"
        return cls.sessions_dir / "instagram_cookies.json"


class Config(metaclass=ConfigMeta):
    """
    Singleton configuration class.
    All values are read from env vars (with sane defaults).
    """

    # ── Browser selection ─────────────────────────────────────────────────
    browser_type: Literal["chrome", "brave"] = (
        os.getenv("BROWSER_TYPE", "chrome").lower().strip()  # type: ignore[assignment]
    )
    headless: bool = os.getenv("HEADLESS", "false").lower() in ("1", "true", "yes")

    # ── Paths ─────────────────────────────────────────────────────────────
    data_dir: Path = PROJECT_ROOT / "data"
    sessions_dir: Path = data_dir / "sessions"
    screenshots_dir: Path = data_dir / "screenshots"
    db_path: Path = data_dir / "memory.db"

    # ── Playwright timeouts (ms) ──────────────────────────────────────────
    default_timeout: int = int(os.getenv("DEFAULT_TIMEOUT_MS", "30000"))
    navigation_timeout: int = int(os.getenv("NAVIGATION_TIMEOUT_MS", "60000"))

    # ── Retry settings ────────────────────────────────────────────────────
    max_retries: int = int(os.getenv("MAX_RETRIES", "3"))
    retry_delay: float = float(os.getenv("RETRY_DELAY_S", "2.0"))

    # ── MCP Server ────────────────────────────────────────────────────────
    mcp_server_name: str = os.getenv("MCP_SERVER_NAME", "instagram-mcp")
    mcp_host: str = os.getenv("MCP_HOST", "127.0.0.1")
    mcp_port: int = int(os.getenv("MCP_PORT", "8765"))

    # ── Logging ──────────────────────────────────────────────────────────
    log_level: str = os.getenv("LOG_LEVEL", "INFO").upper()
    log_file: Path = PROJECT_ROOT / "logs" / "instagram_mcp.log"

    @classmethod
    def validate_username(cls, username: str) -> bool:
        """Check if a username matches the strict pattern to prevent path traversals."""
        import re
        if not username:
            return False
        return bool(re.match(r"^[a-zA-Z0-9._]{1,30}$", username))

    @classmethod
    def get_active_username(cls) -> str | None:
        """Read the currently active account name from active_account.json."""
        active_file = cls.sessions_dir / "active_account.json"
        if active_file.exists():
            try:
                import json
                with open(active_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                username = data.get("active_username")
                if username and cls.validate_username(username):
                    return username
            except Exception:
                pass
        return None

    @classmethod
    def get_active_account_dir(cls) -> Path | None:
        """Get the directory of the currently active account."""
        username = cls.get_active_username()
        if username:
            return cls.sessions_dir / username
        return None

    @classmethod
    def get_active_screenshots_dir(cls) -> Path:
        """Resolve screenshots subfolder dynamically per account."""
        username = cls.get_active_username()
        if username:
            d = cls.sessions_dir / username / "screenshots"
            d.mkdir(parents=True, exist_ok=True)
            return d
        return cls.screenshots_dir

    @classmethod
    def get_browser_executable(cls) -> str | None:
        """Auto-detect browser executable path for macOS and Windows."""
        if platform.system() == "Darwin":
            if cls.browser_type == "brave":
                return _find_executable(_BRAVE_PATHS_MACOS)
            return _find_executable(_CHROME_PATHS_MACOS)
        elif platform.system() == "Windows":
            if cls.browser_type == "brave":
                return _find_executable(_BRAVE_PATHS_WINDOWS)
            return _find_executable(_CHROME_PATHS_WINDOWS)
        return None

    @classmethod
    def get_browser_profile_dir(cls) -> str | None:
        """Return the default profile directory for the chosen browser."""
        if platform.system() == "Darwin":
            if cls.browser_type == "brave":
                return _find_executable(_BRAVE_PROFILES_MACOS)
            return _find_executable(_CHROME_PROFILES_MACOS)
        elif platform.system() == "Windows":
            if cls.browser_type == "brave":
                return _find_executable(_BRAVE_PROFILES_WINDOWS)
            return _find_executable(_CHROME_PROFILES_WINDOWS)
        return None

    @classmethod
    def ensure_dirs(cls) -> None:
        """Create all required directories if they don't exist."""
        for d in (cls.data_dir, cls.sessions_dir, cls.screenshots_dir, cls.log_file.parent):
            d.mkdir(parents=True, exist_ok=True)

    @classmethod
    def validate(cls) -> list[str]:
        """Return a list of validation warnings (not errors — server still runs)."""
        warnings: list[str] = []
        exe = cls.get_browser_executable()
        if exe is None:
            warnings.append(
                f"Browser executable not found for '{cls.browser_type}'. "
                "Playwright bundled Chromium will be used as fallback."
            )
        return warnings

    @classmethod
    def summary(cls) -> dict:
        return {
            "browser_type": cls.browser_type,
            "headless": cls.headless,
            "active_account": cls.get_active_username() or "None (Anonymous)",
            "db_path": str(cls.db_path),
            "mcp_server": f"{cls.mcp_host}:{cls.mcp_port}",
            "log_level": cls.log_level,
        }


# Ensure directories exist at import time
Config.ensure_dirs()

