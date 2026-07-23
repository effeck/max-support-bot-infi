"""SQLite database layer for the support bot."""

import aiosqlite
from typing import Any, Optional


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id     INTEGER PRIMARY KEY,
    username    TEXT,
    full_name   TEXT,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tickets (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL,
    kind            TEXT NOT NULL,
    content_type    TEXT NOT NULL,
    text            TEXT,
    file_id         TEXT,
    status          TEXT NOT NULL DEFAULT 'open',
    admin_comment   TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status);
CREATE INDEX IF NOT EXISTS idx_tickets_user   ON tickets(user_id);
"""


class Database:
    def __init__(self, path: str) -> None:
        self.path = path

    async def init(self) -> None:
        async with aiosqlite.connect(self.path) as conn:
            await conn.executescript(SCHEMA)
            await conn.commit()

    async def close(self) -> None:
        return None

    async def upsert_user(self, user_id, username, full_name):
        async with aiosqlite.connect(self.path) as conn:
            await conn.execute(
                """INSERT INTO users (user_id, username, full_name) VALUES (?, ?, ?)
                   ON CONFLICT(user_id) DO UPDATE SET username=excluded.username, full_name=excluded.full_name""",
                (user_id, username, full_name),
            )
            await conn.commit()

    async def get_user(self, user_id):
        async with aiosqlite.connect(self.path) as conn:
            conn.row_factory = aiosqlite.Row
            cur = await conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            row = await cur.fetchone()
            return dict(row) if row else None

    async def create_ticket(self, user_id, kind, content_type, text, file_id):
        async with aiosqlite.connect(self.path) as conn:
            cur = await conn.execute(
                "INSERT INTO tickets (user_id, kind, content_type, text, file_id) VALUES (?, ?, ?, ?, ?)",
                (user_id, kind, content_type, text, file_id),
            )
            await conn.commit()
            return cur.lastrowid

    async def get_ticket(self, ticket_id):
        async with aiosqlite.connect(self.path) as conn:
            conn.row_factory = aiosqlite.Row
            cur = await conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
            row = await cur.fetchone()
            return dict(row) if row else None

    async def list_tickets(self, only_open=True, limit=20):
        async with aiosqlite.connect(self.path) as conn:
            conn.row_factory = aiosqlite.Row
            if only_open:
                cur = await conn.execute("SELECT * FROM tickets WHERE status = 'open' ORDER BY created_at DESC LIMIT ?", (limit,))
            else:
                cur = await conn.execute("SELECT * FROM tickets ORDER BY created_at DESC LIMIT ?", (limit,))
            return [dict(r) for r in await cur.fetchall()]

    async def set_status(self, ticket_id, status, reason=None):
        async with aiosqlite.connect(self.path) as conn:
            await conn.execute(
                "UPDATE tickets SET status = ?, admin_comment = COALESCE(?, admin_comment), updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (status, reason, ticket_id),
            )
            await conn.commit()

    async def stats(self):
        async with aiosqlite.connect(self.path) as conn:
            cur = await conn.execute("SELECT status, COUNT(*) as c FROM tickets GROUP BY status")
            rows = await cur.fetchall()
            out = {"total": 0, "open": 0, "accepted": 0, "rejected": 0, "commented": 0}
            for status, count in rows:
                out["total"] += count
                out[status] = out.get(status, 0) + count
            return out
