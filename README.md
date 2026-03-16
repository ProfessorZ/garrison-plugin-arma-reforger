# garrison-plugin-arma-reforger

RCON plugin for Arma Reforger dedicated servers, built for [Garrison](https://github.com/ProfessorZ).

## RCON Setup

To enable RCON on your Arma Reforger server, edit the `BEServer_x64.cfg` file and add the following lines:

```
RConPort 2302
RConPassword yourpassword
```

**Warning:** Do not erase existing `BEServer_x64.cfg` content, append only.

## Default Ports

| Protocol | Port |
|----------|------|
| Game     | 2001 |
| RCON     | 2302 |

## Official Documentation

For more details on server hosting, see the official Arma Reforger documentation:
https://community.bistudio.com/wiki/Arma_Reforger:Server_Hosting

## Supported Commands

| Command | Description |
|---------|-------------|
| **PLAYER_MGMT** | |
| `players` | List connected players |
| `#kick <playerID>` | Kick a player by ID |
| `#exec ban <playerID>` | Ban a player by ID |
| `#exec unban <playerID>` | Unban a player by ID |
| `say <message>` | Send a global broadcast message |
| `#reassign` | Move all players to role selection |
| **MISSION** | |
| `#missions` | List available missions |
| `#mission <name>` | Load a mission by name |
| `#restart` | Restart the current mission |
| **SERVER** | |
| `#shutdown` | Gracefully shut down the server |
