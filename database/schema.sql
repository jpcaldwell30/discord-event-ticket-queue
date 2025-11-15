CREATE TABLE IF NOT EXISTS `warns` (
  `id` int(11) NOT NULL,
  `user_id` varchar(20) NOT NULL,
  `server_id` varchar(20) NOT NULL,
  `moderator_id` varchar(20) NOT NULL,
  `reason` varchar(255) NOT NULL,
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS `events` (
  `id` INTEGER PRIMARY KEY AUTOINCREMENT,
  `guild_id` TEXT NOT NULL,
  `name` TEXT NOT NULL,
  `date` TEXT,
  `venue` TEXT,
  `city` TEXT,
  `url` TEXT,
  `source` TEXT NOT NULL,
  `source_id` TEXT,
  `created_by` TEXT NOT NULL,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(`guild_id`, `source`, `source_id`)
);

CREATE TABLE IF NOT EXISTS `buyer_queue` (
  `id` INTEGER PRIMARY KEY AUTOINCREMENT,
  `event_id` INTEGER NOT NULL,
  `user_id` TEXT NOT NULL,
  `joined_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(`event_id`, `user_id`),
  FOREIGN KEY(`event_id`) REFERENCES `events`(`id`) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS `tickets` (
  `id` INTEGER PRIMARY KEY AUTOINCREMENT,
  `event_id` INTEGER NOT NULL,
  `seller_id` TEXT NOT NULL,
  `price` REAL NOT NULL,
  `status` TEXT NOT NULL DEFAULT 'available',
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(`event_id`) REFERENCES `events`(`id`) ON DELETE CASCADE
);
