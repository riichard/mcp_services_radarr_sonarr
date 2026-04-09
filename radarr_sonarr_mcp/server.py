#!/usr/bin/env python
"""MCP server for Radarr and Sonarr."""

import logging
import os
from typing import Optional

from fastmcp import FastMCP

from radarr_sonarr_mcp.config import RadarrConfig, SonarrConfig, load_config
from radarr_sonarr_mcp.services.radarr_service import RadarrService
from radarr_sonarr_mcp.services.sonarr_service import SonarrService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _radarr(cfg: dict) -> RadarrService:
    nas_ip = cfg["nasConfig"]["ip"]
    r = cfg["radarrConfig"]
    return RadarrService(RadarrConfig(
        api_key=r["apiKey"],
        base_url=f"http://{nas_ip}:{r.get('port', '7878')}{r.get('basePath', '/api/v3')}",
        port=r.get("port", "7878"),
    ))


def _sonarr(cfg: dict) -> SonarrService:
    nas_ip = cfg["nasConfig"]["ip"]
    s = cfg["sonarrConfig"]
    return SonarrService(SonarrConfig(
        api_key=s["apiKey"],
        base_url=f"http://{nas_ip}:{s.get('port', '8989')}{s.get('basePath', '/api/v3')}",
        port=s.get("port", "8989"),
    ))


class RadarrSonarrMCP:
    def __init__(self):
        self.config = load_config().__dict__ if not isinstance(load_config(), dict) else load_config()
        # Rebuild as the raw dict format the helpers expect
        cfg = load_config()
        self.config = {
            "nasConfig": {"ip": cfg.nas_config.ip, "port": cfg.nas_config.port},
            "radarrConfig": {
                "apiKey": cfg.radarr_config.api_key,
                "port": cfg.radarr_config.port,
                "basePath": "/api/v3",
            },
            "sonarrConfig": {
                "apiKey": cfg.sonarr_config.api_key,
                "port": cfg.sonarr_config.port,
                "basePath": "/api/v3",
            },
            "server": {"port": cfg.server_config.port},
        }
        self.server = FastMCP("radarr-sonarr-mcp-server")
        self._register_tools()

    # ------------------------------------------------------------------
    # Tools
    # ------------------------------------------------------------------
    def _register_tools(self):
        cfg = self.config

        # ---- Movies ----

        @self.server.tool()
        def get_available_movies(
            year: Optional[int] = None,
            downloaded: Optional[bool] = None,
            actors: Optional[str] = None,
        ) -> dict:
            """List movies in Radarr with optional filters."""
            movies = _radarr(cfg).get_all_movies()
            if year is not None:
                movies = [m for m in movies if m.year == year]
            if downloaded is not None:
                movies = [m for m in movies if m.has_file == downloaded]
            if actors:
                movies = [
                    m for m in movies
                    if m.data and any(
                        actors.lower() in c.get("name", "").lower()
                        for c in m.data.get("credits", {}).get("cast", [])
                    )
                ]
            return {
                "count": len(movies),
                "movies": [
                    {
                        "id": m.id,
                        "title": m.title,
                        "year": m.year,
                        "overview": m.overview,
                        "downloaded": m.has_file,
                        "status": m.status,
                        "genres": m.genres or [],
                    }
                    for m in movies
                ],
            }

        @self.server.tool()
        def lookup_movie(term: str) -> dict:
            """Search for a movie by title (searches TMDB via Radarr)."""
            results = _radarr(cfg).lookup_movie(term)
            return {
                "count": len(results),
                "movies": [
                    {
                        "tmdbId": m.data.get("tmdbId"),
                        "title": m.title,
                        "year": m.year,
                        "overview": m.overview,
                        "status": m.status,
                        "inLibrary": m.id != 0,
                    }
                    for m in results
                ],
            }

        @self.server.tool()
        def add_movie(
            tmdb_id: int,
            quality_profile_id: int,
            root_folder_path: str = "/mnt/media/movies",
            search_on_add: bool = True,
            monitored: bool = True,
        ) -> dict:
            """Add a movie to Radarr and optionally trigger a search."""
            return _radarr(cfg).add_movie(
                tmdb_id=tmdb_id,
                quality_profile_id=quality_profile_id,
                root_folder_path=root_folder_path,
                search_on_add=search_on_add,
                monitored=monitored,
            )

        @self.server.tool()
        def get_radarr_quality_profiles() -> dict:
            """List quality profiles configured in Radarr."""
            return _radarr(cfg).get_quality_profiles()

        @self.server.tool()
        def get_radarr_root_folders() -> dict:
            """List root folders configured in Radarr."""
            return _radarr(cfg).get_root_folders()

        # ---- Series ----

        @self.server.tool()
        def get_available_series(
            year: Optional[int] = None,
            downloaded: Optional[bool] = None,
            actors: Optional[str] = None,
        ) -> dict:
            """List TV series in Sonarr with optional filters."""
            service = _sonarr(cfg)
            series = service.get_all_series()
            if year is not None:
                series = [s for s in series if s.year == year]
            if downloaded is not None:
                series = [
                    s for s in series
                    if bool(s.statistics and s.statistics.episode_file_count > 0) == downloaded
                ]
            if actors:
                series = [
                    s for s in series
                    if s.data and any(
                        actors.lower() in c.get("name", "").lower()
                        for c in s.data.get("credits", {}).get("cast", [])
                    )
                ]
            return {
                "count": len(series),
                "series": [
                    {
                        "id": s.id,
                        "title": s.title,
                        "year": s.year,
                        "overview": s.overview,
                        "status": s.status,
                        "network": s.network,
                        "genres": s.genres or [],
                        "episodesDownloaded": s.statistics.episode_file_count if s.statistics else 0,
                        "episodesTotal": s.statistics.episode_count if s.statistics else 0,
                        "fullyDownloaded": service.is_series_watched(s),
                    }
                    for s in series
                ],
            }

        @self.server.tool()
        def lookup_series(term: str) -> dict:
            """Search for a TV series by title (searches TVDB via Sonarr)."""
            results = _sonarr(cfg).lookup_series(term)
            return {
                "count": len(results),
                "series": [
                    {
                        "tvdbId": s.data.get("tvdbId"),
                        "title": s.title,
                        "year": s.year,
                        "overview": s.overview,
                        "status": s.status,
                        "network": s.network,
                        "inLibrary": s.id != 0,
                        "seasons": [
                            {"seasonNumber": sn.get("seasonNumber"), "monitored": sn.get("monitored", True)}
                            for sn in s.data.get("seasons", [])
                        ],
                    }
                    for s in results
                ],
            }

        @self.server.tool()
        def add_series(
            tvdb_id: int,
            quality_profile_id: int,
            root_folder_path: str = "/mnt/media/tv",
            search_on_add: bool = True,
            monitored: bool = True,
        ) -> dict:
            """Add a TV series to Sonarr and optionally trigger a search for all episodes."""
            return _sonarr(cfg).add_series(
                tvdb_id=tvdb_id,
                quality_profile_id=quality_profile_id,
                root_folder_path=root_folder_path,
                search_on_add=search_on_add,
                monitored=monitored,
            )

        @self.server.tool()
        def get_series_episodes(series_id: int) -> dict:
            """Get all episodes for a series by its Sonarr ID."""
            episodes = _sonarr(cfg).get_episodes(series_id)
            return {
                "count": len(episodes),
                "episodes": [
                    {
                        "id": e.id,
                        "season": e.season_number,
                        "episode": e.episode_number,
                        "title": e.title,
                        "airDate": e.air_date,
                        "downloaded": e.has_file,
                        "monitored": e.monitored,
                    }
                    for e in episodes
                ],
            }

        @self.server.tool()
        def get_sonarr_quality_profiles() -> dict:
            """List quality profiles configured in Sonarr."""
            return _sonarr(cfg).get_quality_profiles()

        @self.server.tool()
        def get_sonarr_root_folders() -> dict:
            """List root folders configured in Sonarr."""
            return _sonarr(cfg).get_root_folders()

    def run(self):
        port = self.config["server"]["port"]
        logger.info(f"Starting MCP server on port {port}")
        self.server.run(transport="streamable-http", host="0.0.0.0", port=port)


def main():
    RadarrSonarrMCP().run()


if __name__ == "__main__":
    main()
