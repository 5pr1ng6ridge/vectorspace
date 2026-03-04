# src/engine/resources/paths.py
from pathlib import Path

_RESOURCE_ROOT: Path | None = None

def init_resource_root(game_dir: Path) -> None:
    global _RESOURCE_ROOT
    _RESOURCE_ROOT = game_dir

def _root() -> Path:
    if _RESOURCE_ROOT is None:
        raise RuntimeError("resource root not initialized")
    return _RESOURCE_ROOT

def script_path(*parts: str) -> Path:
    return _root() / "scripts" / Path(*parts)

def asset_path(*parts: str) -> Path:
    return _root() / "assets" / Path(*parts)