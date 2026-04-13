"""Python 场景脚本辅助。"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Callable

SceneNode = dict[str, Any]
SceneCallable = Callable[..., Any]
SceneLinearItem = SceneNode | SceneCallable
SceneLinearScript = Iterable[SceneLinearItem]


def bg(file: str) -> SceneNode:
    return {"type": "bg", "file": file}


def say(speaker: str, text: str) -> SceneNode:
    return {"type": "say", "speaker": speaker, "text": text}


def formula(latex: str) -> SceneNode:
    return {"type": "formula", "latex": latex}


def style(
    *,
    font_size: int | None = None,
    color: str | None = None,
    name_font_size: int | None = None,
    name_color: str | None = None,
) -> SceneNode:
    node: SceneNode = {"type": "style"}
    if font_size is not None:
        node["font_size"] = int(font_size)
    if color is not None:
        node["color"] = color
    if name_font_size is not None:
        node["name_font_size"] = int(name_font_size)
    if name_color is not None:
        node["name_color"] = name_color
    return node


def typing(
    *,
    speed_ms: int | None = None,
    cps: float | None = None,
) -> SceneNode:
    node: SceneNode = {"type": "typing"}
    if speed_ms is not None:
        node["speed_ms"] = int(speed_ms)
    if cps is not None:
        node["cps"] = float(cps)
    return node


def call(fn: SceneCallable) -> SceneNode:
    return {"type": "call", "fn": fn}


def jump(scene_name: str) -> SceneNode:
    return {"type": "jump", "scene": scene_name}


def dialogue_ui_show(
    *,
    duration_ms: int | None = None,
    easing: str | None = None,
    wait: bool = False,
) -> SceneNode:
    node: SceneNode = {"type": "dialogue_ui_show", "wait": bool(wait)}
    if duration_ms is not None:
        node["duration_ms"] = int(duration_ms)
    if easing is not None:
        node["easing"] = easing
    return node


def dialogue_ui_hide(
    *,
    duration_ms: int | None = None,
    easing: str | None = None,
    wait: bool = False,
) -> SceneNode:
    node: SceneNode = {"type": "dialogue_ui_hide", "wait": bool(wait)}
    if duration_ms is not None:
        node["duration_ms"] = int(duration_ms)
    if easing is not None:
        node["easing"] = easing
    return node


def ui_show(
    *,
    duration_ms: int | None = None,
    easing: str | None = None,
    wait: bool = False,
) -> SceneNode:
    return dialogue_ui_show(duration_ms=duration_ms, easing=easing, wait=wait)


def ui_hide(
    *,
    duration_ms: int | None = None,
    easing: str | None = None,
    wait: bool = False,
) -> SceneNode:
    return dialogue_ui_hide(duration_ms=duration_ms, easing=easing, wait=wait)


def image_register(
    image_id: str,
    file: str,
    *,
    folder: str | None = None,
    x: float | None = None,
    y: float | None = None,
    scale: float | None = None,
    opacity: float | None = None,
    z: int | None = None,
    anchor_x: float | None = None,
    anchor_y: float | None = None,
    visible: bool = False,
) -> SceneNode:
    node: SceneNode = {
        "type": "image_register",
        "id": image_id,
        "file": file,
        "visible": bool(visible),
    }
    if folder is not None:
        node["folder"] = folder
    if x is not None:
        node["x"] = float(x)
    if y is not None:
        node["y"] = float(y)
    if scale is not None:
        node["scale"] = float(scale)
    if opacity is not None:
        node["opacity"] = float(opacity)
    if z is not None:
        node["z"] = int(z)
    if anchor_x is not None:
        node["anchor_x"] = float(anchor_x)
    if anchor_y is not None:
        node["anchor_y"] = float(anchor_y)
    return node


def image_show(
    image_id: str,
    *,
    file: str | None = None,
    folder: str | None = None,
    x: float | None = None,
    y: float | None = None,
    dx: float | None = None,
    dy: float | None = None,
    scale: float | None = None,
    dscale: float | None = None,
    opacity: float | None = None,
    dopacity: float | None = None,
    z: int | None = None,
    duration_ms: int | None = None,
    easing: str | None = None,
    wait: bool = False,
) -> SceneNode:
    node: SceneNode = {
        "type": "image_show",
        "id": image_id,
        "wait": bool(wait),
    }
    if file is not None:
        node["file"] = file
    if folder is not None:
        node["folder"] = folder
    if x is not None:
        node["x"] = float(x)
    if y is not None:
        node["y"] = float(y)
    if dx is not None:
        node["dx"] = float(dx)
    if dy is not None:
        node["dy"] = float(dy)
    if scale is not None:
        node["scale"] = float(scale)
    if dscale is not None:
        node["dscale"] = float(dscale)
    if opacity is not None:
        node["opacity"] = float(opacity)
    if dopacity is not None:
        node["dopacity"] = float(dopacity)
    if z is not None:
        node["z"] = int(z)
    if duration_ms is not None:
        node["duration_ms"] = int(duration_ms)
    if easing is not None:
        node["easing"] = easing
    return node


def image_hide(
    image_id: str,
    *,
    dx: float | None = None,
    dy: float | None = None,
    dscale: float | None = None,
    opacity: float | None = None,
    duration_ms: int | None = None,
    easing: str | None = None,
    wait: bool = False,
    remove: bool = False,
) -> SceneNode:
    node: SceneNode = {
        "type": "image_hide",
        "id": image_id,
        "wait": bool(wait),
        "remove": bool(remove),
    }
    if dx is not None:
        node["dx"] = float(dx)
    if dy is not None:
        node["dy"] = float(dy)
    if dscale is not None:
        node["dscale"] = float(dscale)
    if opacity is not None:
        node["opacity"] = float(opacity)
    if duration_ms is not None:
        node["duration_ms"] = int(duration_ms)
    if easing is not None:
        node["easing"] = easing
    return node


def image_transform(
    image_id: str,
    *,
    x: float | None = None,
    y: float | None = None,
    dx: float | None = None,
    dy: float | None = None,
    scale: float | None = None,
    dscale: float | None = None,
    opacity: float | None = None,
    dopacity: float | None = None,
    z: int | None = None,
    duration_ms: int | None = None,
    easing: str | None = None,
    wait: bool = False,
) -> SceneNode:
    node: SceneNode = {
        "type": "image_transform",
        "id": image_id,
        "wait": bool(wait),
    }
    if x is not None:
        node["x"] = float(x)
    if y is not None:
        node["y"] = float(y)
    if dx is not None:
        node["dx"] = float(dx)
    if dy is not None:
        node["dy"] = float(dy)
    if scale is not None:
        node["scale"] = float(scale)
    if dscale is not None:
        node["dscale"] = float(dscale)
    if opacity is not None:
        node["opacity"] = float(opacity)
    if dopacity is not None:
        node["dopacity"] = float(dopacity)
    if z is not None:
        node["z"] = int(z)
    if duration_ms is not None:
        node["duration_ms"] = int(duration_ms)
    if easing is not None:
        node["easing"] = easing
    return node


def image_remove(image_id: str) -> SceneNode:
    return {"type": "image_remove", "id": image_id}


def image_clear() -> SceneNode:
    return {"type": "image_clear"}


def scene(
    scene_id: str,
    script: SceneLinearScript,
    *,
    defaults: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """构造标准场景字典。"""
    return {"id": scene_id, "defaults": dict(defaults or {}), "script": script}
