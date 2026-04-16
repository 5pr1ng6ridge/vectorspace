"""场景脚本加载器（Python 版）。"""

from __future__ import annotations

import importlib.util
from collections.abc import Iterable
from pathlib import Path
from types import ModuleType
from typing import Any, Callable

from ..resources.paths import script_path

SceneNode = dict[str, Any]
SceneLinearItem = SceneNode | Callable[..., Any]
_SCENE_CACHE: dict[str, tuple[int, dict[str, Any]]] = {}


def load_scene_script(scene_ref: str | Path) -> dict[str, Any]:
    """加载场景脚本并规范化为 Runner 可消费的数据结构。"""
    if isinstance(scene_ref, Path):
        path = scene_ref
        if path.suffix.lower() != ".py":
            raise ValueError(f"仅支持 Python 场景脚本（.py）：{path}")
        return _load_cached_scene_script(path, scene_name=path.stem)

    if isinstance(scene_ref, str):
        path = script_path("scenes", f"{scene_ref}.py")
        if not path.exists():
            raise FileNotFoundError(f"未找到场景脚本：{path}")
        return _load_cached_scene_script(path, scene_name=scene_ref)

    raise TypeError("scene_ref 必须是 str 或 Path")

def _load_cached_scene_script(path: Path, *, scene_name: str) -> dict[str, Any]:
    cache_key = str(path.resolve())
    mtime_ns = path.stat().st_mtime_ns
    cached = _SCENE_CACHE.get(cache_key)
    if cached is not None and cached[0] == mtime_ns:
        return cached[1]

    raw_data = _load_python_scene(path)
    normalized = _normalize_scene_data(raw_data, scene_name=scene_name)
    _SCENE_CACHE[cache_key] = (mtime_ns, normalized)
    return normalized


def _load_python_scene(path: Path) -> Any:
    """导入 Python 场景模块并提取场景对象。"""
    module_name = f"_vectspace_scene_{path.stem}_{path.stat().st_mtime_ns}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法导入场景模块：{path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return _extract_scene_from_module(module, path)


def _extract_scene_from_module(module: ModuleType, path: Path) -> Any:
    """按约定从模块中提取场景数据。"""
    for builder_name in ("build_scene", "build_script"):
        builder = getattr(module, builder_name, None)
        if builder is None:
            continue
        if not callable(builder):
            raise TypeError(f"{path} 中的 {builder_name} 必须是可调用对象")
        return _maybe_wrap_linear_scene(builder(), module, path)

    for attr in ("SCENE", "scene", "SCRIPT", "script"):
        if hasattr(module, attr):
            return _maybe_wrap_linear_scene(getattr(module, attr), module, path)

    raise ValueError(
        f"{path} 未提供场景入口。请定义 build_scene()/build_script() 或 SCENE/scene/SCRIPT/script。"
    )


def _maybe_wrap_linear_scene(raw_data: Any, module: ModuleType, path: Path) -> Any:
    """把“线性脚本对象”包装成标准 scene dict。"""
    if isinstance(raw_data, dict):
        return raw_data

    if not _is_linear_script_object(raw_data):
        return raw_data

    return {
        "id": _read_scene_id(module, path),
        "defaults": _read_scene_defaults(module, path),
        "script": raw_data,
    }


def _read_scene_id(module: ModuleType, path: Path) -> str:
    scene_id = getattr(module, "SCENE_ID", None)
    if scene_id is None:
        scene_id = getattr(module, "scene_id", None)
    if scene_id is None:
        return path.stem
    scene_id_str = str(scene_id).strip()
    if not scene_id_str:
        raise ValueError(f"{path} 的 SCENE_ID/scene_id 不能为空")
    return scene_id_str


def _read_scene_defaults(module: ModuleType, path: Path) -> dict[str, Any]:
    defaults = getattr(module, "DEFAULTS", None)
    if defaults is None:
        defaults = getattr(module, "defaults", None)

    if defaults is None:
        return {}
    if not isinstance(defaults, dict):
        raise TypeError(f"{path} 的 DEFAULTS/defaults 必须是 dict")
    return defaults


def _normalize_scene_data(raw_data: Any, scene_name: str) -> dict[str, Any]:
    """把 Python 场景数据规范化为 Runner 使用的 nodes+flow。"""
    if isinstance(raw_data, dict):
        if "nodes" in raw_data and "flow" in raw_data:
            return raw_data

        if "script" in raw_data:
            script_items = _coerce_script_items(raw_data["script"], where="'script'")
            return _linear_to_graph(
                script_items,
                scene_id=str(raw_data.get("id", scene_name)),
                defaults=raw_data.get("defaults", {}),
            )

        raise ValueError("场景 dict 必须包含 ('nodes' 与 'flow')，或包含 'script'。")

    script_items = _coerce_script_items(raw_data, where="scene root")
    return _linear_to_graph(script_items, scene_id=scene_name, defaults={})


def _coerce_script_items(raw_data: Any, *, where: str) -> list[SceneLinearItem]:
    if _is_linear_script_object(raw_data):
        return list(raw_data)
    raise TypeError(f"{where} 必须是线性脚本（iterable[dict|callable]）")


def _is_linear_script_object(raw_data: Any) -> bool:
    """判断对象是否可视为“线性脚本”。"""
    if isinstance(raw_data, (str, bytes, bytearray, dict, Path)):
        return False
    return isinstance(raw_data, Iterable)


def _linear_to_graph(
    items: list[SceneLinearItem],
    scene_id: str,
    defaults: dict[str, Any] | None,
) -> dict[str, Any]:
    """把线性脚本转为 Runner 现有图结构。"""
    nodes: dict[str, SceneNode] = {}
    flow: list[str] = []

    for idx, item in enumerate(items):
        node_id = f"n{idx:04d}"

        if callable(item):
            node: SceneNode = {"type": "call", "fn": item}
        elif isinstance(item, dict):
            node = dict(item)
        else:
            raise TypeError(
                f"线性脚本第 {idx} 项必须是 dict 或 callable，实际为 {type(item)!r}"
            )

        nodes[node_id] = node
        flow.append(node_id)

    return {
        "id": scene_id,
        "defaults": defaults if isinstance(defaults, dict) else {},
        "nodes": nodes,
        "flow": flow,
    }
