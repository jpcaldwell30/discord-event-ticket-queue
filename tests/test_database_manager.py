import asyncio
from pathlib import Path
import sys

import aiosqlite

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT))

from database import DatabaseManager


async def create_manager() -> DatabaseManager:
    schema_path = PROJECT_ROOT / "database" / "schema.sql"
    connection = await aiosqlite.connect(":memory:")
    connection.row_factory = aiosqlite.Row
    with open(schema_path, "r", encoding="utf-8") as schema_file:
        await connection.executescript(schema_file.read())
    manager = DatabaseManager(connection=connection)
    await manager.enable_foreign_keys()
    return manager


def test_create_event_and_list():
    async def runner():
        manager = await create_manager()
        try:
            event_id = await manager.create_event(
                guild_id=123,
                name="Test Event",
                created_by=111,
                source="manual",
                date="2024-01-01",
                venue="Test Venue",
                city="Test City",
                url="https://example.com",
            )

            events = await manager.list_events_with_stats(123)
            assert len(events) == 1
            event = events[0]
            assert event["id"] == event_id
            assert event["name"] == "Test Event"
            assert event["queue_size"] == 0
        finally:
            await manager.close()

    asyncio.run(runner())


def test_queue_operations():
    async def runner():
        manager = await create_manager()
        try:
            event_id = await manager.create_event(
                guild_id=999,
                name="Queue Event",
                created_by=222,
                source="manual",
            )

            added_first, position_first = await manager.add_buyer_to_queue(event_id, 1)
            assert added_first is True
            assert position_first == 1

            added_second, position_second = await manager.add_buyer_to_queue(event_id, 2)
            assert added_second is True
            assert position_second == 2

            added_duplicate, position_duplicate = await manager.add_buyer_to_queue(
                event_id, 1
            )
            assert added_duplicate is False
            assert position_duplicate == 1

            queue = await manager.list_queue(event_id)
            assert [entry["user_id"] for entry in queue] == ["1", "2"]

            next_buyer = await manager.get_next_buyer(event_id)
            assert next_buyer is not None
            assert next_buyer["user_id"] == "1"

            await manager.remove_buyer_from_queue(event_id, 1)
            next_buyer_after_removal = await manager.get_next_buyer(event_id)
            assert next_buyer_after_removal is not None
            assert next_buyer_after_removal["user_id"] == "2"
        finally:
            await manager.close()

    asyncio.run(runner())


def test_ticket_listing():
    async def runner():
        manager = await create_manager()
        try:
            event_id = await manager.create_event(
                guild_id=55,
                name="Ticket Event",
                created_by=333,
                source="manual",
            )

            listing_id = await manager.add_ticket_listing(event_id, 555, 42.5)
            assert isinstance(listing_id, int)

            listings = await manager.list_tickets(event_id)
            assert len(listings) == 1
            listing = listings[0]
            assert listing["seller_id"] == "555"
            assert listing["price"] == 42.5
        finally:
            await manager.close()

    asyncio.run(runner())
