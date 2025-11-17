import os
from typing import Any, Dict, Optional

import aiohttp
import discord
from discord.ext import commands
from discord.ext.commands import Context


class EventTicketing(commands.Cog, name="events"):
    """Ticket queue management for Discord events."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.api_key = os.getenv("EDMTRAIN_API_KEY")

    async def cog_unload(self) -> None:
        # Placeholder for future cleanup (e.g. persistent sessions)
        return

    @commands.hybrid_group(
        name="event",
        description="Manage ticketed events.",
        invoke_without_command=True,
    )
    @commands.guild_only()
    async def event_group(self, context: Context) -> None:
        await self._send_event_list(context)

    @event_group.command(name="create", description="Create a manual event.")
    @commands.guild_only()
    async def event_create(
        self,
        context: Context,
        name: str,
        date: Optional[str] = None,
        venue: Optional[str] = None,
        city: Optional[str] = None,
        url: Optional[str] = None,
    ) -> None:
        event_id = await self.bot.database.create_event(
            guild_id=context.guild.id,
            name=name,
            created_by=context.author.id,
            source="manual",
            date=date,
            venue=venue,
            city=city,
            url=url,
        )
        await context.send(
            f"Created event **{discord.utils.escape_markdown(name)}** with ID `{event_id}`."
        )

    @event_group.command(name="import", description="Import an EDMTrain event by ID.")
    @commands.guild_only()
    async def event_import(self, context: Context, edmtrain_id: int) -> None:
        if context.interaction and not context.interaction.response.is_done():
            await context.interaction.response.defer()

        if not self.api_key:
            kwargs = {"ephemeral": True} if context.interaction else {}
            await context.send(
                "The EDMTrain API key is not configured. Set `EDMTRAIN_API_KEY` in the environment.",
                **kwargs,
            )
            return

        event_data = await self._fetch_edmtrain_event(edmtrain_id)
        if event_data is None:
            kwargs = {"ephemeral": True} if context.interaction else {}
            await context.send(
                "I couldn't find that event on EDMTrain. Double-check the event ID and try again.",
                **kwargs,
            )
            return

        existing = await self.bot.database.get_event_by_source(
            context.guild.id, "edmtrain", str(edmtrain_id)
        )
        if existing:
            kwargs = {"ephemeral": True} if context.interaction else {}
            await context.send(
                f"That EDMTrain event already exists here as `{existing['id']}`.",
                **kwargs,
            )
            return

        event_id = await self.bot.database.create_event(
            guild_id=context.guild.id,
            name=event_data["name"],
            created_by=context.author.id,
            source="edmtrain",
            source_id=str(edmtrain_id),
            date=event_data.get("date"),
            venue=event_data.get("venue"),
            city=event_data.get("city"),
            url=event_data.get("url"),
        )
        await context.send(
            f"Imported EDMTrain event **{discord.utils.escape_markdown(event_data['name'])}** as `{event_id}`."
        )

    @commands.hybrid_command(
        name="queue_join", description="Join the buying queue for an event."
    )
    @commands.guild_only()
    async def queue_join(self, context: Context, event_id: int) -> None:
        event = await self._get_event(context, event_id)
        if event is None:
            return

        added, position = await self.bot.database.add_buyer_to_queue(
            event_id, context.author.id
        )
        if added:
            await context.send(
                f"You joined the queue for **{discord.utils.escape_markdown(event['name'])}** at position `{position}`."
            )
        else:
            kwargs = {"ephemeral": True} if context.interaction else {}
            await context.send(
                f"You're already in the queue for **{discord.utils.escape_markdown(event['name'])}** at position `{position}`.",
                **kwargs,
            )

    @commands.hybrid_command(
        name="queue_leave", description="Leave the buying queue for an event."
    )
    @commands.guild_only()
    async def queue_leave(self, context: Context, event_id: int) -> None:
        event = await self._get_event(context, event_id)
        if event is None:
            return

        await self.bot.database.remove_buyer_from_queue(event_id, context.author.id)
        await context.send(
            f"Removed you from the queue for **{discord.utils.escape_markdown(event['name'])}**."
        )

    @commands.hybrid_command(
        name="queue_view", description="View the queue for an event."
    )
    @commands.guild_only()
    async def queue_view(self, context: Context, event_id: int) -> None:
        event = await self._get_event(context, event_id)
        if event is None:
            return

        queue_entries = await self.bot.database.list_queue(event_id)
        if not queue_entries:
            await context.send(
                f"No one is waiting to buy a ticket for **{discord.utils.escape_markdown(event['name'])}** yet."
            )
            return

        lines = []
        for position, entry in enumerate(queue_entries, start=1):
            user_id = int(entry["user_id"])
            member = context.guild.get_member(user_id)
            display = member.mention if member else f"<@{user_id}>"
            lines.append(f"`{position}.` {display}")

        message = "\n".join(lines[:15])
        if len(lines) > 15:
            message += f"\n…and {len(lines) - 15} more"

        await context.send(
            f"Buyers queued for **{discord.utils.escape_markdown(event['name'])}**:\n{message}"
        )

    @commands.hybrid_command(
        name="ticket_sell",
        description="List a ticket for sale and notify the next buyer in line.",
    )
    @commands.guild_only()
    async def ticket_sell(self, context: Context, event_id: int, price: float) -> None:
        event = await self._get_event(context, event_id)
        if event is None:
            return

        if price <= 0:
            kwargs = {"ephemeral": True} if context.interaction else {}
            await context.send("Please provide a price greater than zero.", **kwargs)
            return

        await self.bot.database.add_ticket_listing(event_id, context.author.id, price)
        await context.send(
            f"Ticket listed for **{discord.utils.escape_markdown(event['name'])}** at ${price:,.2f}."
        )

        await self._notify_next_buyer(context, event, price)

    async def _get_event(
        self, context: Context, event_id: int
    ) -> Optional[Dict[str, Any]]:
        event = await self.bot.database.get_event(context.guild.id, event_id)
        if event is None:
            kwargs = {"ephemeral": True} if context.interaction else {}
            await context.send(
                "I couldn't find an event with that ID in this server.", **kwargs
            )
        return event

    async def _send_event_list(self, context: Context) -> None:
        events = await self.bot.database.list_events_with_stats(context.guild.id)
        if not events:
            await context.send(
                "There are no events yet. Use `/event create` or `/event import` to add one."
            )
            return

        embed = discord.Embed(
            title="Ticketed events",
            colour=discord.Colour.blurple(),
        )
        for event in events:
            lines = []
            if event.get("date"):
                lines.append(f"Date: {event['date']}")
            if event.get("venue"):
                venue_line = event["venue"]
                if event.get("city"):
                    venue_line += f" — {event['city']}"
                lines.append(venue_line)
            if event.get("url"):
                lines.append(f"[Event link]({event['url']})")
            lines.append(f"Queue length: {event['queue_size']}")
            embed.add_field(
                name=f"`{event['id']}` — {event['name']}",
                value="\n".join(lines) or "No details provided.",
                inline=False,
            )

        await context.send(embed=embed)

    async def _fetch_edmtrain_event(self, edmtrain_id: int) -> Optional[Dict[str, Any]]:
        params = {"eventId": edmtrain_id, "client": self.api_key}
        url = "https://edmtrain.com/api/events"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=15) as response:
                    if response.status != 200:
                        return None
                    payload = await response.json()
        except aiohttp.ClientError:
            return None

        events = payload.get("events") or payload.get("data")
        if not events:
            return None

        event_info = events[0]
        venue_info = event_info.get("venue") or {}
        location_info = venue_info.get("location") or {}

        def _first_non_empty(*keys: str) -> Optional[str]:
            for key in keys:
                value = event_info.get(key)
                if value:
                    return value
            return None

        def _resolve_url() -> Optional[str]:
            for key in ("link", "ticketLink", "url"):
                value = event_info.get(key)
                if value:
                    return value
            return None

        return {
            "name": event_info.get("name") or _first_non_empty("title", "eventName") or f"EDMTrain {edmtrain_id}",
            "date": _first_non_empty("date", "startDate", "start_date", "day") or event_info.get("dateFormatted"),
            "venue": venue_info.get("name"),
            "city": location_info.get("city"),
            "url": _resolve_url(),
        }

    async def _notify_next_buyer(
        self, context: Context, event: Dict[str, Any], price: float
    ) -> None:
        next_buyer = await self.bot.database.get_next_buyer(event["id"])
        if not next_buyer:
            kwargs = {"ephemeral": True} if context.interaction else {}
            await context.send(
                "No buyers are currently queued for this event. The listing has been recorded.",
                **kwargs,
            )
            return

        user_id = int(next_buyer["user_id"])
        if user_id == context.author.id:
            # Skip notifying the seller if they happen to be in the queue.
            kwargs = {"ephemeral": True} if context.interaction else {}
            await context.send(
                "You are first in the queue—no other buyers to notify yet.",
                **kwargs,
            )
            return

        member = context.guild.get_member(user_id)
        user: Optional[discord.abc.User] = member or self.bot.get_user(user_id)
        if user is None:
            try:
                user = await self.bot.fetch_user(user_id)
            except discord.NotFound:
                user = None

        notification = (
            f"A ticket for **{event['name']}** is now available from {context.author.mention} "
            f"for ${price:,.2f}. Reply to them to coordinate the purchase."
        )

        if user:
            try:
                await user.send(notification)
            except discord.Forbidden:
                pass

        mention = member.mention if member else f"<@{user_id}>"
        await context.send(
            f"{mention}, {context.author.mention} is selling a ticket for **{event['name']}** at ${price:,.2f}."
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(EventTicketing(bot))
