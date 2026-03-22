from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CommandParam:
    name: str
    type: str
    required: bool = True
    description: str = ""
    choices: list[str] = field(default_factory=list)
    default: Optional[str] = None


@dataclass
class CommandDef:
    name: str
    description: str
    category: str
    params: list[CommandParam] = field(default_factory=list)
    admin_only: bool = False
    example: str = ""


def get_commands():
    return [
        CommandDef(
            name="players",
            description="List connected players",
            category="PLAYER_MGMT",
        ),
        CommandDef(
            name="say",
            description="Send a global broadcast message",
            category="PLAYER_MGMT",
            params=[
                CommandParam(
                    name="message",
                    type="string",
                    required=True,
                    description="Message to broadcast",
                )
            ],
        ),
        CommandDef(
            name="whisper",
            description="Send a private message to a player",
            category="PLAYER_MGMT",
            params=[
                CommandParam(
                    name="playerID",
                    type="integer",
                    required=True,
                    description="Player numeric ID",
                ),
                CommandParam(
                    name="message",
                    type="string",
                    required=True,
                    description="Private message to send",
                ),
            ],
        ),
        CommandDef(
            name="kick",
            description="Kick a player by numeric ID",
            category="MODERATION",
            params=[
                CommandParam(
                    name="playerID",
                    type="integer",
                    required=True,
                    description="Player numeric ID to kick",
                ),
                CommandParam(
                    name="reason",
                    type="string",
                    required=False,
                    description="Kick reason",
                    default="",
                ),
            ],
        ),
        CommandDef(
            name="ban",
            description="Ban a player permanently by numeric ID",
            category="MODERATION",
            params=[
                CommandParam(
                    name="playerID",
                    type="integer",
                    required=True,
                    description="Player numeric ID to ban",
                ),
                CommandParam(
                    name="duration",
                    type="integer",
                    required=False,
                    description="Duration in minutes (0 = permanent)",
                    default="0",
                ),
                CommandParam(
                    name="reason",
                    type="string",
                    required=False,
                    description="Ban reason",
                    default="",
                ),
            ],
        ),
        CommandDef(
            name="unban",
            description="Unban by GUID, IP, or ban index",
            category="MODERATION",
            params=[
                CommandParam(
                    name="identifier",
                    type="string",
                    required=True,
                    description="GUID, IP address, or ban index",
                ),
            ],
        ),
        CommandDef(
            name="bans",
            description="List all active bans",
            category="MODERATION",
        ),
        CommandDef(
            name="lock",
            description="Lock server to prevent new connections",
            category="MODERATION",
        ),
        CommandDef(
            name="unlock",
            description="Unlock server to allow new connections",
            category="MODERATION",
        ),
        CommandDef(
            name="missions",
            description="List available missions",
            category="MISSION",
        ),
        CommandDef(
            name="mission",
            description="Load a mission by name",
            category="MISSION",
            params=[
                CommandParam(
                    name="name",
                    type="string",
                    required=True,
                    description="Mission name to load",
                ),
                CommandParam(
                    name="difficulty",
                    type="string",
                    required=False,
                    description="Mission difficulty",
                    choices=["Regular", "Veteran", "Recruit"],
                    default="",
                ),
            ],
        ),
        CommandDef(
            name="restart",
            description="Restart the current mission",
            category="MISSION",
        ),
        CommandDef(
            name="reassign",
            description="Restart mission and move all players to role assignment",
            category="MISSION",
        ),
        CommandDef(
            name="restart_server",
            description="Restart the server process",
            category="SERVER",
            admin_only=True,
        ),
        CommandDef(
            name="shutdown",
            description="Gracefully shut down the server",
            category="SERVER",
            admin_only=True,
        ),
    ]
