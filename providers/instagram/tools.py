"""
providers/instagram/tools.py — Instagram automation tools.

Implements all high-level tools for Instagram browser automation.
Extends BaseProvider and utilizes providers/instagram/selectors.py.
"""

from __future__ import annotations

import asyncio
import re
import sys
from pathlib import Path
from typing import Any

from playwright.async_api import Page, TimeoutError as PWTimeout

# Ensure parent root is in sys.path
sys.path.append(str(Path(__file__).parent.parent.parent.resolve()))

from core.base_provider import BaseProvider
from core.browser_engine import (
    click_element,
    extract_text,
    open_url,
    scroll_page,
    take_screenshot,
    type_text,
)
from config import Config
from logger import get_logger
from memory import memory
from session_manager import session_manager
import providers.instagram.selectors as sel

log = get_logger(__name__)

INSTAGRAM_BASE = "https://www.instagram.com"


async def _page() -> Page:
    _, p = await session_manager.get_context_and_page()
    return p


def parse_stat_number(s: str) -> int:
    """Parse numeric strings like '12.4K' or '1,200' to integers."""
    s = s.strip().upper().replace(",", "")
    if not s:
        return 0
    try:
        if "M" in s:
            return int(float(s.replace("M", "")) * 1_000_000)
        if "K" in s:
            return int(float(s.replace("K", "")) * 1_000)
        digits = "".join(c for c in s if c.isdigit() or c == ".")
        return int(float(digits)) if "." in digits else int(digits)
    except Exception:
        return 0


class InstagramProvider(BaseProvider):
    """Instagram MCP service provider."""

    async def initialize(self) -> None:
        log.info("Instagram platform provider initialized.")

    async def validate_session(self) -> bool:
        page = await _page()
        return await session_manager.is_logged_in(page)


# ─── Tool Implementations ───────────────────────────────────────────────────


async def open_instagram() -> dict:
    """Navigate to Instagram homepage."""
    result = await open_url(INSTAGRAM_BASE)
    await asyncio.sleep(1.5)
    return {**result, "tool": "open_instagram"}


async def login_instagram() -> dict:
    """
    Manual-only verification flow.
    Instructs the AI to prompt the user to complete login in the opened browser window.
    """
    page = await _page()
    already = await session_manager.is_logged_in(page)
    if already:
        return {
            "status": "ok",
            "message": "Already logged in to Instagram.",
        }
    
    # We are already directed to the login page headful inside _launch_browser
    return {
        "status": "needs_login",
        "message": (
            "Authentication required. A headful browser window has been opened at the Instagram login page. "
            "Please enter your credentials manually in that window. Once you have logged in, "
            "tell me 'I am logged in' or 'done' so I can verify and save your session state."
        )
    }


async def save_session() -> dict:
    """Manually save the current browser session state to disk."""
    ctx, _ = await session_manager.get_context_and_page()
    ok = await session_manager.save_session(ctx)
    return {
        "status": "ok" if ok else "error",
        "path": str(Config.session_file),
        "message": "Session saved successfully." if ok else "Failed to save session state.",
    }


async def load_session() -> dict:
    """Load session state status."""
    exists = await session_manager.load_session()
    return {
        "status": "ok" if exists else "not_found",
        "path": str(Config.session_file),
        "message": "Session state snapshot file exists." if exists else "No saved session found.",
    }


async def read_feed(scroll_count: int = 3) -> dict:
    """
    Read the home feed.
    """
    page = await _page()

    # Navigate to home if not there
    if page.url.rstrip("/") != INSTAGRAM_BASE.rstrip("/"):
        await open_url(INSTAGRAM_BASE)

    await asyncio.sleep(2)
    posts: list[dict] = []

    for scroll_n in range(scroll_count + 1):
        try:
            articles = await page.query_selector_all(sel.FEED_ARTICLE)
            for article in articles:
                try:
                    # Username
                    user_link = await article.query_selector(sel.FEED_HEADER_USER)
                    username = await user_link.inner_text() if user_link else ""

                    # Caption
                    caption = ""
                    for c_sel in sel.FEED_CAPTIONS:
                        caption_el = await article.query_selector(c_sel)
                        if caption_el:
                            caption = await caption_el.inner_text()
                            break
                    if not caption:
                        caption = await article.inner_text()
                        caption = caption[:300]

                    # Likes
                    likes_text = ""
                    for l_sel in sel.FEED_LIKES:
                        likes_el = await article.query_selector(l_sel)
                        if likes_el:
                            likes_text = await likes_el.inner_text()
                            break

                    # Link to post
                    post_link_el = await article.query_selector(sel.FEED_POST_URL)
                    post_url = ""
                    if post_link_el:
                        href = await post_link_el.get_attribute("href")
                        post_url = f"{INSTAGRAM_BASE}{href}" if href else ""

                    post_data = {
                        "username": username.strip(),
                        "caption": caption.strip()[:500],
                        "likes": likes_text.strip(),
                        "url": post_url,
                    }
                    if post_url and not any(p["url"] == post_url for p in posts):
                        posts.append(post_data)
                        await memory.save_feed_item(
                            username=post_data["username"],
                            caption=post_data["caption"],
                            url=post_data["url"],
                        )
                except Exception:
                    continue

        except Exception as exc:
            log.debug(f"Feed extraction issue: {exc}")

        if scroll_n < scroll_count:
            await scroll_page("down", 800)
            await asyncio.sleep(1.5)

    return {
        "status": "ok",
        "posts_found": len(posts),
        "posts": posts[:20],
        "scrolled": scroll_count,
    }


async def open_reel(url: str) -> dict:
    """Open a specific Reel URL."""
    if not url.startswith("http"):
        url = f"{INSTAGRAM_BASE}/reel/{url}/"
    result = await open_url(url)
    await asyncio.sleep(1.5)
    page = await _page()
    title = await page.title()
    return {**result, "tool": "open_reel", "title": title}


async def read_comments(post_url: str | None = None, max_comments: int = 20) -> dict:
    """
    Read comments from a post, handling dynamic inner scroll containers.
    """
    page = await _page()

    if post_url:
        await open_url(post_url)
        await asyncio.sleep(2)

    comments: list[dict] = []

    try:
        # Click view comments trigger
        try:
            await page.click(sel.EXPAND_COMMENTS_TEXT, timeout=3000)
            await asyncio.sleep(1)
        except Exception:
            pass

        # Harvest comments loop
        for _ in range(3):
            comment_els = await page.query_selector_all(sel.COMMENT_TEXT)
            for el in comment_els:
                try:
                    text = await el.inner_text()
                    if text.strip() and len(text.strip()) > 2:
                        parent = await el.evaluate_handle("el => el.closest('li')")
                        try:
                            author_el = await parent.query_selector("a")
                            author = await author_el.inner_text() if author_el else ""
                        except Exception:
                            author = ""

                        c = {"author": author.strip(), "text": text.strip()[:200]}
                        if c not in comments:
                            comments.append(c)
                except Exception:
                    continue

            # Scroll the comment container dynamically using JS overflow evaluator
            await page.evaluate("""() => {
                const divs = Array.from(document.querySelectorAll('div'));
                const scrollable = divs.find(el => {
                    const style = window.getComputedStyle(el);
                    return (style.overflowY === 'auto' || style.overflowY === 'scroll') && el.scrollHeight > el.clientHeight;
                });
                if (scrollable) {
                    scrollable.scrollTop += 400;
                }
            }""")
            await asyncio.sleep(1)

            if len(comments) >= max_comments:
                break

    except Exception as exc:
        log.error(f"read_comments error: {exc}")
        return {"status": "error", "message": str(exc)}

    return {
        "status": "ok",
        "comments_found": len(comments),
        "comments": comments[:max_comments],
        "url": page.url,
    }


async def post_comment(comment_text: str, post_url: str | None = None) -> dict:
    """Post a comment on a post."""
    page = await _page()

    if post_url:
        await open_url(post_url)
        await asyncio.sleep(2.5)

    try:
        input_el = None
        for sel_input in sel.COMMENT_INPUTS:
            input_el = await page.query_selector(sel_input)
            if input_el:
                break

        if not input_el:
            return {"status": "error", "message": "Comment input element not found."}

        await input_el.click()
        await asyncio.sleep(0.5)
        await input_el.fill(comment_text)
        await asyncio.sleep(0.5)

        # Click submit button
        posted = False
        for btn_sel in sel.COMMENT_POST_BUTTONS:
            try:
                btn = await page.query_selector(btn_sel)
                if btn:
                    await btn.click()
                    posted = True
                    break
            except Exception:
                continue

        if not posted:
            return {"status": "error", "message": "Could not submit comment."}

        await asyncio.sleep(1.5)
        return {
            "status": "ok",
            "message": "Comment posted successfully.",
            "comment": comment_text,
            "url": page.url,
        }
    except Exception as exc:
        log.error(f"post_comment error: {exc}")
        return {"status": "error", "message": str(exc)}


async def like_post(post_url: str | None = None) -> dict:
    """Like a post."""
    page = await _page()

    if post_url:
        await open_url(post_url)
        await asyncio.sleep(1.5)

    try:
        liked = False
        for like_sel in sel.LIKE_BUTTONS:
            try:
                el = await page.query_selector(like_sel)
                if el:
                    # Check if already liked
                    svg_label = await el.evaluate("el => el.getAttribute('aria-label')")
                    if svg_label and svg_label.lower() == "unlike":
                        log.info("Post is already liked.")
                        return {"status": "ok", "message": "Post is already liked.", "url": page.url}
                        
                    await el.click()
                    liked = True
                    break
            except Exception:
                continue

        await asyncio.sleep(1)
        if liked:
            return {"status": "ok", "message": "Post liked successfully.", "url": page.url}
        return {"status": "error", "message": "Like button not found."}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


async def monitor_notifications() -> dict:
    """Check recent notifications."""
    page = await _page()

    try:
        triggered = False
        for notif_sel in sel.NOTIF_TRIGGER:
            try:
                el = await page.query_selector(notif_sel)
                if el:
                    await el.click()
                    await asyncio.sleep(2)
                    triggered = True
                    break
            except Exception:
                continue

        if not triggered:
            # Fallback to direct navigation if click fails
            await open_url(f"{INSTAGRAM_BASE}/accounts/activity/")
            await asyncio.sleep(2)

        # Retrieve text extractions safely
        result = await extract_text(selector=None, save=False)
        text = result.get("text", "")

        notif_items = []
        notif_els = await page.query_selector_all(sel.NOTIF_CONTAINER_ITEMS)
        for el in notif_els[:20]:
            try:
                t = await el.inner_text()
                if t.strip():
                    notif_items.append(t.strip()[:200])
            except Exception:
                continue

        return {
            "status": "ok",
            "notifications": notif_items if notif_items else [text[:1000]],
            "count": len(notif_items),
        }
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


async def analyze_profile(username: str) -> dict:
    """
    Analyze profile metadata and persist statistics correctly inside memory.
    """
    clean_username = username.lstrip("@")
    profile_url = f"{INSTAGRAM_BASE}/{clean_username}/"
    await open_url(profile_url)
    await asyncio.sleep(2.5)

    page = await _page()
    data: dict[str, Any] = {"username": clean_username, "url": profile_url}

    try:
        # Full name
        name_el = await page.query_selector(sel.PROFILE_NAME)
        if name_el:
            data["full_name"] = (await name_el.inner_text()).strip()

        # Bio
        for bio_sel in sel.PROFILE_BIO:
            bio_el = await page.query_selector(bio_sel)
            if bio_el:
                data["bio"] = (await bio_el.inner_text()).strip()[:500]
                break

        # Stats parsing
        stat_els = await page.query_selector_all(sel.PROFILE_STATS)
        stats = []
        for el in stat_els:
            text = (await el.inner_text()).strip()
            stats.append(text)
        data["stats_raw"] = stats

        followers_str = "0"
        following_str = "0"
        posts_str = "0"
        
        for s in stats:
            lower = s.lower()
            num_match = re.search(r"[\d,\.]+[KMkm]?", s)
            num_str = num_match.group() if num_match else "0"
            if "follower" in lower or "seguidores" in lower:
                followers_str = num_str
            elif "following" in lower or "seguidos" in lower:
                following_str = num_str
            elif "post" in lower or "publica" in lower:
                posts_str = num_str

        data["followers"] = followers_str
        data["following"] = following_str
        data["post_count"] = posts_str

        # Private check
        lock = await page.query_selector(sel.PROFILE_PRIVATE)
        data["is_private"] = bool(lock)

        # Recent posts links
        post_links = await page.query_selector_all(sel.PROFILE_RECENT_POSTS)
        recent_urls = []
        for el in post_links[:9]:
            href = await el.get_attribute("href")
            if href:
                recent_urls.append(f"{INSTAGRAM_BASE}{href}")
        data["recent_post_urls"] = recent_urls

        # Database Upsert with fully parsed integer metrics
        await memory.upsert_profile(
            username=clean_username,
            full_name=data.get("full_name", ""),
            followers=parse_stat_number(followers_str),
            following=parse_stat_number(following_str),
            post_count=parse_stat_number(posts_str),
            bio=data.get("bio", ""),
            is_private=data.get("is_private", False),
        )

    except Exception as exc:
        log.error(f"analyze_profile error: {exc}")
        data["error"] = str(exc)

    return {"status": "ok", "profile": data}


async def summarize_visible_content() -> dict:
    """Summarize page content and attach inline visual screenshot metadata."""
    page = await _page()
    url = page.url
    title = await page.title()

    result = await extract_text(save=True)
    raw_text = result.get("text", "")

    # Take screenshot for context
    screenshot = await take_screenshot(description=f"Summary contextual capture: {title}")

    await memory.save_analysis(
        analysis=raw_text[:3000],
        url=url,
        source="summarize_visible_content",
    )

    return {
        "status": "ok",
        "url": url,
        "title": title,
        "content_length": len(raw_text),
        "summary": raw_text[:2000],
        "screenshot": screenshot.get("filename", ""),
    }
