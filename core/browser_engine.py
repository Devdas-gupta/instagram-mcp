"""
core/browser_engine.py — Low-level Playwright browser engine.

Provides general browser primitives:
  open_browser, open_url, click_element, type_text, scroll_page,
  hover_element, press_key, switch_tab, close_tab, list_tabs,
  current_url, page_title, extract_text, inspect_element, take_screenshot.
"""

from __future__ import annotations

import asyncio
import base64
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from playwright.async_api import (
    BrowserContext,
    ElementHandle,
    Page,
    TimeoutError as PWTimeout,
)

# Ensure parent root is in sys.path
sys.path.append(str(Path(__file__).parent.parent.resolve()))

from config import Config
from logger import get_logger
from memory import memory
from session_manager import session_manager

log = get_logger(__name__)


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


async def _get_page() -> Page:
    """Gets the active page, triggering crash recovery if stale."""
    _, page = await session_manager.get_context_and_page()
    return page


async def _get_context() -> BrowserContext:
    """Gets the active context, triggering crash recovery if stale."""
    ctx, _ = await session_manager.get_context_and_page()
    return ctx


# ─── Browser Engine Functions ───────────────────────────────────────────


async def open_browser() -> dict:
    """Launch browser and verify state."""
    _, page = await session_manager.get_context_and_page()
    url = page.url
    return {"status": "ok", "current_url": url, "message": "Browser is open and ready."}


async def open_url(url: str) -> dict:
    """Navigate to a URL with dynamic load-state verification."""
    page = await _get_page()
    await page.goto(url, wait_until="domcontentloaded", timeout=Config.navigation_timeout)
    await page.wait_for_timeout(1000)
    return {"status": "ok", "url": page.url, "title": await page.title()}


async def click_element(selector: str, timeout_ms: int | None = None) -> dict:
    """Click an element. Uses Playwright auto-waiting (no blind retry)."""
    page = await _get_page()
    t = timeout_ms or Config.default_timeout
    await page.click(selector, timeout=t)
    return {"status": "ok", "selector": selector, "action": "clicked"}


async def type_text(selector: str, text: str, clear_first: bool = True) -> dict:
    """Type text safely, obfuscating passwords in output logs."""
    page = await _get_page()
    
    # Check if target is sensitive
    is_sensitive = any(w in selector.lower() for w in ["password", "pass", "secret", "key", "2fa", "code"])
    log_text = "********" if is_sensitive else text
    
    if clear_first:
        await page.fill(selector, "")
    await page.type(selector, text, delay=30)
    return {"status": "ok", "selector": selector, "typed": log_text}


async def scroll_page(direction: str = "down", amount: int = 500) -> dict:
    """Scroll the top-level viewport."""
    page = await _get_page()
    direction = direction.lower()

    scroll_map = {
        "down":  (0, amount),
        "up":    (0, -amount),
        "right": (amount, 0),
        "left":  (-amount, 0),
    }
    dx, dy = scroll_map.get(direction, (0, amount))
    await page.evaluate(f"window.scrollBy({dx}, {dy})")
    await page.wait_for_timeout(300)
    return {"status": "ok", "direction": direction, "amount": amount}


async def hover_element(selector: str) -> dict:
    """Hover over an element."""
    page = await _get_page()
    await page.hover(selector, timeout=Config.default_timeout)
    return {"status": "ok", "selector": selector, "action": "hovered"}


async def press_key(key: str, selector: str | None = None) -> dict:
    """Press a keyboard key."""
    page = await _get_page()
    if selector:
        await page.focus(selector)
    await page.keyboard.press(key)
    return {"status": "ok", "key": key}


async def switch_tab(index: int) -> dict:
    """Switch to a tab by index."""
    ctx = await _get_context()
    pages = ctx.pages
    if index < 0 or index >= len(pages):
        return {"status": "error", "message": f"Tab index {index} out of range (0–{len(pages)-1})"}
    page = pages[index]
    await page.bring_to_front()
    session_manager._page = page
    await session_manager.register_page(page)
    return {"status": "ok", "tab": index, "url": page.url, "title": await page.title()}


async def close_tab(index: int | None = None) -> dict:
    """Close the active tab (or tab at index)."""
    ctx = await _get_context()
    pages = ctx.pages
    if not pages:
        return {"status": "error", "message": "No open tabs."}
    if index is not None:
        if 0 <= index < len(pages):
            await pages[index].close()
            return {"status": "ok", "closed_tab": index}
        return {"status": "error", "message": f"Tab {index} not found."}
    page = await _get_page()
    await page.close()
    remaining = ctx.pages
    if remaining:
        session_manager._page = remaining[-1]
    return {"status": "ok", "message": "Active tab closed."}


async def list_tabs() -> dict:
    """List all open tabs."""
    ctx = await _get_context()
    tabs = []
    for i, p in enumerate(ctx.pages):
        try:
            title = await p.title()
        except Exception:
            title = ""
        tabs.append({"index": i, "url": p.url, "title": title})
    return {"status": "ok", "tabs": tabs, "count": len(tabs)}


async def current_url() -> dict:
    """Return the current page URL."""
    page = await _get_page()
    return {"status": "ok", "url": page.url}


async def page_title() -> dict:
    """Return the current page title."""
    page = await _get_page()
    title = await page.title()
    return {"status": "ok", "title": title}


async def extract_text(selector: str | None = None, save: bool = True) -> dict:
    """Extract page or element text."""
    page = await _get_page()
    try:
        if selector:
            element = await page.query_selector(selector)
            if not element:
                return {"status": "error", "message": f"Selector not found: {selector}"}
            text = await element.inner_text()
        else:
            text = await page.inner_text("body")

        text = text.strip()
        url = page.url
        title = await page.title()

        if save and text:
            await memory.save_extracted_text(url=url, content=text, title=title, selector=selector or "body")

        return {
            "status": "ok",
            "text": text[:5000],  # Truncate for prompt text content safety
            "length": len(text),
            "url": url,
            "selector": selector or "body",
        }
    except Exception as exc:
        log.error(f"extract_text error: {exc}")
        return {"status": "error", "message": str(exc)}


async def inspect_element(selector: str) -> dict:
    """Return attributes, text, and bounds of a selector."""
    page = await _get_page()
    try:
        element = await page.query_selector(selector)
        if not element:
            return {"status": "error", "message": f"Selector not found: {selector}"}

        tag = await element.evaluate("el => el.tagName.toLowerCase()")
        text = await element.inner_text()
        attrs = await element.evaluate(
            """el => {
                const result = {};
                for (const attr of el.attributes) {
                    result[attr.name] = attr.value;
                }
                return result;
            }"""
        )
        box = await element.bounding_box()

        return {
            "status": "ok",
            "tag": tag,
            "text": text[:500],
            "attributes": attrs,
            "bounding_box": box,
            "selector": selector,
        }
    except Exception as exc:
        log.error(f"inspect_element error: {exc}")
        return {"status": "error", "message": str(exc)}


async def take_screenshot(
    filename: str | None = None,
    full_page: bool = False,
    description: str = "",
) -> dict:
    """Capture page screenshot and save metadata."""
    page = await _get_page()
    ts = _ts()
    fname = filename or f"screenshot_{ts}.png"
    path = Config.get_active_screenshots_dir() / fname

    try:
        await page.screenshot(path=str(path), full_page=full_page)
        url = page.url
        title = await page.title()

        await memory.save_screenshot(filename=fname, url=url, title=title, description=description)
        log.info(f"Screenshot saved → {path}")
        
        # Read file for direct inline response
        raw = path.read_bytes()
        b64 = base64.b64encode(raw).decode()

        return {
            "status": "ok",
            "filename": fname,
            "path": str(path),
            "url": url,
            "title": title,
            "image_base64": b64,  # Returns full string so wrapper can build Image content block
        }
    except Exception as exc:
        log.error(f"Screenshot error: {exc}")
        return {"status": "error", "message": str(exc)}



async def new_tab(url: str | None = None) -> dict:
    """Open a new tab."""
    ctx = await _get_context()
    page = await ctx.new_page()
    await session_manager._apply_stealth(page)
    session_manager._page = page
    await session_manager.register_page(page)
    if url:
        await page.goto(url, wait_until="domcontentloaded", timeout=Config.navigation_timeout)
    return {"status": "ok", "url": page.url, "title": await page.title()}


async def evaluate_js(script: str) -> dict:
    """Execute javascript in browser context."""
    page = await _get_page()
    try:
        result = await page.evaluate(script)
        return {"status": "ok", "result": result}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}
