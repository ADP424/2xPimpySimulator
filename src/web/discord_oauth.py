from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlencode

import requests
from flask import current_app, session

DISCORD_API_BASE = "https://discord.com/api/v10"
DISCORD_OAUTH_AUTHORIZE = "https://discord.com/api/oauth2/authorize"
DISCORD_OAUTH_TOKEN = "https://discord.com/api/oauth2/token"


@dataclass(frozen=True)
class DiscordUser:
    """Represents a Discord user from OAuth."""

    id: int
    username: str
    discriminator: str
    avatar: Optional[str]

    @property
    def avatar_url(self) -> str:
        if self.avatar:
            return f"https://cdn.discordapp.com/avatars/{self.id}/{self.avatar}.png"

        default_avatar_index = (self.id >> 22) % 6
        return f"https://cdn.discordapp.com/embed/avatars/{default_avatar_index}.png"

    def to_dict(self) -> dict:
        """Convert to a JSON-serializable dictionary."""

        return {
            "id": self.id,
            "username": self.username,
            "discriminator": self.discriminator,
            "avatar": self.avatar,
            "avatar_url": self.avatar_url,
        }


@dataclass(frozen=True)
class DiscordGuild:
    """Represents a Discord guild/server from OAuth."""

    id: int
    name: str
    icon: Optional[str]
    owner: bool
    permissions: int

    @property
    def icon_url(self) -> Optional[str]:
        if self.icon:
            return f"https://cdn.discordapp.com/icons/{self.id}/{self.icon}.png"
        return None

    def to_dict(self) -> dict:
        """Convert to a JSON-serializable dictionary."""

        return {
            "id": self.id,
            "name": self.name,
            "icon": self.icon,
            "icon_url": self.icon_url,
            "owner": self.owner,
            "permissions": self.permissions,
        }


def get_oauth_url(state: str) -> str:
    """Generate the Discord OAuth2 authorization URL."""

    params = {
        "client_id": current_app.config["DISCORD_CLIENT_ID"],
        "redirect_uri": current_app.config["DISCORD_REDIRECT_URI"],
        "response_type": "code",
        "scope": "identify guilds",
        "state": state,
    }
    return f"{DISCORD_OAUTH_AUTHORIZE}?{urlencode(params)}"


def exchange_code(code: str) -> dict:
    """Exchange an authorization code for access tokens."""

    data = {
        "client_id": current_app.config["DISCORD_CLIENT_ID"],
        "client_secret": current_app.config["DISCORD_CLIENT_SECRET"],
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": current_app.config["DISCORD_REDIRECT_URI"],
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    response = requests.post(DISCORD_OAUTH_TOKEN, data=data, headers=headers)
    response.raise_for_status()
    return response.json()


def get_user(access_token: str) -> DiscordUser:
    """Fetch the current user's Discord profile."""

    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(f"{DISCORD_API_BASE}/users/@me", headers=headers)
    response.raise_for_status()
    data = response.json()

    return DiscordUser(
        id=int(data["id"]),
        username=data["username"],
        discriminator=data.get("discriminator", "0"),
        avatar=data.get("avatar"),
    )


def get_user_guilds(access_token: str) -> list[DiscordGuild]:
    """Fetch the guilds the user is a member of."""

    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(f"{DISCORD_API_BASE}/users/@me/guilds", headers=headers)
    response.raise_for_status()

    guilds: list[DiscordGuild] = []
    for data in response.json():
        guilds.append(
            DiscordGuild(
                id=int(data["id"]),
                name=data["name"],
                icon=data.get("icon"),
                owner=data.get("owner", False),
                permissions=int(data.get("permissions", 0)),
            )
        )

    return guilds


def store_user_in_session(user: DiscordUser, guilds: list[DiscordGuild], access_token: str) -> None:
    """Store user/guild data in the Flask session."""

    session["discord_id"] = user.id
    session["discord_username"] = user.username
    session["discord_avatar_url"] = user.avatar_url
    session["access_token"] = access_token

    # Store guilds as plain dicts for session serialization.
    session["guilds"] = [guild.to_dict() for guild in guilds]


def get_guild_dicts_from_session() -> list[dict]:
    """Return guild dictionaries stored in the session."""

    guilds = session.get("guilds")
    if not guilds:
        return []

    if isinstance(guilds, list) and guilds and isinstance(guilds[0], int):
        # Old/corrupted format (IDs only)
        session.pop("guilds", None)
        current_app.logger.warning("Cleared invalid guild list from session (IDs only).")
        return []

    out: list[dict] = []
    for g in guilds:
        if isinstance(g, dict) and "id" in g and "name" in g:
            out.append(g)
        else:
            current_app.logger.warning(f"Invalid guild format in session: {g}")

    return out


def get_guilds_from_session() -> list[DiscordGuild]:
    """Return guilds stored in the session as typed dataclasses."""

    guild_dicts = get_guild_dicts_from_session()
    guilds: list[DiscordGuild] = []

    for g in guild_dicts:
        try:
            guilds.append(
                DiscordGuild(
                    id=int(g["id"]),
                    name=str(g.get("name", "")),
                    icon=g.get("icon"),
                    owner=bool(g.get("owner", False)),
                    permissions=int(g.get("permissions", 0)),
                )
            )
        except Exception:
            current_app.logger.warning(f"Failed to parse guild from session: {g}")

    return guilds
