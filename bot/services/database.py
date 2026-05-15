import aiosqlite
import json
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "chat_history.db")


def _ensure_data_dir():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)


async def get_db() -> aiosqlite.Connection:
    _ensure_data_dir()
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("""
        CREATE TABLE IF NOT EXISTS chat_history (
            chat_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    await db.execute("""
        CREATE INDEX IF NOT EXISTS idx_chat_history_chat_id
        ON chat_history(chat_id)
    """)
    await db.commit()
    return db


class ChatHistoryDB:
    def __init__(self, max_messages: int = 12):
        self.max_messages = max_messages

    async def get_history(self, chat_id: str) -> list[dict]:
        db = await get_db()
        try:
            cursor = await db.execute(
                "SELECT role, content FROM chat_history WHERE chat_id = ? "
                "ORDER BY created_at DESC LIMIT ?",
                (chat_id, self.max_messages),
            )
            rows = await cursor.fetchall()
            return [{"role": row[0], "content": row[1]} for row in reversed(rows)]
        finally:
            await db.close()

    async def append(self, chat_id: str, role: str, content: str):
        db = await get_db()
        try:
            await db.execute(
                "INSERT INTO chat_history (chat_id, role, content) VALUES (?, ?, ?)",
                (chat_id, role, content),
            )
            await db.execute(
                "DELETE FROM chat_history WHERE chat_id = ? AND rowid NOT IN "
                "(SELECT rowid FROM chat_history WHERE chat_id = ? "
                "ORDER BY created_at DESC LIMIT ?)",
                (chat_id, chat_id, self.max_messages),
            )
            await db.commit()
        finally:
            await db.close()
