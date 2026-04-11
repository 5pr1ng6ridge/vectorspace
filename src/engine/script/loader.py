"""Scene script loader.

Supports:
- JSON scene files (legacy): ``game/scripts/scenes/<name>.json``
- Python scene files (preferred): ``game/scripts/scenes/<name>.py``
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any, Callable

from ..resources.paths import script_path

SceneNode = dict[str, Any]
SceneLinearItem = SceneNode | Callable[..., Any]


def load_scene_script(scene_ref: str | Path) -> dict[str, Any]:
    """Load scene script by scene name or explicit path.

    - ``scene_ref`` is ``str``: resolve ``.py`` first, then ``.json``.
    - ``scene_ref`` is ``Path``: load by suffix (``.py``/``.json``).
    """
    if isinstance(scene_ref, Path):
        raw_data = _load_scene_from_path(scene_ref)
        return _normalize_scene_data(raw_data, scene_name=scene_ref.stem)

    if isinstance(scene_ref, str):
        py_path = script_path("scenes", f"{scene_ref}.py")
        json_path = script_path("scenes", f"{scene_ref}.json")

        if py_path.exists():
            raw_data = _load_python_scene(py_path)
            return _normalize_scene_data(raw_data, scene_name=scene_ref)

        if json_path.exists():
            raw_data = _load_json_scene(json_path)
            return _normalize_scene_data(raw_data, scene_name=scene_ref)

        raise FileNotFoundError(
            f"Scene '{scene_ref}' not found. Expected one of: {py_path}, {json_path}"
        )

    raise TypeError("scene_ref must be str or Path")


def _load_scene_from_path(path: Path) -> Any:
    suffix = path.suffix.lower()
    if suffix == ".py":
        return _load_python_scene(path)
    if suffix == ".json":
        return _load_json_scene(path)
    raise ValueError(f"Unsupported scene suffix: {path}")


def _load_json_scene(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _load_python_scene(path: Path) -> Any:
    module_name = f"_vectspace_scene_{path.stem}_{path.stat().st_mtime_ns}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import scene module: {path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return _extract_scene_from_module(module, path)


def _extract_scene_from_module(module: ModuleType, path: Path) -> Any:
    """Extract scene payload from a Python module.

    Supported entry points (priority order):
    1. ``build_scene()`` callable
    2. ``SCENE``
    3. ``scene``
    4. ``SCRIPT``
    5. ``script``
    """
    build_scene = getattr(module, "build_scene", None)
    if build_scene is not None:
        if not callable(build_scene):
            raise TypeError(f"'build_scene' must be callable in: {path}")
        return build_scene()

    for attr in ("SCENE", "scene", "SCRIPT", "script"):
        if hasattr(module, attr):
            return getattr(module, attr)

    raise ValueError(
        f"No scene entry found in {path}. Provide build_scene() or one of: "
        "'SCENE', 'scene', 'SCRIPT', 'script'."
    )


def _normalize_scene_data(raw_data: Any, scene_name: str) -> dict[str, Any]:
    """Normalize loaded scene payload to runner-compatible shape.

    Accepted input forms:
    - Legacy dict with ``nodes`` + ``flow``
    - Dict with ``script`` (linear list form)
    - Bare linear list form
    """
    if isinstance(raw_data, dict):
        if "nodes" in raw_data and "flow" in raw_data:
            return raw_data

        if "script" in raw_data:
            script_items = raw_data["script"]
            if not isinstance(script_items, list):
                raise TypeError("'script' must be a list")
            return _linear_to_graph(
                script_items,
                scene_id=str(raw_data.get("id", scene_name)),
                defaults=raw_data.get("defaults", {}),
            )

        raise ValueError(
            "Scene dict must contain either ('nodes' and 'flow') or 'script'."
        )

    if isinstance(raw_data, list):
        return _linear_to_graph(raw_data, scene_id=scene_name, defaults={})

    raise TypeError("Scene payload must be dict or list")


def _linear_to_graph(
    items: list[SceneLinearItem],
    scene_id: str,
    defaults: dict[str, Any] | None,
) -> dict[str, Any]:
    """Convert linear script list to legacy nodes/flow structure."""
    nodes: dict[str, SceneNode] = {}
    flow: list[str] = []

    for idx, item in enumerate(items):
        node_id = f"n{idx:04d}"
        node: SceneNode

        if callable(item):
            node = {"type": "call", "fn": item}
        elif isinstance(item, dict):
            node = dict(item)
        else:
            raise TypeError(
                f"Linear scene item at index {idx} must be dict or callable, got {type(item)!r}"
            )

        nodes[node_id] = node
        flow.append(node_id)

    return {
        "id": scene_id,
        "defaults": defaults if isinstance(defaults, dict) else {},
        "nodes": nodes,
        "flow": flow,
    }
