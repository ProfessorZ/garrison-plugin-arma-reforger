"""Garrison GamePlugin for Arma Reforger dedicated servers."""

import logging
import re
from typing import Optional

from app.plugins.base import GamePlugin, PlayerInfo, ServerStatus, CommandDef, ServerOption
from .bercon import BERConConnection
from .schema import commands

logger = logging.getLogger(__name__)

# Regex for parsing "get players" output lines.
# Expected format: "  <index> <uuid> <name>"
_PLAYER_RE = re.compile(r"^\s*\d+\s+([0-9a-fA-F-]{36})\s+(.+)$", re.MULTILINE)


class ArmaReforgerPlugin(GamePlugin):
    custom_connection = True
    game_type = "arma-reforger"
    display_name = "Arma Reforger"

    def __init__(self, server: dict, options: Optional[dict] = None):
        super().__init__(server, options)
        host = server.get("host", "127.0.0.1")
        port = server.get("rcon_port", 2301)
        password = server.get("rcon_password", "")
        self._conn = BERConConnection(host, port, password)

    # ── connection lifecycle ────────────────────────────────────────

    async def connect(self) -> None:
        await self._conn.connect()

    async def disconnect(self) -> None:
        await self._conn.close()

    # ── commands ────────────────────────────────────────────────────

    def get_commands(self) -> list[CommandDef]:
        return commands

    # ── players ─────────────────────────────────────────────────────

    async def get_players(self) -> list[PlayerInfo]:
        raw = await self._conn.send_command("get players")
        players = []
        for match in _PLAYER_RE.finditer(raw):
            uuid = match.group(1)
            name = match.group(2).strip()
            players.append(PlayerInfo(name=name, uid=uuid))
        return players

    async def _resolve_uuid(self, name: str) -> str:
        """Resolve a player name to their UUID."""
        players = await self.get_players()
        for p in players:
            if p.name.lower() == name.lower():
                return p.uid
        raise ValueError(f"Player not found: {name}")

    # ── status ──────────────────────────────────────────────────────

    async def get_status(self) -> ServerStatus:
        try:
            players = await self.get_players()
            return ServerStatus(online=True, player_count=len(players), players=players)
        except Exception as exc:
            logger.warning("Status check failed: %s", exc)
            return ServerStatus(online=False, player_count=0, players=[])

    # ── moderation ──────────────────────────────────────────────────

    async def kick_player(self, name: str, reason: str = "") -> str:
        uuid = await self._resolve_uuid(name)
        cmd = f"kick {uuid}"
        if reason:
            cmd += f" {reason}"
        return await self._conn.send_command(cmd)

    async def ban_player(self, name: str, reason: str = "") -> str:
        uuid = await self._resolve_uuid(name)
        cmd = f"ban {uuid}"
        if reason:
            cmd += f" {reason}"
        return await self._conn.send_command(cmd)

    async def unban_player(self, name: str) -> str:
        # For unban, name is expected to be the UUID directly
        return await self._conn.send_command(f"unban {name}")

    # ── raw command passthrough ─────────────────────────────────────

    async def send_command(self, command: str) -> str:
        return await self._conn.send_command(command)
