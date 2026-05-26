"""
session_manager.py — Manages Playwright browser sessions for Instagram MCP.

Responsibilities:
  • Save / load Playwright storage state (cookies + localStorage) per account
  • Dynamic session versioning & backup recovery
  • Dynamic headful override for manual auth
  • Non-blocking verification API (check_login_status) & Profile scraper
  • True multi-account switching capabilities
  • Browser crash auto-recovery
"""

from __future__ import annotations

import asyncio
import json
import time
import os
import shutil
from pathlib import Path
from datetime import datetime, timezone
from typing import Any

from playwright.async_api import (
    BrowserContext,
    Page,
    async_playwright,
)

from config import Config
from logger import get_logger
from memory import memory

log = get_logger(__name__)

INSTAGRAM_BASE_URL = "https://www.instagram.com"
INSTAGRAM_LOGIN_URL = "https://www.instagram.com/accounts/login/"


def check_session_corruption() -> bool:
    """Check if the current active session JSON file exists and contains valid JSON."""
    session_file = Config.session_file
    if not session_file.exists():
        return False
    try:
        with open(session_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        return isinstance(data, dict) and "cookies" in data
    except Exception:
        return False


async def restore_from_backup() -> bool:
    """Attempt to restore the active session file from a backup snapshot."""
    active_dir = Config.get_active_account_dir()
    if not active_dir:
        return False
        
    backup = active_dir / "storage_state.json.bak"
    session_file = Config.session_file
    
    if backup.exists():
        try:
            with open(backup, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and "cookies" in data:
                active_dir.mkdir(parents=True, exist_ok=True)
                with open(session_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
                log.info(f"Successfully restored session from backup snapshot for {active_dir.name}.")
                return True
        except Exception as exc:
            log.warning(f"Failed to restore from backup: {exc}")
    return False


class SessionManager:
    """
    Manages browser session lifecycle for Instagram.
    """

    def __init__(self) -> None:
        self._playwright = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._account_lock = None
        self._lifecycle_lock = None
        self._pages: list[Page] = []
        
        # Cache active username in memory on startup
        Config._active_username_cached = Config.get_active_username()

    @property
    def account_lock(self) -> asyncio.Lock:
        if self._account_lock is None:
            self._account_lock = asyncio.Lock()
        return self._account_lock

    @property
    def lifecycle_lock(self) -> asyncio.Lock:
        if self._lifecycle_lock is None:
            self._lifecycle_lock = asyncio.Lock()
        return self._lifecycle_lock

    async def register_page(self, page: Page) -> None:
        """Track opened tabs and auto-close the oldest inactive ones to prevent memory leaks."""
        self._pages = [p for p in self._pages if not p.is_closed()]
        if page not in self._pages:
            self._pages.append(page)
            
        # Clean up if exceeding threshold (max 5 open pages)
        if len(self._pages) > 5:
            # Find the oldest that is not current active page
            for i, p in enumerate(self._pages):
                if p != self._page and not p.is_closed():
                    try:
                        await p.close()
                        log.info(f"Closed idle tab to conserve memory: {p.url}")
                    except Exception:
                        pass
                    self._pages.pop(i)
                    break

    async def get_context_and_page(self, force_headful: bool = False) -> tuple[BrowserContext, Page]:
        """
        Return (context, page). Creates or recovers browser context dynamically.
        """
        # Crash Auto-Recovery
        if self._context and self._page:
            try:
                # Test if the page is still responsive
                _ = self._page.url
                if not self._page.is_closed():
                    return self._context, self._page
            except Exception:
                log.warning("Stale page or closed context detected. Restoring browser engine...")
                await self.close()

        await self._launch_browser(force_headful=force_headful)
        context = self._context
        page = self._page

        if context is None or page is None:
            raise RuntimeError("Browser engine failed to start.")

        return context, page

    async def save_session(self, context: BrowserContext | None = None) -> bool:
        """Persist Playwright storage state to disk + backup for current account."""
        ctx = context or self._context
        if ctx is None:
            log.warning("No context to save.")
            return False
        try:
            active_dir = Config.get_active_account_dir()
            if not active_dir:
                log.warning("Cannot save session: no active account selected.")
                return False
                
            active_dir.mkdir(parents=True, exist_ok=True)
            session_file = Config.session_file
            
            # Fetch storage state dict natively
            state = await ctx.storage_state()
            
            # Save primary state
            with open(session_file, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)
                
            # Save backup snapshot
            backup_path = active_dir / "storage_state.json.bak"
            with open(backup_path, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)
                
            log.info(f"Session saved successfully → {session_file}")
            await memory.log_session_event(
                "save_session",
                details=str(session_file),
                success=True,
            )
            return True
        except Exception as exc:
            log.error(f"Failed to save session: {exc}")
            await memory.log_session_event("save_session", details=str(exc), success=False)
            return False

    async def load_session(self) -> bool:
        """
        Check if a saved session exists (or recovers from backup).
        """
        session_file = Config.session_file
        if not session_file.exists():
            restored = await restore_from_backup()
            if not restored:
                return False
        return check_session_corruption()

    async def is_logged_in(self, page: Page) -> bool:
        """Check whether the browser session is authenticated (non-blocking checks)."""
        try:
            current = page.url
            if "accounts/login" in current or "challenge" in current:
                return False
            
            # Check for home icon SVG or main layout items
            element = await page.query_selector("svg[aria-label='Home']")
            if element:
                return True
                
            nav = await page.query_selector("nav")
            if nav:
                return True
                
            # If not login screen, assume authenticated
            return "accounts/login" not in page.url
        except Exception as exc:
            log.debug(f"is_logged_in check failed: {exc}")
            return False

    async def extract_profile_info(self, page: Page) -> tuple[str | None, str | None]:
        """Scrape username and display name from the page context."""
        try:
            js_code = r"""
            (() => {
                // Try sidebar nav profile link
                const links = Array.from(document.querySelectorAll('a[href^="/"]'));
                const excluded = ['/', '/explore', '/explore/', '/direct', '/direct/', '/reels', '/reels/', '/emails', '/emails/', '/developer', '/about', '/legal', '/terms', '/privacy', '/directory', '/press', '/api', '/jobs', '/help', '/security', '/blog', '/suggested', '/accounts'];
                
                let foundUsername = null;
                for (const link of links) {
                    const href = link.getAttribute('href');
                    if (!href) continue;
                    const clean = href.split('?')[0].split('#')[0].replace(/\/+$/, '');
                    if (clean && !excluded.some(ex => clean === ex || clean.replace(/^\/+/, '') === ex.replace(/^\/+/, '') || clean.startsWith(ex + '/'))) {
                        const parts = clean.split('/').filter(Boolean);
                        if (parts.length === 1) {
                            const possibleUser = parts[0];
                            if (/^[a-zA-Z0-9._]{1,30}$/.test(possibleUser)) {
                                foundUsername = possibleUser;
                                break;
                            }
                        }
                    }
                }
                
                // Try profile picture alt text fallback
                if (!foundUsername) {
                    const img = document.querySelector('img[alt*="profile picture" i]');
                    if (img) {
                        const alt = img.getAttribute('alt');
                        const match = alt.match(/(.+?)'s profile picture/i);
                        if (match && match[1]) {
                            foundUsername = match[1];
                        }
                    }
                }
                
                return {
                    username: foundUsername,
                    displayName: foundUsername
                };
            })()
            """
            info = await page.evaluate(js_code)
            return info.get("username"), info.get("displayName")
        except Exception as exc:
            log.warning(f"Failed to extract profile info: {exc}")
            return None, None

    async def check_login_status(self) -> dict:
        """MCP Tool utility to verify and save manual login status."""
        if not self._page:
            return {"status": "error", "message": "Browser is not open. Open browser first."}
        
        logged_in = await self.is_logged_in(self._page)
        if logged_in:
            # Scrape profile info (username)
            username, display_name = await self.extract_profile_info(self._page)
            if not username:
                await asyncio.sleep(2.0)
                username, display_name = await self.extract_profile_info(self._page)
                
            if not username or not Config.validate_username(username):
                return {
                    "status": "error",
                    "message": "Login confirmed, but failed to auto-detect a valid/secure username."
                }
                
            async with self.account_lock:
                # Write active account config
                Config._active_username_cached = username
                active_file = Config.sessions_dir / "active_account.json"
                with open(active_file, "w", encoding="utf-8") as f:
                    json.dump({"active_username": username}, f, indent=2)
                    
                # Create account directory
                account_dir = Config.sessions_dir / username
                account_dir.mkdir(parents=True, exist_ok=True)
                (account_dir / "screenshots").mkdir(exist_ok=True)
                
                # Save metadata.json
                metadata_file = account_dir / "metadata.json"
                now_iso = datetime.now(timezone.utc).isoformat()
                metadata = {
                    "username": username,
                    "display_name": display_name or username,
                    "alias": "",
                    "last_login": now_iso,
                    "session_created": now_iso,
                    "last_used": now_iso,
                    "version": "1.0"
                }
                if metadata_file.exists():
                    try:
                        with open(metadata_file, "r", encoding="utf-8") as f:
                            old_meta = json.load(f)
                        metadata["session_created"] = old_meta.get("session_created", now_iso)
                        metadata["alias"] = old_meta.get("alias", "")
                    except Exception:
                        pass
                        
                with open(metadata_file, "w", encoding="utf-8") as f:
                    json.dump(metadata, f, indent=2)
                    
                # Save Playwright storage state directly into the new folder
                ok = await self.save_session(self._context)
                if ok:
                    legacy_file = Config.sessions_dir / "instagram_session.json"
                    if legacy_file.exists():
                        try:
                            legacy_file.unlink()
                        except Exception:
                            pass
                    return {
                        "status": "ok",
                        "logged_in": True,
                        "username": username,
                        "message": f"Login confirmed for account '{username}'! Session successfully saved."
                    }
                else:
                    return {
                        "status": "error",
                        "message": "Logged in, but failed to write session files."
                    }
        else:
            return {
                "status": "needs_login",
                "logged_in": False,
                "current_url": self._page.url,
                "message": "Manual login not detected. Please complete the authentication form in the browser window."
            }

    # ── Multi-Account Operations ───────────────────────────────────────────

    async def list_accounts(self) -> dict:
        """Scan data/sessions/ and compile a list of all saved profiles."""
        accounts = []
        if not Config.sessions_dir.exists():
            return {"status": "ok", "accounts": [], "count": 0}
        
        for p in Config.sessions_dir.iterdir():
            if p.is_dir() and (p / "metadata.json").exists():
                try:
                    with open(p / "metadata.json", "r", encoding="utf-8") as f:
                        meta = json.load(f)
                    accounts.append(meta)
                except Exception:
                    pass
        
        active = Config.get_active_username()
        return {
            "status": "ok",
            "active_account": active,
            "accounts": accounts,
            "count": len(accounts)
        }

    async def switch_account(self, username: str) -> dict:
        """Switch the active session to the target username."""
        target = username.strip().lstrip("@")
        if not Config.validate_username(target):
            return {"status": "error", "message": "Invalid username format."}
            
        async with self.account_lock:
            target_dir = Config.sessions_dir / target
            if not target_dir.exists() or not (target_dir / "metadata.json").exists():
                return {"status": "error", "message": f"Account '{target}' not found. Please log in first."}
            
            # Close active browser
            await self.close()
            
            # Update memory cache and active account tracker
            Config._active_username_cached = target
            active_file = Config.sessions_dir / "active_account.json"
            with open(active_file, "w", encoding="utf-8") as f:
                json.dump({"active_username": target}, f, indent=2)
                
            # Update last_used in metadata
            metadata_file = target_dir / "metadata.json"
            try:
                with open(metadata_file, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                meta["last_used"] = datetime.now(timezone.utc).isoformat()
                with open(metadata_file, "w", encoding="utf-8") as f:
                    json.dump(meta, f, indent=2)
            except Exception:
                pass
                
            log.info(f"Switched active account to: {target}")
            
            # Spin up browser with the new session
            await self.get_context_and_page()
            return {
                "status": "ok",
                "active_account": target,
                "message": f"Successfully switched to account '{target}'."
            }

    async def logout_current_account(self) -> dict:
        """Logout the current active account and open the clean login page."""
        async with self.account_lock:
            await self.close()
            
            # Clear memory cache and active tracker
            Config._active_username_cached = None
            active_file = Config.sessions_dir / "active_account.json"
            if active_file.exists():
                try:
                    active_file.unlink()
                except Exception:
                    pass
                    
            # Force a headful launch to the login page (anonymous mode)
            await self.get_context_and_page(force_headful=True)
            return {
                "status": "ok",
                "message": "Logged out of current account. A fresh headful browser has been opened for a new login."
            }

    async def remove_account(self, username: str) -> dict:
        """Delete an account directory completely."""
        target = username.strip().lstrip("@")
        if not Config.validate_username(target):
            return {"status": "error", "message": "Invalid username format."}
            
        async with self.account_lock:
            target_dir = Config.sessions_dir / target
            if not target_dir.exists():
                return {"status": "error", "message": f"Account '{target}' does not exist."}
            
            # If active, close it first and clear tracker
            active = Config.get_active_username()
            if active == target:
                await self.close()
                Config._active_username_cached = None
                active_file = Config.sessions_dir / "active_account.json"
                if active_file.exists():
                    try:
                        active_file.unlink()
                    except Exception:
                        pass
                        
            # Delete directory recursively
            try:
                shutil.rmtree(target_dir, ignore_errors=True)
            except Exception as exc:
                return {"status": "error", "message": f"Failed to delete account directory: {exc}"}
                
            return {
                "status": "ok",
                "message": f"Account profile '{target}' was successfully removed from this machine."
            }

    async def rename_account_alias(self, username: str, alias: str) -> dict:
        """Save a custom display alias for an account profile."""
        target = username.strip().lstrip("@")
        if not Config.validate_username(target):
            return {"status": "error", "message": "Invalid username format."}
            
        async with self.account_lock:
            target_dir = Config.sessions_dir / target
            metadata_file = target_dir / "metadata.json"
            if not metadata_file.exists():
                return {"status": "error", "message": f"Account '{target}' not found."}
                
            try:
                with open(metadata_file, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                meta["alias"] = alias
                with open(metadata_file, "w", encoding="utf-8") as f:
                    json.dump(meta, f, indent=2)
                return {
                    "status": "ok",
                    "username": target,
                    "alias": alias,
                    "message": f"Successfully renamed '{target}' alias to '{alias}'."
                }
            except Exception as exc:
                return {"status": "error", "message": f"Failed to update alias: {exc}"}

    async def current_account(self) -> dict:
        """Return details about the currently active account."""
        active = Config.get_active_username()
        if not active:
            return {"status": "ok", "active_account": None, "message": "No account is currently active (anonymous)."}
            
        metadata_file = Config.sessions_dir / active / "metadata.json"
        if metadata_file.exists():
            try:
                with open(metadata_file, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                return {
                    "status": "ok",
                    "active_account": active,
                    "metadata": meta
                }
            except Exception:
                pass
                
        return {
            "status": "ok",
            "active_account": active,
            "message": f"Account '{active}' is active, but metadata file is missing."
        }

    async def clear_saved_session(self) -> dict:
        """Delete all saved sessions and profiles."""
        await self.close()
        
        # Clear active tracker
        active_file = Config.sessions_dir / "active_account.json"
        if active_file.exists():
            try:
                active_file.unlink()
            except Exception:
                pass
        
        deleted = []
        if Config.sessions_dir.exists():
            try:
                shutil.rmtree(Config.sessions_dir, ignore_errors=True)
                deleted.append("sessions_dir")
            except Exception as exc:
                log.warning(f"Could not delete sessions directory: {exc}")
                
        return {
            "status": "ok",
            "message": f"All account sessions cleared. Cleaned: {', '.join(deleted)}"
        }

    async def export_session_backup(self) -> dict:
        """Backup current session snapshot."""
        active_dir = Config.get_active_account_dir()
        if not active_dir or not Config.session_file.exists():
            return {"status": "error", "message": "No active session file found."}
        try:
            backup = active_dir / "storage_state.json.bak"
            shutil.copy2(Config.session_file, backup)
            return {
                "status": "ok",
                "backup_path": str(backup),
                "message": f"Session snapshot successfully backed up for {active_dir.name}."
            }
        except Exception as exc:
            return {"status": "error", "message": f"Failed to export backup: {exc}"}

    async def close(self) -> None:
        """Close browser and Playwright."""
        async with self.lifecycle_lock:
            if self._context:
                try:
                    await self._context.close()
                except Exception:
                    pass
            if self._playwright:
                try:
                    await self._playwright.stop()
                except Exception:
                    pass
            self._context = None
            self._page = None
            self._playwright = None
            self._pages = []
            log.info("Browser closed.")

    # ── Internals ──────────────────────────────────────────────────────────

    async def _launch_browser(self, force_headful: bool = False) -> None:
        """Launch Playwright Chromium using isolated profile directory."""
        async with self.lifecycle_lock:
            self._playwright = await async_playwright().start()
            pw = self._playwright

            executable = Config.get_browser_executable()
            
            # Check session snapshot existence
            session_exists = await self.load_session()
            
            # Run headful if no session exists or headful forced
            headless = False if not session_exists else (Config.headless if not force_headful else False)

            launch_kwargs: dict[str, Any] = {
                "headless": headless,
                "args": [
                    "--no-sandbox",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-infobars",
                    "--lang=en-US",  # Force English language UI
                ],
            }
            if executable:
                launch_kwargs["executable_path"] = executable
                log.info(f"Launching browser: {executable} (headless={headless})")
            else:
                log.info(f"Using bundled Playwright browser (headless={headless})")

            # Create isolated profile folder
            username = Config.get_active_username()
            if username:
                profile_dir = Config.sessions_dir / username / "playwright_profile"
            else:
                profile_dir = Config.sessions_dir / "anonymous_playwright_profile"

            profile_dir.mkdir(parents=True, exist_ok=True)
            
            # Remove stale lock files
            for lock_name in ["SingletonLock", "lock"]:
                lock_file = profile_dir / lock_name
                if lock_file.exists():
                    try:
                        if lock_file.is_symlink():
                            lock_file.unlink()
                        else:
                            lock_file.unlink()
                        log.info(f"Removed stale browser lock: {lock_file}")
                    except Exception as exc:
                        log.warning(f"Could not remove lock file {lock_file}: {exc}")

            profile_dir_str = str(profile_dir)
            
            # Restore session file if corrupted
            if not session_exists:
                await restore_from_backup()

            if Config.session_file.exists() and check_session_corruption():
                try:
                    context = await pw.chromium.launch_persistent_context(
                        user_data_dir=profile_dir_str,
                        storage_state=str(Config.session_file),
                        locale="en-US",
                        **launch_kwargs,
                    )
                    page = context.pages[0] if context.pages else await context.new_page()
                    await self._apply_stealth(page)

                    logged_in = await self.is_logged_in(page)
                    if logged_in:
                        log.info("Restored session successfully!")
                        self._context = context
                        self._page = page
                        await self.register_page(page)
                        return
                    else:
                        log.warning("Session credentials expired. Re-triggering headful login...")
                        await context.close()
                        await asyncio.sleep(1.5)
                except Exception as exc:
                    log.warning(f"Could not restore session: {exc}")

            # If not logged in, force headful mode and navigate to login
            launch_kwargs["headless"] = False
            log.info("Launching headful Chromium for manual authentication...")
            
            context = await pw.chromium.launch_persistent_context(
                user_data_dir=profile_dir_str,
                locale="en-US",
                **launch_kwargs,
            )
            page = context.pages[0] if context.pages else await context.new_page()
            await self._apply_stealth(page)

            self._context = context
            self._page = page
            await self.register_page(page)

            # Navigate user to login screen
            await page.goto(INSTAGRAM_LOGIN_URL, wait_until="domcontentloaded", timeout=60_000)
    @staticmethod
    async def _apply_stealth(page: Page) -> None:
        """Inject JS to hide automation signals."""
        await page.add_init_script(
            """
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.chrome = { runtime: {} };
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
            """
        )


# Module-level singleton
session_manager = SessionManager()
