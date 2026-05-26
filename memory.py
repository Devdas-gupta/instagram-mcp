"""
memory.py — SQLite-backed local memory for Instagram MCP Server.

Stores: screenshots, extracted text, session history, analysis history,
visited profiles, and free-form notes.  All I/O is async (aiosqlite).
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiosqlite

from config import Config
from logger import get_logger

log = get_logger(__name__)

# ─── Schema ───────────────────────────────────────────────────────────────────
_SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS screenshots (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    filename    TEXT    NOT NULL,
    url         TEXT,
    title       TEXT,
    description TEXT,
    created_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE TABLE IF NOT EXISTS extracted_text (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    url         TEXT    NOT NULL,
    title       TEXT,
    content     TEXT    NOT NULL,
    selector    TEXT,
    created_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE TABLE IF NOT EXISTS session_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    event       TEXT    NOT NULL,
    username    TEXT,
    details     TEXT,
    success     INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE TABLE IF NOT EXISTS analysis_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    url         TEXT,
    analysis    TEXT    NOT NULL,
    source      TEXT,
    created_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE TABLE IF NOT EXISTS visited_profiles (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    username        TEXT    NOT NULL UNIQUE,
    full_name       TEXT,
    followers       INTEGER,
    following       INTEGER,
    post_count      INTEGER,
    bio             TEXT,
    is_private      INTEGER DEFAULT 0,
    last_visited_at TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    notes           TEXT
);

CREATE TABLE IF NOT EXISTS notes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT    NOT NULL,
    content     TEXT    NOT NULL,
    tags        TEXT,
    created_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE TABLE IF NOT EXISTS feed_items (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id       TEXT,
    username      TEXT,
    post_type     TEXT,
    caption       TEXT,
    likes         INTEGER,
    comments      INTEGER,
    url           TEXT,
    captured_at   TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
"""


class Memory:
    """Async SQLite memory store."""

    def __init__(self, db_path: Path | None = None) -> None:
        self._db_path = db_path or Config.db_path
        self._conn: aiosqlite.Connection | None = None
        self._lock: asyncio.Lock | None = None  # created lazily inside a running loop

    @property
    def _get_lock(self) -> asyncio.Lock:
        """Return the asyncio.Lock, creating it lazily on first access.

        Deferred creation avoids the Python 3.10+ DeprecationWarning (and
        Python 3.14 RuntimeError) that occurs when asyncio primitives are
        instantiated outside a running event loop.
        """
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    # ── Lifecycle ─────────────────────────────────────────────────────────

    async def connect(self) -> None:
        """Open (and initialise) the database."""
        if self._conn is not None:
            return
        self._conn = await aiosqlite.connect(self._db_path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.executescript(_SCHEMA)
        await self._conn.commit()
        log.info(f"Memory DB connected: [bold]{self._db_path}[/bold]")

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()
            self._conn = None
        # Reset lock so a future connect() on a new event loop gets a fresh one
        self._lock = None

    async def __aenter__(self) -> "Memory":
        await self.connect()
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.close()

    def _check(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("Memory.connect() has not been called.")
        return self._conn

    # ── Screenshots ───────────────────────────────────────────────────────

    async def save_screenshot(
        self,
        filename: str,
        url: str = "",
        title: str = "",
        description: str = "",
    ) -> int:
        async with self._get_lock:
            db = self._check()
            cur = await db.execute(
                "INSERT INTO screenshots (filename, url, title, description) VALUES (?,?,?,?)",
                (filename, url, title, description),
            )
            await db.commit()
            return cur.lastrowid  # type: ignore[return-value]

    async def list_screenshots(self, limit: int = 20) -> list[dict]:
        db = self._check()
        cur = await db.execute(
            "SELECT * FROM screenshots ORDER BY created_at DESC LIMIT ?", (limit,)
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]

    # ── Extracted text ────────────────────────────────────────────────────

    async def save_extracted_text(
        self, url: str, content: str, title: str = "", selector: str = ""
    ) -> int:
        async with self._get_lock:
            db = self._check()
            cur = await db.execute(
                "INSERT INTO extracted_text (url, title, content, selector) VALUES (?,?,?,?)",
                (url, title, content, selector),
            )
            await db.commit()
            return cur.lastrowid  # type: ignore[return-value]

    async def search_extracted_text(self, query: str, limit: int = 10) -> list[dict]:
        db = self._check()
        cur = await db.execute(
            "SELECT * FROM extracted_text WHERE content LIKE ? ORDER BY created_at DESC LIMIT ?",
            (f"%{query}%", limit),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]

    # ── Session history ────────────────────────────────────────────────────

    async def log_session_event(
        self,
        event: str,
        username: str = "",
        details: str = "",
        success: bool = True,
    ) -> None:
        async with self._get_lock:
            db = self._check()
            await db.execute(
                "INSERT INTO session_history (event, username, details, success) VALUES (?,?,?,?)",
                (event, username, details, int(success)),
            )
            await db.commit()

    async def get_session_history(self, limit: int = 50) -> list[dict]:
        db = self._check()
        cur = await db.execute(
            "SELECT * FROM session_history ORDER BY created_at DESC LIMIT ?", (limit,)
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]

    # ── Analysis history ───────────────────────────────────────────────────

    async def save_analysis(self, analysis: str, url: str = "", source: str = "") -> int:
        async with self._get_lock:
            db = self._check()
            cur = await db.execute(
                "INSERT INTO analysis_history (url, analysis, source) VALUES (?,?,?)",
                (url, analysis, source),
            )
            await db.commit()
            return cur.lastrowid  # type: ignore[return-value]

    async def get_analysis_history(self, limit: int = 20) -> list[dict]:
        db = self._check()
        cur = await db.execute(
            "SELECT * FROM analysis_history ORDER BY created_at DESC LIMIT ?", (limit,)
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]

    # ── Visited profiles ───────────────────────────────────────────────────

    async def upsert_profile(
        self,
        username: str,
        full_name: str = "",
        followers: int | None = None,
        following: int | None = None,
        post_count: int | None = None,
        bio: str = "",
        is_private: bool = False,
        notes: str = "",
    ) -> None:
        async with self._get_lock:
            db = self._check()
            await db.execute(
                """
                INSERT INTO visited_profiles
                    (username, full_name, followers, following, post_count, bio, is_private, notes,
                     last_visited_at)
                VALUES (?,?,?,?,?,?,?,?, strftime('%Y-%m-%dT%H:%M:%SZ','now'))
                ON CONFLICT(username) DO UPDATE SET
                    full_name       = excluded.full_name,
                    followers       = excluded.followers,
                    following       = excluded.following,
                    post_count      = excluded.post_count,
                    bio             = excluded.bio,
                    is_private      = excluded.is_private,
                    notes           = excluded.notes,
                    last_visited_at = strftime('%Y-%m-%dT%H:%M:%SZ','now')
                """,
                (username, full_name, followers, following, post_count, bio, int(is_private), notes),
            )
            await db.commit()

    async def get_profile(self, username: str) -> dict | None:
        db = self._check()
        cur = await db.execute(
            "SELECT * FROM visited_profiles WHERE username = ?", (username,)
        )
        row = await cur.fetchone()
        return dict(row) if row else None

    async def list_profiles(self, limit: int = 50) -> list[dict]:
        db = self._check()
        cur = await db.execute(
            "SELECT * FROM visited_profiles ORDER BY last_visited_at DESC LIMIT ?", (limit,)
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]

    # ── Notes ─────────────────────────────────────────────────────────────

    async def save_note(self, title: str, content: str, tags: str = "") -> int:
        async with self._get_lock:
            db = self._check()
            cur = await db.execute(
                "INSERT INTO notes (title, content, tags) VALUES (?,?,?)",
                (title, content, tags),
            )
            await db.commit()
            return cur.lastrowid  # type: ignore[return-value]

    async def list_notes(self, limit: int = 50) -> list[dict]:
        db = self._check()
        cur = await db.execute(
            "SELECT * FROM notes ORDER BY updated_at DESC LIMIT ?", (limit,)
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]

    # ── Feed items ─────────────────────────────────────────────────────────

    async def save_feed_item(
        self,
        username: str = "",
        post_id: str = "",
        post_type: str = "post",
        caption: str = "",
        likes: int | None = None,
        comments: int | None = None,
        url: str = "",
    ) -> int:
        async with self._get_lock:
            db = self._check()
            cur = await db.execute(
                """INSERT INTO feed_items
                   (post_id, username, post_type, caption, likes, comments, url)
                   VALUES (?,?,?,?,?,?,?)""",
                (post_id, username, post_type, caption, likes, comments, url),
            )
            await db.commit()
            return cur.lastrowid  # type: ignore[return-value]

    async def get_feed_items(self, limit: int = 50) -> list[dict]:
        db = self._check()
        cur = await db.execute(
            "SELECT * FROM feed_items ORDER BY captured_at DESC LIMIT ?", (limit,)
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]

    # ── Generic query ──────────────────────────────────────────────────────

    async def execute_query(self, sql: str, params: tuple = ()) -> list[dict]:
        """Run an arbitrary read-only SELECT and return results as dicts."""
        db = self._check()
        cur = await db.execute(sql, params)
        rows = await cur.fetchall()
        return [dict(r) for r in rows]

    async def get_stats(self) -> dict:
        """Return row counts for all tables."""
        tables = [
            "screenshots", "extracted_text", "session_history",
            "analysis_history", "visited_profiles", "notes", "feed_items",
        ]
        stats: dict[str, int] = {}
        db = self._check()
        for table in tables:
            cur = await db.execute(f"SELECT COUNT(*) FROM {table}")
            row = await cur.fetchone()
            stats[table] = row[0] if row else 0
        return stats


# ─── Module-level singleton ───────────────────────────────────────────────────
memory = Memory()
