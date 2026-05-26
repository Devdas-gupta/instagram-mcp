"""
server.py — Instagram MCP Server

Entry point.  Registers every tool with FastMCP and starts the server.
All tools are async and use Playwright under the hood.

Run:
    python server.py
or
    python server.py --transport stdio   # for Claude Desktop / Cursor
"""

from __future__ import annotations

import contextlib
import sys
from collections.abc import AsyncGenerator
from typing import Any
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

from config import Config
from logger import get_logger, console
from memory import memory
from session_manager import session_manager

# ── Import all tool modules ───────────────────────────────────────────────────
import browser_controller as bc
import instagram_tools as ig

log = get_logger(__name__)

# ─── MCP Server ───────────────────────────────────────────────────────────────

@contextlib.asynccontextmanager
async def _lifespan(app: FastMCP) -> AsyncGenerator[None, None]:  # noqa: ARG001
    """
    FastMCP lifespan hook — runs inside the server's own event loop.

    Startup: initialise the SQLite memory database.
    Shutdown: close the memory DB and Playwright browser session cleanly.
    """
    # ── Startup ───────────────────────────────────────────────────────────
    await memory.connect()
    log.info("Memory DB initialized (lifespan startup).")
    try:
        yield
    finally:
        # ── Shutdown ──────────────────────────────────────────────────────
        log.info("MCP server shutting down — cleaning up…")
        try:
            await session_manager.close()
        except Exception as exc:  # pragma: no cover
            log.warning(f"session_manager.close() raised: {exc}")
        try:
            await memory.close()
        except Exception as exc:  # pragma: no cover
            log.warning(f"memory.close() raised: {exc}")
        log.info("Cleanup complete.")


mcp = FastMCP(
    name=Config.mcp_server_name,
    lifespan=_lifespan,
    instructions="""
You have full control of a real local browser (Chrome or Brave) on macOS or Windows.
You can automate Instagram browsing, read feeds, interact with posts, manage sessions, and more.
All data stays local — no credentials stored, no cloud, no API keys required.

Key rules:
- Call open_browser first if you haven't started a session yet.
- If not logged in, call login_instagram which will direct the user to log in manually.
- Wait for the user to finish login in the browser window, then call check_login_status to verify and save the session.
- Be respectful of Instagram's rate limits — add delays between actions.
""",
)


# ═══════════════════════════════════════════════════════════════════════════════
# BROWSER CONTROL TOOLS
# ═══════════════════════════════════════════════════════════════════════════════


@mcp.tool()
async def open_browser() -> dict:
    """
    Launch the browser (Chrome or Brave as configured) and return status.
    Must be called before any other browser operations if a session hasn't started.
    """
    result = await bc.open_browser()
    await memory.log_session_event("open_browser", success=result.get("status") == "ok")
    return result


@mcp.tool()
async def open_url(url: str) -> dict:
    """
    Navigate the active browser tab to the given URL.

    Args:
        url: Full URL to navigate to (e.g., "https://www.instagram.com")
    """
    return await bc.open_url(url)


@mcp.tool()
async def click_element(selector: str, timeout_ms: int = 30000) -> dict:
    """
    Click a DOM element identified by CSS selector, XPath, or text.

    Args:
        selector: CSS selector, XPath (start with //), or text= prefix
        timeout_ms: Max wait time in milliseconds (default 30000)

    Examples:
        click_element("button.like-btn")
        click_element("//button[@aria-label='Like']")
        click_element("text=Follow")
    """
    return await bc.click_element(selector, timeout_ms)


@mcp.tool()
async def type_text(selector: str, text: str, clear_first: bool = True) -> dict:
    """
    Type text into an input field or textarea.

    Args:
        selector: CSS selector of the input element
        text: Text to type
        clear_first: Whether to clear existing text before typing (default True)
    """
    return await bc.type_text(selector, text, clear_first)


@mcp.tool()
async def scroll_page(direction: str = "down", amount: int = 500) -> dict:
    """
    Scroll the page in a given direction.

    Args:
        direction: "down" | "up" | "left" | "right"
        amount: Pixels to scroll (default 500)
    """
    return await bc.scroll_page(direction, amount)


@mcp.tool()
async def hover_element(selector: str) -> dict:
    """
    Hover the mouse over a DOM element.

    Args:
        selector: CSS selector of the element to hover
    """
    return await bc.hover_element(selector)


@mcp.tool()
async def press_key(key: str, selector: str | None = None) -> dict:
    """
    Press a keyboard key, optionally targeting a specific element.

    Args:
        key: Key to press, e.g. "Enter", "Escape", "Tab", "ArrowDown", "Control+a"
        selector: Optional CSS selector to focus before pressing
    """
    return await bc.press_key(key, selector)


@mcp.tool()
async def switch_tab(index: int) -> dict:
    """
    Switch the active browser tab by 0-based index.

    Args:
        index: Tab index (0 = first tab)
    """
    return await bc.switch_tab(index)


@mcp.tool()
async def close_tab(index: int | None = None) -> dict:
    """
    Close a browser tab.

    Args:
        index: Tab index to close. If None, closes the active tab.
    """
    return await bc.close_tab(index)


@mcp.tool()
async def list_tabs() -> dict:
    """
    List all currently open browser tabs with their index, URL, and title.
    """
    return await bc.list_tabs()


@mcp.tool()
async def current_url() -> dict:
    """Return the URL of the current browser tab."""
    return await bc.current_url()


@mcp.tool()
async def page_title() -> dict:
    """Return the title of the current browser tab."""
    return await bc.page_title()


@mcp.tool()
async def extract_text(selector: str | None = None, save: bool = True) -> dict:
    """
    Extract visible text from the page or a specific element.

    Args:
        selector: Optional CSS/XPath selector. If None, extracts full page text.
        save: Whether to save the extracted text to local memory (default True)
    """
    return await bc.extract_text(selector, save)


@mcp.tool()
async def inspect_element(selector: str) -> dict:
    """
    Inspect a DOM element — returns tag, text, attributes, and bounding box.

    Args:
        selector: CSS selector of the element to inspect
    """
    return await bc.inspect_element(selector)


@mcp.tool()
async def take_screenshot(
    filename: str | None = None,
    full_page: bool = False,
    description: str = "",
) -> dict:
    """
    Capture a screenshot of the current page.

    Args:
        filename: Optional filename (auto-generated if not provided)
        full_page: Whether to capture the full scrollable page (default False)
        description: Optional description saved to memory
    """
    return await bc.take_screenshot(filename, full_page, description)


@mcp.tool()
async def new_tab(url: str | None = None) -> dict:
    """
    Open a new browser tab, optionally navigating to a URL.

    Args:
        url: Optional URL to load in the new tab
    """
    return await bc.new_tab(url)


@mcp.tool()
async def evaluate_js(script: str) -> dict:
    """
    Execute JavaScript code in the browser page context and return the result.

    Args:
        script: JavaScript code to evaluate (e.g., "document.title")
    """
    return await bc.evaluate_js(script)


# ═══════════════════════════════════════════════════════════════════════════════
# INSTAGRAM TOOLS
# ═══════════════════════════════════════════════════════════════════════════════


@mcp.tool()
async def open_instagram() -> dict:
    """
    Navigate to the Instagram homepage.
    Ensures the browser is open and ready.
    """
    return await ig.open_instagram()


@mcp.tool()
async def login_instagram() -> dict:
    """
    Direct the user to complete the manual login process.
    Opens the headful browser window to the Instagram login screen.
    Requires no passwords or stored credentials in local env files.
    """
    return await ig.login_instagram()


@mcp.tool()
async def check_login_status() -> dict:
    """
    Check if the user has successfully authenticated in the browser window,
    and save the session snapshot to disk.
    """
    return await session_manager.check_login_status()


@mcp.tool()
async def clear_saved_session() -> dict:
    """
    Completely clear saved login sessions, cookies, and profiles on this machine.
    Forces a fresh login on the next run.
    """
    return await session_manager.clear_saved_session()


@mcp.tool()
async def export_session_backup() -> dict:
    """
    Export a backup snapshot of the current authenticated browser state.
    """
    return await session_manager.export_session_backup()


@mcp.tool()
async def list_accounts() -> dict:
    """
    List all saved Instagram account profiles on this machine.
    """
    return await session_manager.list_accounts()


@mcp.tool()
async def switch_account(username: str) -> dict:
    """
    Switch the active session/profile to the specified username.

    Args:
        username: Instagram username of the account to switch to.
    """
    return await session_manager.switch_account(username)


@mcp.tool()
async def logout_current_account() -> dict:
    """
    Logout the current active account and open a fresh headful browser login page
    to authenticate a new profile.
    """
    return await session_manager.logout_current_account()


@mcp.tool()
async def remove_account(username: str) -> dict:
    """
    Delete a saved account profile, cookies, and session state from this machine.

    Args:
        username: Instagram username of the account to delete.
    """
    return await session_manager.remove_account(username)


@mcp.tool()
async def rename_account_alias(username: str, alias: str) -> dict:
    """
    Assign a custom alias display name to a saved account profile.

    Args:
        username: Instagram username of the account to rename.
        alias: The new alias label.
    """
    return await session_manager.rename_account_alias(username, alias)


@mcp.tool()
async def current_account() -> dict:
    """
    Get details of the currently active authenticated Instagram account.
    """
    return await session_manager.current_account()


@mcp.tool()
async def save_session() -> dict:
    """
    Manually save the current browser session (cookies + storage state) to disk.
    The session will be reused on the next server start.
    """
    return await ig.save_session()


@mcp.tool()
async def load_session() -> dict:
    """
    Check if a saved session exists and report its status.
    The session is loaded automatically on browser launch.
    """
    return await ig.load_session()


@mcp.tool()
async def read_feed(scroll_count: int = 3) -> dict:
    """
    Read the Instagram home feed.

    Scrolls the page to load posts and extracts usernames, captions, and post URLs.
    Results are saved to local SQLite memory.

    Args:
        scroll_count: Number of times to scroll down to load more posts (default 3)
    """
    return await ig.read_feed(scroll_count)


@mcp.tool()
async def open_reel(url: str) -> dict:
    """
    Open a specific Instagram Reel.

    Args:
        url: Full Reel URL or just the Reel ID
    """
    return await ig.open_reel(url)


@mcp.tool()
async def read_comments(post_url: str | None = None, max_comments: int = 20) -> dict:
    """
    Read comments from an Instagram post.

    Args:
        post_url: URL of the post (optional — uses current page if not provided)
        max_comments: Maximum number of comments to retrieve (default 20)
    """
    return await ig.read_comments(post_url, max_comments)


@mcp.tool()
async def like_post(post_url: str | None = None) -> dict:
    """
    Like an Instagram post.

    ⚠️ Use responsibly. Excessive liking may trigger Instagram rate limits.

    Args:
        post_url: URL of the post to like (optional — uses current page if not provided)
    """
    return await ig.like_post(post_url)


@mcp.tool()
async def post_comment(comment_text: str, post_url: str | None = None) -> dict:
    """
    Post a comment on an Instagram post.

    ⚠️ Use responsibly. Instagram may restrict accounts that spam comments.

    Args:
        comment_text: The comment to post
        post_url: URL of the post (optional — uses current page if not provided)
    """
    return await ig.post_comment(comment_text, post_url)


@mcp.tool()
async def monitor_notifications() -> dict:
    """
    Open Instagram notifications and return recent activity as structured data.
    """
    return await ig.monitor_notifications()


@mcp.tool()
async def analyze_profile(username: str) -> dict:
    """
    Navigate to an Instagram profile and extract structured information.

    Returns: full name, bio, followers, following, post count, privacy status, recent posts.
    Saves the profile to local SQLite memory for future reference.

    Args:
        username: Instagram username (with or without @)
    """
    return await ig.analyze_profile(username)


@mcp.tool()
async def summarize_visible_content() -> dict:
    """
    Extract and summarize all visible text on the current browser page.

    Also takes a screenshot and saves everything to local memory.
    """
    return await ig.summarize_visible_content()


# ═══════════════════════════════════════════════════════════════════════════════
# MEMORY TOOLS
# ═══════════════════════════════════════════════════════════════════════════════


@mcp.tool()
async def memory_stats() -> dict:
    """Return row counts for all local SQLite memory tables."""
    return await memory.get_stats()


@mcp.tool()
async def list_screenshots(limit: int = 20) -> dict:
    """
    List saved screenshots from local memory.

    Args:
        limit: Maximum number of screenshots to return (default 20)
    """
    items = await memory.list_screenshots(limit)
    return {"status": "ok", "screenshots": items, "count": len(items)}


@mcp.tool()
async def list_visited_profiles(limit: int = 50) -> dict:
    """List previously analyzed Instagram profiles stored in local memory."""
    profiles = await memory.list_profiles(limit)
    return {"status": "ok", "profiles": profiles, "count": len(profiles)}


@mcp.tool()
async def save_note(title: str, content: str, tags: str = "") -> dict:
    """
    Save a text note to local memory.

    Args:
        title: Note title
        content: Note content
        tags: Comma-separated tags (optional)
    """
    note_id = await memory.save_note(title, content, tags)
    return {"status": "ok", "id": note_id, "title": title}


@mcp.tool()
async def list_notes(limit: int = 50) -> dict:
    """List all saved notes from local memory."""
    notes = await memory.list_notes(limit)
    return {"status": "ok", "notes": notes, "count": len(notes)}


@mcp.tool()
async def search_memory(query: str) -> dict:
    """
    Search extracted text in local memory.

    Args:
        query: Search term to look for in saved text extractions
    """
    results = await memory.search_extracted_text(query)
    return {"status": "ok", "results": results, "count": len(results)}


@mcp.tool()
async def session_history(limit: int = 50) -> dict:
    """Return the session event log from local memory."""
    history = await memory.get_session_history(limit)
    return {"status": "ok", "history": history, "count": len(history)}


# ═══════════════════════════════════════════════════════════════════════════════
# SERVER STARTUP
# ═══════════════════════════════════════════════════════════════════════════════


def _print_banner() -> None:
    """Print a startup banner to the terminal."""
    warnings = Config.validate()

    # Determine session status
    session_file = Config.session_file
    if session_file.exists():
        try:
            import json
            with open(session_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            is_valid = isinstance(data, dict) and "cookies" in data
            session_status = "Valid" if is_valid else "Invalid (Corrupted)"
        except Exception:
            session_status = "Invalid (Read Error)"
    else:
        session_status = "No Session (Needs Login)"

    # Determine transport
    import sys
    transport = "stdio"
    if "--transport" in sys.argv:
        idx = sys.argv.index("--transport")
        if idx + 1 < len(sys.argv):
            transport = sys.argv[idx + 1]

    # Active browser path
    browser_path = Config.get_browser_executable() or "Not Found (Playwright default)"

    table = Table(box=box.ROUNDED, show_header=False, padding=(0, 1))
    table.add_column("Key", style="bold cyan")
    table.add_column("Value", style="white")
    
    table.add_row("Active Account", Config.get_active_username() or "None (Anonymous)")
    table.add_row("Session Status", session_status)
    table.add_row("Browser Type", Config.browser_type)
    table.add_row("Active Browser Path", browser_path)
    table.add_row("Headless Mode", str(Config.headless))
    table.add_row("MCP Transport Mode", transport)
    table.add_row("Log Level", Config.log_level)
    table.add_row("Memory DB Path", str(Config.db_path))

    console.print(
        Panel.fit(
            table,
            title="[bold magenta]🤖 Instagram MCP Server[/bold magenta]",
            subtitle="[dim]Local-only · No cloud · Credentials-free[/dim]",
            border_style="magenta",
        )
    )

    if warnings:
        console.print("\n[bold yellow]⚠️  Configuration Warnings:[/bold yellow]")
        for w in warnings:
            console.print(f"  [yellow]•[/yellow] {w}")
        console.print()

    console.print("[bold green]✓ MCP server starting…[/bold green]\n")


def main() -> None:
    _print_banner()

    # Determine transport
    transport = "stdio"
    if "--transport" in sys.argv:
        idx = sys.argv.index("--transport")
        if idx + 1 < len(sys.argv):
            transport = sys.argv[idx + 1]

    # Startup and shutdown are handled inside _lifespan(), which FastMCP
    # runs within its own event loop.
    mcp.run(transport=transport)


if __name__ == "__main__":
    main()

