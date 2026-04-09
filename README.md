# Radarr and Sonarr MCP Server

A Python-based Model Context Protocol (MCP) server that gives Claude direct access to your Radarr (movies) and Sonarr (TV series) — browse, search, and add content without leaving your conversation.

> Fork of [BerryKuipers/mcp_services_radarr_sonarr](https://github.com/BerryKuipers/mcp_services_radarr_sonarr) with FastMCP v3 compatibility fixes, missing `config.py`, and new tools for adding content and managing quality profiles.

## Features

- Browse your movie and TV library with filters (year, downloaded status)
- Search TMDB/TVDB for new content
- Add movies and series directly from Claude, with quality profile selection
- List and manage quality profiles and root folders

## Quick Start (Claude Code — stdio)

This is the recommended setup. Claude Code spawns the server as a subprocess — no ports, no network transport issues.

**1. Clone and install**

```bash
git clone https://github.com/riichard/mcp_services_radarr_sonarr ~/dev/mcp-radarr-sonarr
cd ~/dev/mcp-radarr-sonarr
python3 -m venv .venv
.venv/bin/pip install -e . mcp
```

**2. Find your API keys**

In Radarr: Settings → General → API Key
In Sonarr: Settings → General → API Key

**3. Register with Claude Code**

```bash
claude mcp add radarr-sonarr \
  --scope user \
  -e NAS_IP=192.168.1.100 \
  -e RADARR_API_KEY=your_radarr_key \
  -e RADARR_PORT=7878 \
  -e SONARR_API_KEY=your_sonarr_key \
  -e SONARR_PORT=8989 \
  -- ~/dev/mcp-radarr-sonarr/.venv/bin/python ~/dev/mcp-radarr-sonarr/stdio_server.py
```

Replace `192.168.1.100` with your server's IP and fill in your API keys.

That's it — restart Claude Code and start asking.

## Available Tools

### Movies
| Tool | Description |
|------|-------------|
| `get_available_movies` | List your library, optionally filtered by `year` or `downloaded` |
| `lookup_movie` | Search TMDB for a movie by title |
| `add_movie` | Add a movie by TMDB ID with a chosen quality profile |
| `get_radarr_quality_profiles` | List available quality profiles |
| `get_radarr_root_folders` | List configured root folders |

### TV Series
| Tool | Description |
|------|-------------|
| `get_available_series` | List your library, optionally filtered by `year` or `downloaded` |
| `lookup_series` | Search TVDB for a series by title |
| `add_series` | Add a series by TVDB ID with a chosen quality profile |
| `get_series_episodes` | List episodes for a series by Sonarr ID |
| `get_sonarr_quality_profiles` | List available quality profiles |
| `get_sonarr_root_folders` | List configured root folders |

## Example Prompts

```
What sci-fi movies from 2023 do I have downloaded?
Look up The Mandalorian and add it with my 1080p x265 profile.
What TV shows do I have that aren't fully downloaded yet?
Add Dune Part Two — use whatever my best quality profile is.
How many episodes of Stranger Things do I have?
```

## Shared Server (optional)

If multiple people on your LAN want to use the same server (e.g. a shared NAS), you can run `stdio_server.py` as a network-accessible SSE server on the NAS instead. See the `run.py` entrypoint and configure it as a systemd service. Each client then connects via:

```bash
claude mcp add --transport sse --scope user radarr-sonarr http://your-nas-ip:3000/sse
```

Note: SSE transport compatibility with Claude Code varies by FastMCP version. The stdio approach above is more reliable.

## Requirements

- Python 3.9+
- `mcp` package (official MCP SDK)
- `requests`
- Radarr and/or Sonarr running on your network

## Changes from upstream

- Added missing `config.py` module (upstream never committed it)
- Fixed FastMCP v3 breaking changes (removed unsupported `description` kwarg, transport compatibility)
- Fixed `Series.from_dict` crash on lookup results (missing `id` field before adding to library)
- Fixed all `Movie`/`Series` dataclass attribute access (upstream used dict `.get()` on typed objects)
- Fixed `is_series_watched` called with `str` instead of `Series` object
- Added `add_series`, `add_movie` tools
- Added `get_quality_profiles`, `get_root_folders` for both Radarr and Sonarr
- Added `stdio_server.py` — a self-contained stdio server using the official MCP SDK
