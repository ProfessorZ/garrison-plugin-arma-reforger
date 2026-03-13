"""Command definitions for Arma Reforger RCON."""

from app.plugins.base import CommandDef

commands = [
    CommandDef(
        name="get players",
        description="List all connected players with their UUIDs",
        pattern="get players",
    ),
    CommandDef(
        name="kick",
        description="Kick a player by UUID with an optional reason",
        pattern="kick <uuid> [reason]",
    ),
    CommandDef(
        name="ban",
        description="Ban a player by UUID with an optional reason",
        pattern="ban <uuid> [reason]",
    ),
    CommandDef(
        name="unban",
        description="Unban a player by UUID",
        pattern="unban <uuid>",
    ),
    CommandDef(
        name="getBans",
        description="List all active bans",
        pattern="getBans",
    ),
    CommandDef(
        name="missions",
        description="List available missions",
        pattern="missions",
    ),
    CommandDef(
        name="mission",
        description="Load a specific mission by name",
        pattern="mission <name>",
    ),
    CommandDef(
        name="restart",
        description="Restart the server",
        pattern="restart",
    ),
    CommandDef(
        name="shutdown",
        description="Shut down the server",
        pattern="shutdown",
    ),
]
