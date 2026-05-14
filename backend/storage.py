import json
from datetime import date, datetime
from typing import Any

import aiosqlite

from backend.config import DB_PATH

CREATE_ITEMS = """
CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    title TEXT NOT NULL,
    detail TEXT,
    time TEXT,
    url TEXT,
    priority TEXT DEFAULT 'normal',
    fetched_at TEXT NOT NULL
)
"""

CREATE_LOG = """
CREATE TABLE IF NOT EXISTS fetcher_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    status TEXT NOT NULL,
    message TEXT,
    fetched_at TEXT NOT NULL
)
"""


async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(CREATE_ITEMS)
        await db.execute(CREATE_LOG)
        await db.commit()


async def save_items(source: str, items: list[dict[str, Any]]) -> None:
    now = datetime.utcnow().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM items WHERE source = ?", (source,))
        for item in items:
            await db.execute(
                "INSERT INTO items (source, title, detail, time, url, priority, fetched_at) VALUES (?,?,?,?,?,?,?)",
                (
                    source,
                    item.get("title", ""),
                    item.get("detail"),
                    item.get("time"),
                    item.get("url"),
                    item.get("priority", "normal"),
                    now,
                ),
            )
        await db.commit()


async def log_fetch(source: str, status: str, message: str = "") -> None:
    now = datetime.utcnow().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO fetcher_log (source, status, message, fetched_at) VALUES (?,?,?,?)",
            (source, status, message, now),
        )
        await db.commit()


async def get_items(for_date: date | None = None) -> list[dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if for_date:
            prefix = for_date.isoformat()
            cursor = await db.execute(
                "SELECT * FROM items WHERE time LIKE ? OR time IS NULL ORDER BY time ASC",
                (f"{prefix}%",),
            )
        else:
            cursor = await db.execute("SELECT * FROM items ORDER BY source, time ASC")
        rows = await cursor.fetchall()
    return [dict(r) for r in rows]
