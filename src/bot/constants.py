"""
Bot-layer constants.

These affect Discord UX, interaction pacing, and safety limits.
They should NEVER contain gameplay logic.
"""

import discord

# Server
GUILDS = [discord.Object(id=1267910656838078474), discord.Object(id=618568730162495498)]

# UI Timing
VIEW_TIMEOUT = 300

# Pagination / Layout
ITEMS_PER_PAGE = 10

# Text / naming limits
# Discord embed titles are limited to 256 characters, which is also a sensible upper bound
# for user-supplied names that will be shown prominently in UI.
MAX_NAME_LENGTH = 100
