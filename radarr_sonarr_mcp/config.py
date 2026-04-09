"""Configuration dataclasses for the Radarr/Sonarr MCP server."""

import json
import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class NasConfig:
    ip: str
    port: str = "7878"


@dataclass
class RadarrConfig:
    api_key: str
    base_url: str
    port: str = "7878"


@dataclass
class SonarrConfig:
    api_key: str
    base_url: str
    port: str = "8989"


@dataclass
class ServerConfig:
    port: int = 3000


@dataclass
class Config:
    nas_config: NasConfig
    radarr_config: RadarrConfig
    sonarr_config: SonarrConfig
    server_config: ServerConfig


def load_config(config_path: str = "config.json") -> Config:
    if os.environ.get("RADARR_API_KEY"):
        nas_ip = os.environ.get("NAS_IP", "10.0.0.23")
        radarr_port = os.environ.get("RADARR_PORT", "7878")
        radarr_base_path = os.environ.get("RADARR_BASE_PATH", "/api/v3")
        sonarr_port = os.environ.get("SONARR_PORT", "8989")
        sonarr_base_path = os.environ.get("SONARR_BASE_PATH", "/api/v3")
        return Config(
            nas_config=NasConfig(ip=nas_ip),
            radarr_config=RadarrConfig(
                api_key=os.environ["RADARR_API_KEY"],
                base_url=f"http://{nas_ip}:{radarr_port}{radarr_base_path}",
                port=radarr_port,
            ),
            sonarr_config=SonarrConfig(
                api_key=os.environ.get("SONARR_API_KEY", ""),
                base_url=f"http://{nas_ip}:{sonarr_port}{sonarr_base_path}",
                port=sonarr_port,
            ),
            server_config=ServerConfig(port=int(os.environ.get("MCP_SERVER_PORT", "3000"))),
        )

    with open(config_path) as f:
        d = json.load(f)
    nas_ip = d["nasConfig"]["ip"]
    radarr_port = d["radarrConfig"].get("port", "7878")
    radarr_base_path = d["radarrConfig"].get("basePath", "/api/v3")
    sonarr_port = d["sonarrConfig"].get("port", "8989")
    sonarr_base_path = d["sonarrConfig"].get("basePath", "/api/v3")
    return Config(
        nas_config=NasConfig(ip=nas_ip, port=d["nasConfig"].get("port", "7878")),
        radarr_config=RadarrConfig(
            api_key=d["radarrConfig"]["apiKey"],
            base_url=f"http://{nas_ip}:{radarr_port}{radarr_base_path}",
            port=radarr_port,
        ),
        sonarr_config=SonarrConfig(
            api_key=d["sonarrConfig"]["apiKey"],
            base_url=f"http://{nas_ip}:{sonarr_port}{sonarr_base_path}",
            port=sonarr_port,
        ),
        server_config=ServerConfig(port=int(d.get("server", {}).get("port", 3000))),
    )


def save_config(config: Config, config_path: str = "config.json") -> None:
    d = {
        "nasConfig": {"ip": config.nas_config.ip, "port": config.nas_config.port},
        "radarrConfig": {
            "apiKey": config.radarr_config.api_key,
            "port": config.radarr_config.port,
            "basePath": "/api/v3",
        },
        "sonarrConfig": {
            "apiKey": config.sonarr_config.api_key,
            "port": config.sonarr_config.port,
            "basePath": "/api/v3",
        },
        "server": {"port": config.server_config.port},
    }
    with open(config_path, "w") as f:
        json.dump(d, f, indent=2)
