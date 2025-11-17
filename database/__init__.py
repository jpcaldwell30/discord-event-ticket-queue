"""
Database helpers for the Discord event ticket queue bot.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import aiosqlite


class DatabaseManager:
    """Asynchronous helper around the SQLite connection."""

    def __init__(self, *, connection: aiosqlite.Connection) -> None:
        self.connection = connection
        self.connection.row_factory = aiosqlite.Row

    async def enable_foreign_keys(self) -> None:
        await self.connection.execute("PRAGMA foreign_keys = ON")
        await self.connection.commit()

    async def add_warn(
        self, user_id: int, server_id: int, moderator_id: int, reason: str
    ) -> int:
        """
        Add a warn to the database.

        :param user_id: The ID of the user that should be warned.
        :param server_id: The ID of the guild where the warn happened.
        :param moderator_id: The moderator issuing the warn.
        :param reason: The reason of the warn.
        """
        rows = await self.connection.execute(
            "SELECT id FROM warns WHERE user_id=? AND server_id=? ORDER BY id DESC LIMIT 1",
            (
                user_id,
                server_id,
            ),
        )
        async with rows as cursor:
            result = await cursor.fetchone()
            warn_id = result[0] + 1 if result is not None else 1
            await self.connection.execute(
                "INSERT INTO warns(id, user_id, server_id, moderator_id, reason) VALUES (?, ?, ?, ?, ?)",
                (
                    warn_id,
                    user_id,
                    server_id,
                    moderator_id,
                    reason,
                ),
            )
            await self.connection.commit()
            return warn_id

    async def remove_warn(self, warn_id: int, user_id: int, server_id: int) -> int:
        """
        Remove a warn from the database.
        """

        await self.connection.execute(
            "DELETE FROM warns WHERE id=? AND user_id=? AND server_id=?",
            (
                warn_id,
                user_id,
                server_id,
            ),
        )
        await self.connection.commit()
        rows = await self.connection.execute(
            "SELECT COUNT(*) FROM warns WHERE user_id=? AND server_id=?",
            (
                user_id,
                server_id,
            ),
        )
        async with rows as cursor:
            result = await cursor.fetchone()
            return result[0] if result is not None else 0

    async def get_warnings(self, user_id: int, server_id: int) -> List[aiosqlite.Row]:
        """Return all warnings for the given user in a guild."""

        rows = await self.connection.execute(
            "SELECT user_id, server_id, moderator_id, reason, strftime('%s', created_at), id FROM warns WHERE user_id=? AND server_id=?",
            (
                user_id,
                server_id,
            ),
        )
        async with rows as cursor:
            result = await cursor.fetchall()
            return list(result)

    async def create_event(
        self,
        *,
        guild_id: int,
        name: str,
        created_by: int,
        source: str,
        source_id: Optional[str] = None,
        date: Optional[str] = None,
        venue: Optional[str] = None,
        city: Optional[str] = None,
        url: Optional[str] = None,
    ) -> int:
        """Create a new event and return its identifier."""

        await self.connection.execute(
            """
            INSERT OR IGNORE INTO events
            (guild_id, name, created_by, source, source_id, date, venue, city, url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(guild_id),
                name,
                str(created_by),
                source,
                source_id,
                date,
                venue,
                city,
                url,
            ),
        )
        await self.connection.commit()
        cursor = await self.connection.execute(
            """
            SELECT id FROM events
            WHERE guild_id=? AND name=?
            ORDER BY id DESC LIMIT 1
            """,
            (
                str(guild_id),
                name,
            ),
        )
        async with cursor as rows:
            result = await rows.fetchone()
            return int(result[0])

    async def get_event(self, guild_id: int, event_id: int) -> Optional[Dict[str, Any]]:
        rows = await self.connection.execute(
            "SELECT * FROM events WHERE guild_id=? AND id=?",
            (
                str(guild_id),
                event_id,
            ),
        )
        async with rows as cursor:
            result = await cursor.fetchone()
            return dict(result) if result else None

    async def get_event_by_source(
        self, guild_id: int, source: str, source_id: str
    ) -> Optional[Dict[str, Any]]:
        rows = await self.connection.execute(
            "SELECT * FROM events WHERE guild_id=? AND source=? AND source_id=?",
            (
                str(guild_id),
                source,
                source_id,
            ),
        )
        async with rows as cursor:
            result = await cursor.fetchone()
            return dict(result) if result else None

    async def list_events_with_stats(self, guild_id: int) -> List[Dict[str, Any]]:
        rows = await self.connection.execute(
            """
            SELECT e.*, COUNT(q.id) as queue_size
            FROM events e
            LEFT JOIN buyer_queue q ON q.event_id = e.id
            WHERE e.guild_id=?
            GROUP BY e.id
            ORDER BY e.created_at ASC
            """,
            (str(guild_id),),
        )
        async with rows as cursor:
            result = await cursor.fetchall()
            return [dict(row) for row in result]

    async def add_buyer_to_queue(
        self, event_id: int, user_id: int
    ) -> Tuple[bool, int]:
        try:
            cursor = await self.connection.execute(
                "INSERT INTO buyer_queue(event_id, user_id) VALUES (?, ?)",
                (
                    event_id,
                    str(user_id),
                ),
            )
            await self.connection.commit()
            await cursor.close()
            position = await self._queue_position(event_id, str(user_id))
            return True, position
        except aiosqlite.IntegrityError:
            position = await self._queue_position(event_id, str(user_id))
            return False, position

    async def _queue_position(self, event_id: int, user_id: str) -> int:
        rows = await self.connection.execute(
            """
            SELECT COUNT(*) FROM buyer_queue
            WHERE event_id=? AND id <= (
                SELECT id FROM buyer_queue WHERE event_id=? AND user_id=?
            )
            """,
            (
                event_id,
                event_id,
                user_id,
            ),
        )
        async with rows as cursor:
            result = await cursor.fetchone()
            return int(result[0]) if result and result[0] is not None else 0

    async def remove_buyer_from_queue(self, event_id: int, user_id: int) -> None:
        await self.connection.execute(
            "DELETE FROM buyer_queue WHERE event_id=? AND user_id=?",
            (
                event_id,
                str(user_id),
            ),
        )
        await self.connection.commit()

    async def get_next_buyer(self, event_id: int) -> Optional[Dict[str, Any]]:
        rows = await self.connection.execute(
            "SELECT * FROM buyer_queue WHERE event_id=? ORDER BY id ASC LIMIT 1",
            (event_id,),
        )
        async with rows as cursor:
            result = await cursor.fetchone()
            return dict(result) if result else None

    async def list_queue(self, event_id: int) -> List[Dict[str, Any]]:
        rows = await self.connection.execute(
            "SELECT * FROM buyer_queue WHERE event_id=? ORDER BY id ASC",
            (event_id,),
        )
        async with rows as cursor:
            result = await cursor.fetchall()
            return [dict(row) for row in result]

    async def add_ticket_listing(
        self, event_id: int, seller_id: int, price: float
    ) -> int:
        cursor = await self.connection.execute(
            "INSERT INTO tickets(event_id, seller_id, price) VALUES (?, ?, ?)",
            (
                event_id,
                str(seller_id),
                float(price),
            ),
        )
        await self.connection.commit()
        return cursor.lastrowid

    async def list_tickets(self, event_id: int) -> List[Dict[str, Any]]:
        rows = await self.connection.execute(
            "SELECT * FROM tickets WHERE event_id=? ORDER BY created_at ASC",
            (event_id,),
        )
        async with rows as cursor:
            result = await cursor.fetchall()
            return [dict(row) for row in result]

    async def close(self) -> None:
        await self.connection.close()
