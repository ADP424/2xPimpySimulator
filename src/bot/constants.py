import discord

# Server
GUILDS = [discord.Object(id=1267910656838078474), discord.Object(id=618568730162495498)]

# UI Timing
VIEW_TIMEOUT = 300

# Automated event timing
EVENT_LOOP_INTERVAL_SECONDS = 60 * 60
WEEK_LOOP_INTERVAL_SECONDS = 7 * 24 * 60 * 60

# Alpha runs game time at double speed: an hour tick every 30 minutes and a week every 3.5 days.
# Owner events still roll once per real hour (every ALPHA_OWNER_EVENT_TICK_STRIDE ticks).
ALPHA_HOUR_INTERVAL_SECONDS = EVENT_LOOP_INTERVAL_SECONDS // 2
ALPHA_WEEK_INTERVAL_SECONDS = WEEK_LOOP_INTERVAL_SECONDS // 2
ALPHA_OWNER_EVENT_TICK_STRIDE = 2

# Pagination / Layout
ITEMS_PER_PAGE = 10

# Text / naming limits
MAX_NAME_LENGTH = 100

# Discord UI limits
DISCORD_SELECT_MAX_OPTIONS = 25
DISCORD_LABEL_MAX_LENGTH = 100
DISCORD_DESCRIPTION_MAX_LENGTH = 100
