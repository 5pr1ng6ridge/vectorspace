"""资源路径工具。

约定:
1. 启动时通过 ``init_resource_root`` 指定 ``game/`` 根目录。
2. 运行期其他模块只通过 ``script_path`` / ``asset_path`` 访问资源。
"""

from pathlib import Path

_RESOURCE_ROOT: Path | None = None

def init_resource_root(game_dir: Path) -> None:
    """初始化资源根目录（通常为 ``.../game``）。"""
    global _RESOURCE_ROOT
    _RESOURCE_ROOT = game_dir

def _root() -> Path:
    """返回资源根目录；未初始化时抛错。"""
    if _RESOURCE_ROOT is None:
        raise RuntimeError("resource root not initialized")
    return _RESOURCE_ROOT

def script_path(*parts: str) -> Path:
    """拼接脚本路径：``game/scripts/...``。"""
    return _root() / "scripts" / Path(*parts)

def asset_path(*parts: str) -> Path:
    """拼接资源路径：``game/assets/...``。"""
    return _root() / "assets" / Path(*parts)
