# garrison-plugin-arma-reforger

RCON plugin for Arma Reforger dedicated servers, built for [Garrison](https://github.com/ProfessorZ).

## Features

- BattlEye RCON (UDP) protocol with CRC32 verification and multi-packet reassembly
- Player listing, kick, ban, and unban
- Mission management and server restart/shutdown
- Automatic keepalive and server-message acknowledgement

## RCON Limitations

Arma Reforger's BattlEye RCON has several limitations compared to other game servers:

- **No chat support** — RCON cannot send or receive in-game chat messages.
- **UUID-only identification** — Players are identified by their BI UUID, not by Steam ID or IP address. Kick/ban commands require the UUID.
- **No real-time events** — There is no push-based player join/leave notification; the plugin polls `get players`.
- **No Steam ID mapping** — The server does not expose Steam IDs through RCON.

## Server Configuration

Enable RCON in your server's `server.json`:

```json
{
  "game": {
    "port": 2001
  },
  "a2s": {
    "address": "0.0.0.0",
    "port": 17777
  },
  "rcon": {
    "address": "0.0.0.0",
    "port": 2301,
    "password": "your_rcon_password",
    "maxClients": 5
  }
}
```

## Default Ports

| Protocol | Port |
|----------|------|
| Game     | 2001 |
| RCON     | 2301 |

## Installation

1. Copy this plugin directory into your Garrison `plugins/` folder.
2. Ensure the folder is named `arma-reforger` to match the plugin ID.
3. Configure your server entry in Garrison with the correct host, RCON port, and RCON password.

## Available Commands

| Command       | Description                          |
|---------------|--------------------------------------|
| `get players` | List connected players and UUIDs     |
| `kick`        | Kick a player by UUID                |
| `ban`         | Ban a player by UUID                 |
| `unban`       | Unban a player by UUID               |
| `getBans`     | List all active bans                 |
| `missions`    | List available missions              |
| `mission`     | Load a specific mission              |
| `restart`     | Restart the server                   |
| `shutdown`    | Shut down the server                 |
