"""Garrison plugin for Arma Reforger dedicated servers."""

from __future__ import annotations

import asyncio
import logging
import socket
from typing import Optional

try:
    from app.plugins.base import GamePlugin, PlayerInfo, ServerStatus
except ImportError:
    from dataclasses import dataclass, field
    from abc import ABC, abstractmethod

    @dataclass
    class PlayerInfo:
        name: str
        steam_id: Optional[str] = None

    @dataclass
    class ServerStatus:
        online: bool
        player_count: int = 0
        version: Optional[str] = None
        extra: dict = field(default_factory=dict)

    @dataclass
    class ServerOption:
        name: str
        value: str
        option_type: str
        category: str = "General"
        description: str = ""
        min_val: Optional[float] = None
        max_val: Optional[float] = None
        choices: list[str] = field(default_factory=list)

    @dataclass
    class CommandDef:
        name: str
        description: str
        category: str
        params: list = field(default_factory=list)
        admin_only: bool = False
        example: str = ""

    @dataclass
    class CommandParam:
        name: str
        type: str
        required: bool = True
        description: str = ""
        choices: list[str] = field(default_factory=list)
        default: Optional[str] = None

    class GamePlugin(ABC):
        PLUGIN_API_VERSION = 1
        custom_connection: bool = False

        @property
        @abstractmethod
        def game_type(self) -> str: ...

        @property
        @abstractmethod
        def display_name(self) -> str: ...

        @abstractmethod
        async def parse_players(self, raw_response: str) -> list: ...

        @abstractmethod
        async def get_status(self, send_command) -> ServerStatus: ...

        @abstractmethod
        def get_commands(self) -> list: ...

        def format_command(self, command: str) -> str:
            return command

        async def get_options(self, send_command) -> list:
            return []

        async def set_option(self, send_command, name: str, value: str) -> str:
            raise NotImplementedError

        async def kick_player(self, send_command, name: str, reason: str = "") -> str:
            raise NotImplementedError

        async def ban_player(self, send_command, name: str, reason: str = "") -> str:
            raise NotImplementedError

        async def unban_player(self, send_command, name: str) -> str:
            raise NotImplementedError

        async def connect_custom(self, host: str, port: int, password: str) -> None:
            raise NotImplementedError

        async def disconnect_custom(self) -> None:
            raise NotImplementedError

        async def send_command_custom(self, command: str, content=None) -> str:
            raise NotImplementedError


import berconpy

logger = logging.getLogger(__name__)


class ArmaReforgerPlugin(GamePlugin):
    """Arma Reforger BattleEye RCON plugin.

    berconpy is designed exclusively around the `async with client.connect()`
    context manager pattern — it holds weak refs to the client internally, so
    persistent connect/disconnect lifecycle management causes GC-related
    ReferenceErrors and state machine conflicts.

    Instead we store credentials in connect_custom and open a fresh
    async-with connection per command in send_command_custom. BattleEye
    is UDP so the per-command connection overhead is negligible.
    """

    custom_connection = True

    def __init__(self):
        self._host: Optional[str] = None
        self._port: Optional[int] = None
        self._password: Optional[str] = None
        self._resolved_ip: Optional[str] = None

    @property
    def game_type(self) -> str:
        return "arma-reforger"

    @property
    def display_name(self) -> str:
        return "Arma Reforger"

    async def connect_custom(self, host: str, port: int, password: str) -> None:
        """Store credentials and pre-resolve hostname. No persistent socket."""
        loop = asyncio.get_running_loop()
        resolved = await loop.run_in_executor(None, lambda: socket.gethostbyname(host))
        self._host = host
        self._port = port
        self._password = password
        self._resolved_ip = resolved

    async def disconnect_custom(self) -> None:
        """Clear credentials — no persistent socket to close."""
        self._host = None
        self._port = None
        self._password = None
        self._resolved_ip = None

    def _get_client(self) -> berconpy.ArmaClient:
        if not self._resolved_ip:
            raise RuntimeError("Not connected to server — call connect_custom first")
        return berconpy.ArmaClient()

    async def _with_client(self, coro):
        """Execute a coroutine within a fresh berconpy connection context."""
        client = self._get_client()
        async with asyncio.timeout(15):
            async with client.connect(self._resolved_ip, self._port, self._password):
                return await coro(client)

    async def send_command_custom(self, command: str, content=None) -> str:
        """Open a short-lived berconpy ArmaClient connection, send command, return response."""
        try:
            return await self._with_client(lambda client: client.send_command(command))
        except asyncio.TimeoutError:
            raise RuntimeError(
                f"Timed out connecting to Arma Reforger RCON at {self._resolved_ip}:{self._port}"
            )

    async def parse_players(self, raw_response: str) -> list[PlayerInfo]:
        """Parse the text format player list response (legacy interface)."""
        players = []
        in_data = False
        for line in raw_response.strip().splitlines():
            line = line.strip()
            if "---" in line:
                in_data = True
                continue
            if (
                not in_data
                or not line
                or line.startswith("(")
                or line.lower().startswith("players")
            ):
                continue
            parts = line.split()
            if len(parts) >= 5:
                try:
                    player_idx = parts[0]
                    guid_with_status = parts[-2]
                    name = " ".join(parts[4:-2]).strip()
                    if name:
                        players.append(PlayerInfo(name=name, steam_id=player_idx))
                except (IndexError, ValueError):
                    continue
        return players

    async def get_status(self, send_command) -> ServerStatus:
        """Get server status using the players command."""
        try:
            raw = await self.send_command_custom("players")
            players = await self.parse_players(raw)
            return ServerStatus(
                online=True, player_count=len(players), extra={"game": "arma-reforger"}
            )
        except Exception as exc:
            logger.warning("Status check failed: %s", exc)
            return ServerStatus(online=False, extra={"game": "arma-reforger"})

    def get_commands(self) -> list:
        from schema import get_commands

        return get_commands()

    async def _get_player_by_name_or_id(
        self, client: berconpy.ArmaClient, name_or_id: str
    ) -> Optional[object]:
        """Try to match player by numeric ID first, then exact name, then case-insensitive name."""
        try:
            numeric_id = int(name_or_id)
        except ValueError:
            numeric_id = None

        players = await client.fetch_players()

        if numeric_id is not None:
            for p in players:
                if p.id == numeric_id:
                    return p

        for p in players:
            if p.name == name_or_id:
                return p

        for p in players:
            if p.name.lower() == name_or_id.lower():
                return p

        return None

    async def kick_player(self, send_command, name_or_id: str, reason: str = "") -> str:
        """Kick a player by numeric ID or name."""
        try:
            player = await self._with_client(
                lambda client: self._get_player_by_name_or_id(client, name_or_id)
            )
            if not player:
                return f"Player not found: {name_or_id}"

            async def do_kick(client):
                await client.kick(player.id, reason)
                return f"Kicked player {player.name} (ID {player.id})"

            return await self._with_client(do_kick)
        except Exception as exc:
            logger.warning("Kick failed for %s: %s", name_or_id, exc)
            return f"Failed to kick player: {exc}"

    async def ban_player(self, send_command, name_or_id: str, reason: str = "") -> str:
        """Ban a player permanently by numeric ID or name."""
        try:
            player = await self._with_client(
                lambda client: self._get_player_by_name_or_id(client, name_or_id)
            )
            if not player:
                return f"Player not found: {name_or_id}"

            async def do_ban(client):
                await client.ban(player.id, None, reason)
                return f"Banned player {player.name} (ID {player.id}) permanently"

            return await self._with_client(do_ban)
        except Exception as exc:
            logger.warning("Ban failed for %s: %s", name_or_id, exc)
            return f"Failed to ban player: {exc}"

    async def unban_player(self, send_command, identifier: str) -> str:
        """Unban by GUID, IP, or ban index."""
        try:

            async def do_unban(client):
                bans = await client.fetch_bans()
                for ban in bans:
                    if ban.id == identifier:
                        await client.unban(ban.index)
                        return f"Unbanned {identifier} (ban index {ban.index})"

                try:
                    index = int(identifier)
                    await client.unban(index)
                    return f"Unbanned by index {index}"
                except ValueError:
                    pass

                return f"Ban not found: {identifier}"

            return await self._with_client(do_unban)
        except Exception as exc:
            logger.warning("Unban failed for %s: %s", identifier, exc)
            return f"Failed to unban: {exc}"

    async def say(self, message: str) -> str:
        """Send a global broadcast message."""
        try:

            async def do_send(client):
                await client.send(message)
                return f"Broadcast sent: {message}"

            return await self._with_client(do_send)
        except Exception as exc:
            logger.warning("Say failed: %s", exc)
            return f"Failed to send broadcast: {exc}"

    async def whisper(self, player_id: int, message: str) -> str:
        """Send a private message to a player."""
        try:

            async def do_whisper(client):
                await client.whisper(player_id, message)
                return f"Message sent to player {player_id}"

            return await self._with_client(do_whisper)
        except Exception as exc:
            logger.warning("Whisper failed for player %d: %s", player_id, exc)
            return f"Failed to whisper: {exc}"

    async def list_players(self) -> list[dict]:
        """Return list of connected players as dicts."""
        try:

            async def do_list(client):
                players = await client.fetch_players()
                return [
                    {
                        "id": p.id,
                        "name": p.name,
                        "guid": p.guid,
                        "addr": p.addr,
                        "ping": p.ping,
                        "in_lobby": p.in_lobby,
                        "is_guid_valid": p.is_guid_valid,
                    }
                    for p in players
                ]

            return await self._with_client(do_list)
        except Exception as exc:
            logger.warning("List players failed: %s", exc)
            return []

    async def list_bans(self) -> list[dict]:
        """Return list of active bans as dicts."""
        try:

            async def do_list(client):
                bans = await client.fetch_bans()
                return [
                    {
                        "index": b.index,
                        "id": b.id,
                        "duration": b.duration,
                        "reason": b.reason,
                    }
                    for b in bans
                ]

            return await self._with_client(do_list)
        except Exception as exc:
            logger.warning("List bans failed: %s", exc)
            return []

    async def list_missions(self) -> list[str]:
        """Return list of available missions."""
        try:

            async def do_list(client):
                return await client.fetch_missions()

            return await self._with_client(do_list)
        except Exception as exc:
            logger.warning("List missions failed: %s", exc)
            return []

    async def load_mission(self, name: str, difficulty: str = "") -> str:
        """Load a mission with optional difficulty."""
        try:

            async def do_load(client):
                await client.select_mission(name, difficulty)
                diff_msg = f" (difficulty: {difficulty})" if difficulty else ""
                return f"Loading mission: {name}{diff_msg}"

            return await self._with_client(do_load)
        except Exception as exc:
            logger.warning("Load mission failed for %s: %s", name, exc)
            return f"Failed to load mission: {exc}"

    async def restart_mission(self) -> str:
        """Restart the current mission."""
        try:

            async def do_restart(client):
                await client.restart_mission()
                return "Restarting current mission"

            return await self._with_client(do_restart)
        except Exception as exc:
            logger.warning("Restart mission failed: %s", exc)
            return f"Failed to restart mission: {exc}"

    async def restart_and_reassign(self) -> str:
        """Restart mission and move all players to role assignment."""
        try:

            async def do_reassign(client):
                await client.restart_and_reassign()
                return "Restarting mission and reassigning players"

            return await self._with_client(do_reassign)
        except Exception as exc:
            logger.warning("Restart and reassign failed: %s", exc)
            return f"Failed to restart and reassign: {exc}"

    async def restart_server(self) -> str:
        """Restart the server process."""
        try:

            async def do_restart(client):
                await client.restart_server()
                return "Server restart initiated"

            return await self._with_client(do_restart)
        except Exception as exc:
            logger.warning("Restart server failed: %s", exc)
            return f"Failed to restart server: {exc}"

    async def shutdown_server(self) -> str:
        """Gracefully shut down the server."""
        try:

            async def do_shutdown(client):
                await client.shutdown_server()
                return "Server shutdown initiated"

            return await self._with_client(do_shutdown)
        except Exception as exc:
            logger.warning("Shutdown server failed: %s", exc)
            return f"Failed to shutdown server: {exc}"

    async def lock_server(self) -> str:
        """Lock the server to prevent new connections."""
        try:

            async def do_lock(client):
                await client.lock_server()
                return "Server locked"

            return await self._with_client(do_lock)
        except Exception as exc:
            logger.warning("Lock server failed: %s", exc)
            return f"Failed to lock server: {exc}"

    async def unlock_server(self) -> str:
        """Unlock the server to allow new connections."""
        try:

            async def do_unlock(client):
                await client.unlock_server()
                return "Server unlocked"

            return await self._with_client(do_unlock)
        except Exception as exc:
            logger.warning("Unlock server failed: %s", exc)
            return f"Failed to unlock server: {exc}"
