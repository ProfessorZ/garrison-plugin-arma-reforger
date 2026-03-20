"""Garrison plugin for Arma Reforger dedicated servers."""

from __future__ import annotations

import asyncio
import logging
import socket
from typing import Optional

try:
    from app.plugins.base import GamePlugin, PlayerInfo, ServerStatus, CommandDef, ServerOption
except ImportError:
    # Standalone mode — define minimal stubs so the module is importable outside Garrison
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

        async def send_command_custom(self, command: str) -> str:
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
        resolved = await loop.run_in_executor(
            None, lambda: socket.gethostbyname(host)
        )
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

    async def send_command_custom(self, command: str) -> str:
        """Open a short-lived berconpy connection, send command, return response."""
        if not self._resolved_ip:
            raise RuntimeError("Not connected to server — call connect_custom first")
        client = berconpy.RCONClient()
        try:
            async with asyncio.timeout(15):
                async with client.connect(self._resolved_ip, self._port, self._password):
                    return await client.send_command(command)
        except asyncio.TimeoutError:
            raise RuntimeError(f"Timed out connecting to Arma Reforger RCON at {self._resolved_ip}:{self._port}")

    async def parse_players(self, raw_response: str) -> list:
        players = []
        in_data = False
        for line in raw_response.strip().splitlines():
            line = line.strip()
            if "---" in line:
                in_data = True
                continue
            if not in_data or not line or line.startswith("(") or line.lower().startswith("players"):
                continue
            parts = line.split()
            if len(parts) >= 4:
                try:
                    player_idx = parts[0]
                    name = " ".join(parts[4:]).strip()
                    if name:
                        players.append(PlayerInfo(name=name, steam_id=player_idx))
                except (IndexError, ValueError):
                    continue
        return players

    async def get_status(self, send_command) -> ServerStatus:
        try:
            raw = await self.send_command_custom("players")
            players = await self.parse_players(raw)
            return ServerStatus(online=True, player_count=len(players))
        except Exception as exc:
            logger.warning("Status check failed: %s", exc)
            return ServerStatus(online=False)

    def get_commands(self) -> list:
        from schema import get_commands
        return get_commands()

    async def kick_player(self, send_command, name: str, reason: str = "") -> str:
        return await self.send_command_custom(f"#kick {name}")

    async def ban_player(self, send_command, name: str, reason: str = "") -> str:
        return await self.send_command_custom(f"#exec ban {name}")

    async def unban_player(self, send_command, name: str) -> str:
        return await self.send_command_custom(f"#exec unban {name}")

    async def say(self, message: str) -> str:
        return await self.send_command_custom(f"say {message}")

    async def list_missions(self) -> str:
        return await self.send_command_custom("#missions")

    async def load_mission(self, name: str) -> str:
        return await self.send_command_custom(f"#mission {name}")

    async def restart_mission(self) -> str:
        return await self.send_command_custom("#restart")

    async def reassign(self) -> str:
        return await self.send_command_custom("#reassign")

    async def shutdown(self) -> str:
        return await self.send_command_custom("#shutdown")
