# Discord Event Ticket Queue Bot

A Discord bot that manages buyer queues and ticket listings for events. Guild members can create events manually or import them from the [EDMTrain](https://edmtrain.com/) API, queue for tickets, and notify the next buyer when someone lists a ticket for sale. The project builds on top of the Python Discord Bot Template and layers in database-backed ticket workflows that can run on Oracle Cloud or any environment that supports Python 3.12.

## Features

- **Event management** – create ad-hoc events from Discord or import them from EDMTrain using an API key.
- **Buyer queues** – let users join, leave, and view the queue for an event to signal interest in purchasing a ticket.
- **Seller listings** – allow sellers to post a ticket with an asking price and automatically notify the next buyer in line.
- **SQLite persistence** – events, queues, and listings are stored in an SQLite database with foreign-key enforcement.
- **Hybrid commands** – commands can be used as slash commands or traditional text commands.

## Prerequisites

- Python 3.12
- A Discord bot application and token ([create one here](https://discord.com/developers/applications))
- Optional: An EDMTrain API key for importing public event data

## Configuration

1. Copy `.env.example` to `.env` and populate the environment variables:
   - `DISCORD_TOKEN` – your bot token
   - `EDMTRAIN_API_KEY` – optional, required to import events from EDMTrain
2. Alternatively, define the same variables directly in your hosting environment (e.g., Oracle Cloud).

## Installation

Install the Python dependencies:

```bash
python -m pip install -r requirements.txt
```

## Running the bot

Start the bot locally with:

```bash
python bot.py
```

To run the bot in Docker:

```bash
docker compose up -d --build
```

The bot will automatically create the SQLite database (`data/database.db`) on first launch.

## Deploying on Oracle Cloud Free Tier

If you plan to host the bot on Oracle Cloud, follow the step-by-step guide in
[`docs/oracle_cloud_setup.md`](docs/oracle_cloud_setup.md) to provision a free-tier compute
instance, lock down networking, configure environment variables, and run the bot as a
systemd service.

## Commands overview

All commands must be executed inside a Discord guild.

### Event commands

- `/event` – list all known events for the guild.
- `/event create <name> [date] [venue] [city] [url]` – create a manual event.
- `/event import <edmtrain_id>` – import an event from EDMTrain by ID (requires API key).

### Buyer queue commands

- `/queue_join <event_id>` – join the buyer queue for an event.
- `/queue_leave <event_id>` – leave the buyer queue.
- `/queue_view <event_id>` – view the buyer queue with up to the first 15 entries.

### Seller commands

- `/ticket_sell <event_id> <price>` – list a ticket for sale and notify the next buyer in the queue.

When a seller lists a ticket, the bot records the listing and pings the first user waiting in the queue with the seller's asking price.

## Database

The bot uses SQLite to persist:

- Events and their metadata (name, date, venue, city, URL, source)
- Buyer queue entries (event, user, join order)
- Ticket listings (event, seller, price, timestamp)

Schema migrations are handled through the SQL statements located in `database/schema.sql`. The `DatabaseManager` class in `database/__init__.py` provides async helpers for interacting with the database and is initialized when the bot starts.

## Development

The project includes pytest coverage for the database manager. To run the test suite:

```bash
pytest
```

This repository inherits the Apache 2.0 license from the original template. See [LICENSE.md](LICENSE.md) for details.
