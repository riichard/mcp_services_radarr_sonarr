#!/usr/bin/env python
"""Local stdio MCP server — connects to Radarr/Sonarr on c42x."""

import asyncio
import json
import logging
import os
import subprocess
import urllib.parse
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

logging.basicConfig(level=logging.WARNING)

NAS_IP = os.environ.get("NAS_IP", "192.168.178.90")
RADARR_URL = f"http://{NAS_IP}:{os.environ.get('RADARR_PORT', '7878')}/api/v3"
SONARR_URL = f"http://{NAS_IP}:{os.environ.get('SONARR_PORT', '8989')}/api/v3"
RADARR_KEY = os.environ["RADARR_API_KEY"]
SONARR_KEY = os.environ["SONARR_API_KEY"]


def _curl(method: str, url: str, params: dict = None, body: dict = None) -> Any:
    """Make HTTP request via curl (bypasses macOS socket routing issues)."""
    if params:
        url += "?" + urllib.parse.urlencode(params)
    cmd = ["curl", "-s", "-X", method, url]
    if body is not None:
        cmd += ["-H", "Content-Type: application/json", "-d", json.dumps(body)]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        raise Exception(f"curl failed: {result.stderr}")
    data = json.loads(result.stdout)
    if isinstance(data, list) and len(data) and isinstance(data[0], dict) and "errorMessage" in data[0]:
        raise Exception(f"API error: {data[0]['errorMessage']}")
    return data


def radarr(path: str, method="GET", params=None, json=None) -> Any:
    p = dict(params or {})
    p["apikey"] = RADARR_KEY
    return _curl(method, f"{RADARR_URL}{path}", params=p, body=json)


def sonarr(path: str, method="GET", params=None, json=None) -> Any:
    p = dict(params or {})
    p["apikey"] = SONARR_KEY
    return _curl(method, f"{SONARR_URL}{path}", params=p, body=json)


server = Server("radarr-sonarr-mcp")


@server.list_tools()
async def list_tools():
    return [
        Tool(name="get_available_movies", description="List movies in Radarr", inputSchema={"type": "object", "properties": {"year": {"type": "integer"}, "downloaded": {"type": "boolean"}}}),
        Tool(name="lookup_movie", description="Search for a movie via Radarr/TMDB", inputSchema={"type": "object", "properties": {"term": {"type": "string"}}, "required": ["term"]}),
        Tool(name="add_movie", description="Add a movie to Radarr by TMDB ID", inputSchema={"type": "object", "properties": {"tmdb_id": {"type": "integer"}, "quality_profile_id": {"type": "integer"}, "root_folder_path": {"type": "string"}, "search_on_add": {"type": "boolean"}}, "required": ["tmdb_id", "quality_profile_id"]}),
        Tool(name="get_radarr_quality_profiles", description="List Radarr quality profiles", inputSchema={"type": "object", "properties": {}}),
        Tool(name="get_radarr_root_folders", description="List Radarr root folders", inputSchema={"type": "object", "properties": {}}),
        Tool(name="get_available_series", description="List TV series in Sonarr", inputSchema={"type": "object", "properties": {"year": {"type": "integer"}, "downloaded": {"type": "boolean"}}}),
        Tool(name="lookup_series", description="Search for a TV series via Sonarr/TVDB", inputSchema={"type": "object", "properties": {"term": {"type": "string"}}, "required": ["term"]}),
        Tool(name="add_series", description="Add a TV series to Sonarr by TVDB ID", inputSchema={"type": "object", "properties": {"tvdb_id": {"type": "integer"}, "quality_profile_id": {"type": "integer"}, "root_folder_path": {"type": "string"}, "search_on_add": {"type": "boolean"}}, "required": ["tvdb_id", "quality_profile_id"]}),
        Tool(name="get_series_episodes", description="Get episodes for a series by Sonarr ID", inputSchema={"type": "object", "properties": {"series_id": {"type": "integer"}}, "required": ["series_id"]}),
        Tool(name="get_sonarr_quality_profiles", description="List Sonarr quality profiles", inputSchema={"type": "object", "properties": {}}),
        Tool(name="get_sonarr_root_folders", description="List Sonarr root folders", inputSchema={"type": "object", "properties": {}}),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict):
    try:
        result = dispatch(name, arguments)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]
    except Exception as e:
        return [TextContent(type="text", text=json.dumps({"error": str(e)}))]


def dispatch(name: str, args: dict) -> Any:
    if name == "get_available_movies":
        movies = radarr("/movie")
        if args.get("year"):
            movies = [m for m in movies if m.get("year") == args["year"]]
        if args.get("downloaded") is not None:
            movies = [m for m in movies if m.get("hasFile") == args["downloaded"]]
        return {"count": len(movies), "movies": [
            {"id": m["id"], "title": m["title"], "year": m.get("year"),
             "downloaded": m.get("hasFile"), "status": m.get("status"),
             "overview": m.get("overview", "")[:200]}
            for m in movies
        ]}

    elif name == "lookup_movie":
        results = radarr("/movie/lookup", params={"term": args["term"]})
        return {"count": len(results), "movies": [
            {"tmdbId": m.get("tmdbId"), "title": m["title"], "year": m.get("year"),
             "overview": m.get("overview", "")[:200], "inLibrary": "id" in m}
            for m in results
        ]}

    elif name == "add_movie":
        results = radarr("/movie/lookup", params={"term": f"tmdb:{args['tmdb_id']}"})
        if not results:
            raise Exception(f"No movie found with TMDB ID {args['tmdb_id']}")
        m = results[0]
        payload = {
            "tmdbId": args["tmdb_id"], "title": m["title"], "year": m.get("year"),
            "qualityProfileId": args["quality_profile_id"],
            "rootFolderPath": args.get("root_folder_path", "/mnt/media/movies"),
            "monitored": args.get("monitored", True),
            "addOptions": {"searchForMovie": args.get("search_on_add", True)},
        }
        added = radarr("/movie", method="POST", json=payload)
        return {"id": added.get("id"), "title": added.get("title"), "status": "added"}

    elif name == "get_radarr_quality_profiles":
        profiles = radarr("/qualityprofile")
        return {"profiles": [{"id": p["id"], "name": p["name"]} for p in profiles]}

    elif name == "get_radarr_root_folders":
        folders = radarr("/rootfolder")
        return {"folders": [{"id": f["id"], "path": f["path"]} for f in folders]}

    elif name == "get_available_series":
        series = sonarr("/series")
        if args.get("year"):
            series = [s for s in series if s.get("year") == args["year"]]
        if args.get("downloaded") is not None:
            series = [s for s in series
                      if bool(s.get("statistics", {}).get("episodeFileCount", 0) > 0) == args["downloaded"]]
        return {"count": len(series), "series": [
            {"id": s["id"], "title": s["title"], "year": s.get("year"),
             "status": s.get("status"), "network": s.get("network"),
             "episodesDownloaded": s.get("statistics", {}).get("episodeFileCount", 0),
             "episodesTotal": s.get("statistics", {}).get("episodeCount", 0),
             "overview": s.get("overview", "")[:200]}
            for s in series
        ]}

    elif name == "lookup_series":
        results = sonarr("/series/lookup", params={"term": args["term"]})
        return {"count": len(results), "series": [
            {"tvdbId": s.get("tvdbId"), "title": s["title"], "year": s.get("year"),
             "overview": s.get("overview", "")[:200], "status": s.get("status"),
             "network": s.get("network"), "inLibrary": "id" in s,
             "seasons": [{"seasonNumber": sn.get("seasonNumber")} for sn in s.get("seasons", [])]}
            for s in results
        ]}

    elif name == "add_series":
        results = sonarr("/series/lookup", params={"term": f"tvdb:{args['tvdb_id']}"})
        if not results:
            raise Exception(f"No series found with TVDB ID {args['tvdb_id']}")
        s = results[0]
        payload = {
            "tvdbId": args["tvdb_id"], "title": s["title"],
            "qualityProfileId": args["quality_profile_id"],
            "rootFolderPath": args.get("root_folder_path", "/mnt/media/tv"),
            "seasonFolder": True, "monitored": args.get("monitored", True),
            "seriesType": "standard", "seasons": s.get("seasons", []),
            "addOptions": {"searchForMissingEpisodes": args.get("search_on_add", True), "monitor": "all"},
        }
        added = sonarr("/series", method="POST", json=payload)
        return {"id": added.get("id"), "title": added.get("title"), "status": "added"}

    elif name == "get_series_episodes":
        episodes = sonarr("/episode", params={"seriesId": args["series_id"]})
        return {"count": len(episodes), "episodes": [
            {"season": e["seasonNumber"], "episode": e["episodeNumber"],
             "title": e.get("title"), "downloaded": e.get("hasFile"), "airDate": e.get("airDate")}
            for e in episodes
        ]}

    elif name == "get_sonarr_quality_profiles":
        profiles = sonarr("/qualityprofile")
        return {"profiles": [{"id": p["id"], "name": p["name"]} for p in profiles]}

    elif name == "get_sonarr_root_folders":
        folders = sonarr("/rootfolder")
        return {"folders": [{"id": f["id"], "path": f["path"]} for f in folders]}

    else:
        raise ValueError(f"Unknown tool: {name}")


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
