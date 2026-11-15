"""Settings come from one TOML file (stdlib tomllib, Python >= 3.11).
The only environment variable is RTS_LOCATION, and it only says where that file is.
"""
from __future__ import annotations

import os
import tomllib
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field


DEFAULT_PATH = Path(__file__).resolve().parents[1] / "rts.toml"


class Paths(BaseModel):
    repo_root: Path
    land_parquet: Path
    columns_json: Path
    analogs: Path
    shortlist: Path
    activities_catalog: Path
    moon_sites: Path
    lola_raw: Path
    notify_token: Path
    raw_data: Path

    @property
    def columns_dir(self) -> Path:
        return self.land_parquet.parent / "columns"


class Server(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8787
    search_base: str = "http://127.0.0.1:8787"
    max_notify_body_bytes: int = 2 * 1024 * 1024


class Commands(BaseModel):
    extract_earth_columns: str


class Cors(BaseModel):
    allow_origins: list[str]
    allow_credentials: bool = False


class Settings(BaseModel):
    paths: Paths
    server: Server = Field(default_factory=Server)
    commands: Commands
    cors: Cors


def _resolve_path(base: Path, value: Path | str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path.resolve()
    return (base / path).resolve()


@lru_cache
def get_settings() -> Settings:
    config_path = Path(os.environ.get("RTS_LOCATION", DEFAULT_PATH)).resolve()
    data = tomllib.loads(config_path.read_text(encoding="utf-8"))
    settings = Settings.model_validate(data)
    root = _resolve_path(config_path.parent, settings.paths.repo_root)
    settings.paths = Paths(
        repo_root=root,
        land_parquet=_resolve_path(root, settings.paths.land_parquet),
        columns_json=_resolve_path(root, settings.paths.columns_json),
        analogs=_resolve_path(root, settings.paths.analogs),
        shortlist=_resolve_path(root, settings.paths.shortlist),
        activities_catalog=_resolve_path(root, settings.paths.activities_catalog),
        moon_sites=_resolve_path(root, settings.paths.moon_sites),
        lola_raw=_resolve_path(root, settings.paths.lola_raw),
        notify_token=_resolve_path(root, settings.paths.notify_token),
        raw_data=_resolve_path(root, settings.paths.raw_data),
    )
    return settings