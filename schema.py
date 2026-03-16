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
            name="#kick <playerID>",
            description="Kick a player by ID",
            category="PLAYER_MGMT",
            params=[
                CommandParam(
                    name="playerID",
                    type="integer",
                    required=True,
                    description="Player ID to kick",
                )
            ],
        ),
        CommandDef(
            name="#exec ban <playerID>",
            description="Ban a player by ID",
            category="PLAYER_MGMT",
            params=[
                CommandParam(
                    name="playerID",
                    type="integer",
                    required=True,
                    description="Player ID to ban",
                )
            ],
        ),
        CommandDef(
            name="#exec unban <playerID>",
            description="Unban a player by ID",
            category="PLAYER_MGMT",
            params=[
                CommandParam(
                    name="playerID",
                    type="integer",
                    required=True,
                    description="Player ID to unban",
                )
            ],
        ),
        CommandDef(
            name="say <message>",
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
            name="#reassign",
            description="Move all players to role selection",
            category="PLAYER_MGMT",
        ),
        CommandDef(
            name="#missions",
            description="List available missions",
            category="MISSION",
        ),
        CommandDef(
            name="#mission <name>",
            description="Load a mission by name",
            category="MISSION",
            params=[
                CommandParam(
                    name="name",
                    type="string",
                    required=True,
                    description="Mission name to load",
                )
            ],
        ),
        CommandDef(
            name="#restart",
            description="Restart the current mission",
            category="MISSION",
        ),
        CommandDef(
            name="#shutdown",
            description="Gracefully shut down the server",
            category="SERVER",
        ),
    ]
