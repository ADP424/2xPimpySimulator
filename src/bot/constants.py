"""
Bot-layer constants.

These affect Discord UX, interaction pacing, and safety limits.
They should NEVER contain gameplay logic.
"""

import discord

# Server
GUILDS = [discord.Object(id=1267910656838078474)]

# UI Timing
VIEW_TIMEOUT = 300

# Pagination / Layout
ITEMS_PER_PAGE = 10
