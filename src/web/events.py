from __future__ import annotations

from typing import Any

from flask import session
from flask_socketio import SocketIO, emit, join_room, leave_room

# Store for active connections and their server subscriptions
# In production, use Redis or similar
connected_users: dict[str, set[int]] = {}  # sid -> set of server_ids


def _get_allowed_server_ids_from_session() -> set[int]:
    """Return server IDs the user is allowed to subscribe to (guilds in session)."""

    guilds = session.get("guilds")
    if not isinstance(guilds, list):
        return set()

    allowed: set[int] = set()
    for g in guilds:
        if isinstance(g, dict) and "id" in g:
            try:
                allowed.add(int(g["id"]))
            except Exception:
                continue

    return allowed


def register_events(socketio: SocketIO) -> None:
    """Register all WebSocket event handlers."""

    @socketio.on("connect")
    def handle_connect() -> None:
        """Handle client connection."""

        from flask import request

        sid = request.sid
        connected_users[sid] = set()

        discord_id = session.get("discord_id")
        if discord_id:
            join_room(f"user_{discord_id}")
            emit("connected", {"status": "ok", "discord_id": discord_id})
        else:
            emit("connected", {"status": "ok", "discord_id": None})

    @socketio.on("disconnect")
    def handle_disconnect() -> None:
        """Handle client disconnection."""

        from flask import request

        sid = request.sid

        if sid in connected_users:
            for server_id in connected_users[sid]:
                leave_room(f"server_{server_id}")
            del connected_users[sid]

        discord_id = session.get("discord_id")
        if discord_id:
            leave_room(f"user_{discord_id}")

    @socketio.on("subscribe_servers")
    def handle_subscribe_servers(data: dict) -> None:
        """Subscribe to day change events for specific servers."""

        from flask import request

        sid = request.sid
        server_ids = data.get("server_ids", [])

        if sid not in connected_users:
            connected_users[sid] = set()

        allowed_ids = _get_allowed_server_ids_from_session()

        for server_id in server_ids:
            try:
                sid_int = int(server_id)
            except Exception:
                continue

            if sid_int not in allowed_ids:
                continue

            if sid_int not in connected_users[sid]:
                join_room(f"server_{sid_int}")
                connected_users[sid].add(sid_int)

        emit("subscribed", {"server_ids": list(connected_users[sid])})

    @socketio.on("unsubscribe_servers")
    def handle_unsubscribe_servers(data: dict) -> None:
        """Unsubscribe from day change events for specific servers."""

        from flask import request

        sid = request.sid
        server_ids = data.get("server_ids", [])

        if sid in connected_users:
            for server_id in server_ids:
                try:
                    sid_int = int(server_id)
                except Exception:
                    continue

                if sid_int in connected_users[sid]:
                    leave_room(f"server_{sid_int}")
                    connected_users[sid].discard(sid_int)

        emit("unsubscribed", {"server_ids": server_ids})


def broadcast_day_change(socketio: SocketIO, summary_data: dict[str, Any]) -> None:
    """Broadcast a single server day-change summary to subscribed clients."""

    server_id = int(summary_data.get("server_discord_id", 0))
    if not server_id:
        return

    socketio.emit("day_change", summary_data, room=f"server_{server_id}")
